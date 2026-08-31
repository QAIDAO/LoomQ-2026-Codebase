"""L3：Hybrid-QASM 混合编译。

Hybrid-QASM = 普通 OpenQASM 2.0 + 一个内嵌的 `classical { ... }` 经典
控制块（语法定义见 problem_statement.md 第三节）。本模块具有两个功能：

1. 把 `classical { ... }` 这一段从源码里挖出来，剩下的就是纯 OpenQASM
   2.0: 直接复用 loomq/qasm.py 的 parse_qasm2() 和 loomq/targets/spinq.py
   的单行 emit 函数，得到"量子操作序列"，不需要再写一套平行的量子解析器。
2. 给挖出来的经典块写一个从"迷你语言"到 RISC-V 汇编的小编译器，output可以直接输入进官方 riscv_emulator.py 的 TinyRISCVEmulator 正确执行。

寄存器分配约定：
  - 用户变量 r1..r9   -> x1..x9   （可读写，唯一由经典块赋值的寄存器）
  - 测量结果 c[k]     -> x(10+k) （只读，评测器在 execute() 前注入）
  - 比较运算的临时寄存器 -> x30 / x31（编译器内部专用，固定复用）
"""

import itertools
import re
from typing import Iterator, List, Optional, Tuple

from .ir import GateOp, MeasureOp
from .qasm import parse_qasm2
from .targets.spinq import _EMIT as _SPINQ_EMIT

Operand = Tuple[str, int]  # ("lit", n) | ("reg", i) | ("c", k)
Expr = Tuple[Operand, List[Tuple[str, Operand]]]
Cond = Tuple[Operand, str, Operand]
Stmt = Tuple  # ("assign", reg_idx, Expr) | ("if", Cond, List[Stmt], Optional[List[Stmt]])


# ---------------------------------------------------------------------------
# 第一步：把 classical { ... } 从源码里挖出来
# ---------------------------------------------------------------------------

def _find_classical_block(source: str) -> Tuple[str, str]:
    """定位唯一的 `classical { ... }` 块，返回 (挖掉这段之后剩下的源码,
    大括号内部的原始文本)。跟 qasm.py 的 _iter_statements 一样，扫描时
    要跳过 `//` 注释里的花括号，避免误判嵌套深度。"""
    keyword = "classical"
    n = len(source)
    i = 0
    in_comment = False
    start = None
    while i < n:
        ch = source[i]
        if in_comment:
            if ch == "\n":
                in_comment = False
            i += 1
            continue
        if ch == "/" and source[i + 1 : i + 2] == "/":
            in_comment = True
            i += 2
            continue
        if source[i : i + len(keyword)] == keyword:
            before_ok = i == 0 or not (source[i - 1].isalnum() or source[i - 1] == "_")
            after = i + len(keyword)
            after_ok = after >= n or not (source[after].isalnum() or source[after] == "_")
            if before_ok and after_ok:
                start = i
                i = after
                break
        i += 1
    if start is None:
        raise ValueError("missing 'classical { ... }' block")

    while i < n and source[i].isspace():
        i += 1
    if i >= n or source[i] != "{":
        raise ValueError("expected '{' after 'classical'")
    brace_start = i

    depth = 0
    in_comment = False
    j = i
    end = None
    while j < n:
        ch = source[j]
        if in_comment:
            if ch == "\n":
                in_comment = False
            j += 1
            continue
        if ch == "/" and source[j + 1 : j + 2] == "/":
            in_comment = True
            j += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = j
                break
        j += 1
    if end is None:
        raise ValueError("unterminated 'classical { ... }' block")

    block_inner = source[brace_start + 1 : end]
    remainder = source[:start] + source[end + 1 :]
    return remainder, block_inner


def _quantum_ops(remainder_qasm: str) -> List[str]:
    """挖掉经典块之后剩下的就是纯 OpenQASM 2.0，直接复用 L1 的解析器和
    spinq 后端已有的单行 emit 函数（不含头部声明，只要每个操作一行）。"""
    circuit = parse_qasm2(remainder_qasm)
    return [_SPINQ_EMIT[type(op)](op) for op in circuit.ops]


# ---------------------------------------------------------------------------
# 第二步：经典块迷你语言——分词 + 递归下降解析
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"==|!=|[A-Za-z_]\w*|\d+|[{}()\[\];=+\-]")


def _tokenize(text: str) -> List[str]:
    text = re.sub(r"//.*", "", text)  # 经典块本身很小，直接整体去注释即可
    return _TOKEN_RE.findall(text)


def _register_index(tok: Optional[str]) -> int:
    if tok is None or not re.fullmatch(r"r[1-9]", tok):
        raise ValueError(f"expected assignment target r1..r9, got {tok!r}")
    return int(tok[1:])


class _ClassicalParser:
    """经典块迷你文法：整数字面量、寄存器变量 r1..r9、测量位 c[k]、
    运算符 + - == !=、if/else（else 可省略）、顺序赋值。"""

    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> Optional[str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _advance(self) -> Optional[str]:
        tok = self._peek()
        self.pos += 1
        return tok

    def _expect(self, expected: str) -> None:
        actual = self._advance()
        if actual != expected:
            raise ValueError(f"expected {expected!r}, got {actual!r}")

    def parse_program(self) -> List[Stmt]:
        stmts = self._parse_stmts()
        if self.pos != len(self.tokens):
            raise ValueError(f"trailing tokens: {self.tokens[self.pos:]}")
        return stmts

    def _parse_stmts(self) -> List[Stmt]:
        stmts = []
        while self._peek() not in (None, "}"):
            stmts.append(self._parse_stmt())
        return stmts

    def _parse_stmt(self) -> Stmt:
        if self._peek() == "if":
            return self._parse_if()
        return self._parse_assign()

    def _parse_assign(self) -> Stmt:
        reg_idx = _register_index(self._advance())
        self._expect("=")
        expr = self._parse_expr()
        self._expect(";")
        return ("assign", reg_idx, expr)

    def _parse_if(self) -> Stmt:
        self._expect("if")
        self._expect("(")
        cond = self._parse_cond()
        self._expect(")")
        self._expect("{")
        then_stmts = self._parse_stmts()
        self._expect("}")
        else_stmts = None
        if self._peek() == "else":
            self._advance()
            self._expect("{")
            else_stmts = self._parse_stmts()
            self._expect("}")
        return ("if", cond, then_stmts, else_stmts)

    def _parse_cond(self) -> Cond:
        lhs = self._parse_operand()
        op = self._advance()
        if op not in ("==", "!="):
            raise ValueError(f"expected '==' or '!=' in condition, got {op!r}")
        rhs = self._parse_operand()
        return (lhs, op, rhs)

    def _parse_expr(self) -> Expr:
        first = self._parse_operand()
        terms: List[Tuple[str, Operand]] = []
        while self._peek() in ("+", "-"):
            op = self._advance()
            terms.append((op, self._parse_operand()))
        return (first, terms)

    def _parse_operand(self) -> Operand:
        tok = self._advance()
        if tok == "-":
            nxt = self._advance()
            if nxt is None or not nxt.isdigit():
                raise ValueError("expected integer literal after unary '-'")
            return ("lit", -int(nxt))
        if tok is not None and tok.isdigit():
            return ("lit", int(tok))
        if tok == "c":
            self._expect("[")
            idx_tok = self._advance()
            if idx_tok is None or not idx_tok.isdigit():
                raise ValueError("expected integer index in 'c[...]'")
            self._expect("]")
            return ("c", int(idx_tok))
        if tok is not None and re.fullmatch(r"r[1-9]", tok):
            return ("reg", int(tok[1:]))
        raise ValueError(f"unrecognized operand: {tok!r}")


# ---------------------------------------------------------------------------
# 第三步：从 AST 生成 RISC-V 汇编（riscv_emulator.py 支持的 7 条指令子集）
# ---------------------------------------------------------------------------

def _operand_reg(operand: Operand) -> Optional[str]:
    """寄存器类操作数（r_i / c[k]）返回对应的 x 寄存器名；字面量返回
    None，调用方需要自己决定怎么把它物化成立即数。"""
    kind, value = operand
    if kind == "reg":
        return f"x{value}"
    if kind == "c":
        return f"x{10 + value}"
    return None


def _emit_expr(dest_reg: str, expr: Expr) -> List[str]:
    """直接把表达式结果原地累加进目标寄存器：先用第一个操作数给
    dest_reg 赋初值，再逐项 +/-。这个模拟器是严格顺序执行、没有流水线
    冒险，即使 dest_reg 本身也是某个操作数（例如 r1 = r1 + 5），先读出
    旧值再写回也是安全的，不需要额外的临时寄存器。"""
    lines = []
    first_ref = _operand_reg(expr[0])
    if first_ref is None:
        lines.append(f"li {dest_reg}, {expr[0][1]}")
    else:
        lines.append(f"add {dest_reg}, x0, {first_ref}")
    for op, operand in expr[1]:
        ref = _operand_reg(operand)
        if ref is None:
            value = operand[1] if op == "+" else -operand[1]
            lines.append(f"addi {dest_reg}, {dest_reg}, {value}")
        else:
            instr = "add" if op == "+" else "sub"
            lines.append(f"{instr} {dest_reg}, {dest_reg}, {ref}")
    return lines


def _emit_cond_setup(lhs: Operand, rhs: Operand) -> Tuple[str, str, List[str]]:
    """把条件两边都变成寄存器名，字面量就地物化进 x30/x31（比较运算的
    专用暂存区，跟 r1..r9、c[k] 各自的寄存器区间不会冲突）。"""
    lines: List[str] = []
    lref, rref = _operand_reg(lhs), _operand_reg(rhs)
    if lref is None and rref is None:
        lines.append(f"li x30, {lhs[1]}")
        lines.append(f"li x31, {rhs[1]}")
        return "x30", "x31", lines
    if lref is None:
        lines.append(f"li x31, {lhs[1]}")
        return "x31", rref, lines
    if rref is None:
        lines.append(f"li x31, {rhs[1]}")
        return lref, "x31", lines
    return lref, rref, lines


def _emit_stmts(stmts: List[Stmt], counter: Iterator[int]) -> List[str]:
    lines: List[str] = []
    for stmt in stmts:
        lines.extend(_emit_stmt(stmt, counter))
    return lines


def _emit_stmt(stmt: Stmt, counter: Iterator[int]) -> List[str]:
    if stmt[0] == "assign":
        _, reg_idx, expr = stmt
        return _emit_expr(f"x{reg_idx}", expr)

    _, (lhs, cmp_op, rhs), then_stmts, else_stmts = stmt
    lhs_reg, rhs_reg, lines = _emit_cond_setup(lhs, rhs)
    n = next(counter)
    skip_label = f"IF{n}_ELSE"
    branch = "bne" if cmp_op == "==" else "beq"
    lines.append(f"{branch} {lhs_reg}, {rhs_reg}, {skip_label}")
    lines.extend(_emit_stmts(then_stmts, counter))
    if else_stmts is not None:
        end_label = f"IF{n}_END"
        lines.append(f"j {end_label}")
        lines.append(f"{skip_label}:")
        lines.extend(_emit_stmts(else_stmts, counter))
        lines.append(f"{end_label}:")
    else:
        lines.append(f"{skip_label}:")
    return lines


def compile_classical(block_text: str) -> str:
    tokens = _tokenize(block_text)
    stmts = _ClassicalParser(tokens).parse_program()
    lines = _emit_stmts(stmts, itertools.count())
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 对外入口
# ---------------------------------------------------------------------------

def compile_program(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    remainder, block_text = _find_classical_block(hybrid_qasm_str)
    return _quantum_ops(remainder), compile_classical(block_text)
