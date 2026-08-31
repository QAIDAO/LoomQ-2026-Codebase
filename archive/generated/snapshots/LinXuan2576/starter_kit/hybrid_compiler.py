#!/usr/bin/env python3
"""L3 Hybrid-QASM 混合编译器（方案 A：三段式小编译器）。

输入：Hybrid-QASM 文本（OpenQASM 2.0 + 一个 classical {…} 经典控制块）
输出：
  split_hybrid(source)         → (量子部分 QASM 文本, classical 块文本)
  compile_classical(block)     → RISC-V 汇编文本（riscv_emulator.py 可直接运行）

三段式结构（编译原理入门，服务 PWN/逆向路线）：
  1. 词法分析 tokenize() —— 字符串 → token 流
  2. 语法分析 parse_*()   —— token 流 → 语法树 AST（递归下降）
  3. 代码生成 codegen()   —— AST → RISC-V 汇编

寄存器约定（与赛题契约一致）：
  r1..r9   → x1..x9    用户变量
  c[k]     → x10+k     测量值（评测系统注入 x10 起）
  x20      → 编译器专用临时寄存器（r1..r9 / c[k] 均不会占用）
  x0       → 恒 0（RISC-V 硬约定），add rd, rs, x0 用作寄存器拷贝
"""

import re
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# 第 0 步：分割器 —— 把 Hybrid-QASM 拆成「量子部分」+「classical 块」
# ---------------------------------------------------------------------------

def split_hybrid(source: str) -> Tuple[str, str]:
    """剥离 classical 块，返回 (量子部分 QASM 文本, classical 块文本)。

    处理要点：
      - 支持单行/多行 classical 块（评测用例两种都有）
      - 用大括号深度配对找块边界，块内注释先按行剥掉（防注释里的
        { } 干扰配对）
      - 只找第一个 classical 块（规格约定每份输入一个）
    """
    # 按行剥离 // 注释，保留行结构
    clean = []
    for line in source.splitlines():
        code = line.split("//", 1)[0]
        clean.append(code)
    text = "\n".join(clean)

    m = re.search(r"\bclassical\b", text)
    if not m:
        raise ValueError("no classical block found in Hybrid-QASM")

    # 从关键字后找 '{'，然后深度配对找匹配的 '}'
    i = text.find("{", m.end())
    if i == -1:
        raise ValueError("classical block missing '{'")
    depth = 0
    j = i
    while j < len(text):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    if depth != 0:
        raise ValueError("unbalanced braces in classical block")

    classical_text = text[i:j + 1]
    quantum_text = text[:m.start()] + text[j + 1:]
    return quantum_text, classical_text


# ---------------------------------------------------------------------------
# 第 1 步：词法分析 —— 字符串 → token 流
# ---------------------------------------------------------------------------
# 把经典块拆成最小单元：整数、r 寄存器、c 测量位、运算符/括号/分号、
# 关键字（if/else）。
# 顺序很重要：cbit 必须先于 ident（c[0] 不能拆成 c + [0]），
# == 必须先于 =，int 必须先于 ident。

class Token:
    __slots__ = ("kind", "value", "pos")

    def __init__(self, kind: str, value: str, pos: int):
        self.kind = kind    # 'int' | 'reg' | 'cbit' | 'ident' | 'op'
        self.value = value  # 原文（数字、"r1"、"c[0]"、"=="、";"…）
        self.pos = pos      # 在输入字符串中的偏移（报错定位用）

    def __repr__(self):
        return "Token(%s, %r)" % (self.kind, self.value)


_TOKEN_PATTERNS: List[Tuple[str, str]] = [
    ("int",   r"\d+"),
    ("cbit",  r"c\[\d+\]"),
    ("reg",   r"r[1-9]"),                      # 规格只允许 r1..r9
    ("ident", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("op",    r"==|!=|\+|-|=|\(|\)|\{|\}|;"),
]


def tokenize(text: str) -> List[Token]:
    tokens = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        for kind, pattern in _TOKEN_PATTERNS:
            m = re.match(pattern, text[i:])
            if m:
                tokens.append(Token(kind, m.group(0), i))
                i += len(m.group(0))
                break
        else:
            raise SyntaxError("unexpected char %r at position %d" % (ch, i))
    return tokens


# ---------------------------------------------------------------------------
# 第 2 步：语法分析 —— token 流 → 语法树 AST（递归下降）
# ---------------------------------------------------------------------------
# 迷你文法：
#   program := stmt*
#   stmt    := assign | ifstmt
#   assign  := rN '=' operand (('+'|'-') operand)? ';'
#   ifstmt  := 'if' '(' cond ')' '{' program '}' ('else' '{' program '}')?
#   cond    := operand ('=='|'!=') operand
#   operand := int | rN | c[k]
#
# 递归下降 = 每个文法规则写一个同名函数，遇到什么结构就调什么函数。
# 优点：结构直接对应文法，天然处理嵌套 if/else 归属（else 跟最近的
# 未闭合 if 配对）。这正是逆向里"还原控制流"的反过程。

class Assign:
    """rN = 表达式"""
    __slots__ = ("dst", "terms", "ops")

    def __init__(self, dst: Token, terms: List[Token], ops: List[Token]):
        self.dst = dst
        self.terms = terms          # 1~2 个操作数 token
        self.ops = ops              # 0~1 个 '+'/'-' token


class IfStmt:
    """if (lhs cmp rhs) { then_body } [else { else_body }]"""
    __slots__ = ("lhs", "cmp", "rhs", "then_body", "else_body")

    def __init__(self, lhs: Token, cmp: Token, rhs: Token,
                 then_body: List, else_body: Optional[List]):
        self.lhs = lhs
        self.cmp = cmp              # '==' | '!=' token
        self.rhs = rhs
        self.then_body = then_body
        self.else_body = else_body  # None = 无 else


class Parser:
    """带位置指针的递归下降解析器。pos 存进列表以便闭包修改。"""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    # -- 基础工具 ---------------------------------------------------------

    def peek(self) -> Optional[Token]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def expect_op(self, value: str) -> Token:
        """吃掉一个指定运算符 token，否则报错。"""
        t = self.peek()
        if t is None or t.kind != "op" or t.value != value:
            raise SyntaxError("expect %r near position %d, got %r"
                              % (value, t.pos if t else -1,
                                 t.value if t else "EOF"))
        self.pos += 1
        return t

    def expect_operand(self) -> Token:
        """吃掉一个操作数 token（int | reg | cbit）。"""
        t = self.peek()
        if t is None or t.kind not in ("int", "reg", "cbit"):
            raise SyntaxError("expect operand near position %d, got %r"
                              % (t.pos if t else -1, t.value if t else "EOF"))
        self.pos += 1
        return t

    def expect_if(self, value: str) -> None:
        """吃掉关键字 if/else（ident token）。"""
        t = self.peek()
        if t is None or t.kind != "ident" or t.value != value:
            raise SyntaxError("expect %r near position %d, got %r"
                              % (value, t.pos if t else -1,
                                 t.value if t else "EOF"))
        self.pos += 1

    # -- 文法规则 ---------------------------------------------------------

    def parse_program(self) -> List:
        """program := stmt*（读到 '}' 为止）"""
        stmts = []
        while True:
            t = self.peek()
            if t is None or t.value == "}":
                break
            stmts.append(self.parse_stmt())
        return stmts

    def parse_stmt(self):
        t = self.peek()
        if t is None:
            raise SyntaxError("unexpected end of classical block")
        if t.kind == "ident" and t.value == "if":
            return self.parse_if()
        return self.parse_assign()

    def parse_assign(self) -> Assign:
        """assign := rN '=' operand (('+'|'-') operand)? ';'"""
        dst = self.peek()
        if dst is None or dst.kind != "reg":
            raise SyntaxError("assign target must be r1..r9 near %r" % (dst,))
        self.pos += 1
        self.expect_op("=")
        terms = [self.expect_operand()]
        ops = []
        t = self.peek()
        if t is not None and t.kind == "op" and t.value in ("+", "-"):
            self.pos += 1
            ops.append(t)
            terms.append(self.expect_operand())
        self.expect_op(";")
        return Assign(dst, terms, ops)

    def parse_if(self) -> IfStmt:
        """ifstmt := 'if' '(' cond ')' '{' program '}' ('else' '{' program '}')?"""
        self.expect_if("if")
        self.expect_op("(")
        lhs = self.expect_operand()
        cmp = self.peek()
        if cmp is None or cmp.kind != "op" or cmp.value not in ("==", "!="):
            raise SyntaxError("if condition must use == or !=, got %r" % (cmp,))
        self.pos += 1
        rhs = self.expect_operand()
        self.expect_op(")")
        self.expect_op("{")
        then_body = self.parse_program()
        self.expect_op("}")
        else_body = None
        t = self.peek()
        if t is not None and t.kind == "ident" and t.value == "else":
            self.pos += 1
            self.expect_op("{")
            else_body = self.parse_program()
            self.expect_op("}")
        return IfStmt(lhs, cmp, rhs, then_body, else_body)


def parse_classical(block: str) -> List:
    """入口：classical 块文本（含外层 { }）→ AST 语句列表。"""
    tokens = tokenize(block)
    parser = Parser(tokens)
    parser.expect_op("{")
    stmts = parser.parse_program()
    parser.expect_op("}")
    if parser.peek() is not None:
        raise SyntaxError("trailing tokens after classical block")
    return stmts


# ---------------------------------------------------------------------------
# 第 3 步：代码生成 —— AST → RISC-V 汇编
# ---------------------------------------------------------------------------
# 指令集只有 7 条（riscv_emulator.py）：li / add / sub / addi / beq / bne / j
#   li   rd, imm          rd = 立即数
#   add  rd, rs1, rs2     rd = rs1 + rs2
#   sub  rd, rs1, rs2     rd = rs1 - rs2
#   addi rd, rs1, imm     rd = rs1 + 立即数
#   beq  rs1, rs2, L      rs1 == rs2 时跳 L
#   bne  rs1, rs2, L      rs1 != rs2 时跳 L
#   j    L                无条件跳 L
#
# 翻译要点：
#   - 用户变量 rN → xN；测量位 c[k] → x10+k（读 x10+k 即得测量值）
#   - 表达式翻译成"寄存器 + 立即数"最佳路径：rN±imm → addi（一条指令），
#     寄存器±寄存器 → add/sub，纯常量 → 编译期折叠成 li
#   - if 翻译成"条件跳转跳过 then 块"：
#       条件 ==  → bne 到 else/end（不等才跳过）
#       条件 !=  → beq 到 else/end（相等才跳过）
#     相当于把 then/else 块反向落地，再用 j 跳过对方 —— 这是所有
#     编译器的标准做法（分支反转 + 标签配对）
#   - 标签用计数器生成 L0/L1/L2…，嵌套 if 不会重名

def compile_classical(block: str) -> str:
    ast = parse_classical(block)
    lines: List[str] = []
    label_counter = [0]

    def new_label() -> str:
        label_counter[0] += 1
        return "L%d" % label_counter[0]

    def operand_reg(op: Token, tmp: str = "x20") -> str:
        """操作数 → 所在寄存器名。立即数先 li 进临时寄存器。"""
        if op.kind == "int":
            lines.append("li %s, %s" % (tmp, op.value))
            return tmp
        if op.kind == "reg":
            return "x%d" % int(op.value[1:])
        if op.kind == "cbit":
            return "x%d" % (10 + int(op.value[2:-1]))
        raise ValueError("bad operand: %r" % (op,))

    def emit_assign(stmt: Assign) -> None:
        dst = "x%d" % int(stmt.dst.value[1:])
        terms, ops = stmt.terms, stmt.ops
        if len(terms) == 1:
            # rN = 单一操作数
            if terms[0].kind == "int":
                lines.append("li %s, %s" % (dst, terms[0].value))
            else:
                # 寄存器拷贝：模拟器没有 mv，用 add rd, rs, x0 实现
                lines.append("add %s, %s, x0" % (dst, operand_reg(terms[0])))
            return
        op = ops[0].value  # '+' 或 '-'
        a, b = terms[0], terms[1]
        # 常量折叠：rN = 10 + 5 → li xN, 15（编译期就算完）
        if a.kind == "int" and b.kind == "int":
            v = int(a.value) + int(b.value) if op == "+" else int(a.value) - int(b.value)
            lines.append("li %s, %d" % (dst, v))
            return
        # 左操作数
        if a.kind == "int":
            lines.append("li x20, %s" % a.value)
            ra = "x20"
        else:
            ra = operand_reg(a)
        # 右操作数：立即数走 addi（减法则取负），寄存器走 add/sub
        if b.kind == "int":
            imm = int(b.value)
            lines.append("addi %s, %s, %d" % (dst, ra, imm if op == "+" else -imm))
        else:
            rb = operand_reg(b)
            lines.append("%s %s, %s, %s" % ("add" if op == "+" else "sub", dst, ra, rb))

    def emit_if(stmt: IfStmt) -> None:
        # 编译期常量条件（如 if (1 == 1)）：直接展开对应分支，不发指令
        if stmt.lhs.kind == "int" and stmt.rhs.kind == "int":
            a, b = int(stmt.lhs.value), int(stmt.rhs.value)
            is_true = (a == b) if stmt.cmp.value == "==" else (a != b)
            body = stmt.then_body if is_true else (stmt.else_body or [])
            for s in body:
                emit_stmt(s)
            return
        l_else, l_end = new_label(), new_label()
        ra = operand_reg(stmt.lhs)
        rb = operand_reg(stmt.rhs)
        # 分支反转：若条件为假则跳过 then 块
        branch = "bne" if stmt.cmp.value == "==" else "beq"
        target = l_else if stmt.else_body else l_end
        lines.append("%s %s, %s, %s" % (branch, ra, rb, target))
        for s in stmt.then_body:
            emit_stmt(s)
        if stmt.else_body:
            lines.append("j %s" % l_end)
            lines.append("%s:" % l_else)
            for s in stmt.else_body:
                emit_stmt(s)
        lines.append("%s:" % l_end)

    def emit_stmt(stmt) -> None:
        if isinstance(stmt, Assign):
            emit_assign(stmt)
        elif isinstance(stmt, IfStmt):
            emit_if(stmt)
        else:
            raise ValueError("unknown AST node: %r" % (stmt,))

    for stmt in ast:
        emit_stmt(stmt)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 自测：官方示例 + 嵌套/单行变体
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from riscv_emulator import TinyRISCVEmulator

    def run_check(qasm: str, injections: List[dict], expected: List[int]) -> None:
        qtext, ctext = split_hybrid(qasm)
        asm = compile_classical(ctext)
        print("--- quantum part ---")
        print(qtext.strip())
        print("--- assembly ---")
        print(asm)
        for inject, want in zip(injections, expected):
            emu = TinyRISCVEmulator()
            emu.load_program(asm)
            for reg, val in inject.items():
                emu.set_register(reg, val)
            state = emu.execute()
            got = state.get("x1")
            assert got == want, "x1=%r expected %r (state=%r)" % (got, want, state)
            print("%s -> x1=%d OK" % (inject, got))

    # 官方公开用例：单行 classical
    run_check(
        'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\ncreg c[1];\n'
        'measure q[0] -> c[0];\n'
        'classical { if (c[0] == 1) { r1 = 7; } else { r1 = 3; } }\n',
        [{"x10": 0}, {"x10": 1}], [3, 7],
    )
    # 官方示例（problem_statement）：多行 + else + 后续赋值
    run_check(
        'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\n'
        'h q[0];\nmeasure q[0] -> c[0];\n'
        'classical {\n'
        '  if (c[0] == 1) {\n    r1 = 100;\n  } else {\n    r1 = 10;\n  }\n'
        '  r1 = r1 + 5;\n}\n'
        'cx q[0], q[1];\n',
        [{"x10": 0}, {"x10": 1}], [15, 105],
    )
    # 嵌套 if + 双测量位 + 减法：c[0]=0→9-2=7；c[0]=1,c[1]=0→7-2=5；
    # c[0]=1,c[1]=1→5-2=3
    run_check(
        'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\n'
        'classical {\n'
        '  r1 = 0;\n'
        '  if (c[0] == 1) {\n'
        '    if (c[1] != 0) {\n      r1 = 5;\n    } else {\n      r1 = 7;\n    }\n'
        '  } else {\n    r1 = 9;\n  }\n'
        '  r1 = r1 - 2;\n}\n',
        [{"x10": 0, "x11": 0}, {"x10": 1, "x11": 0}, {"x10": 1, "x11": 1}],
        [7, 5, 3],
    )
    print("ALL SELF-TESTS PASSED")
