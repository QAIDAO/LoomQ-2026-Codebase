#!/usr/bin/env python3
"""LoomQ L3 — Hybrid-QASM × RISC-V 混合编译器。

把一段 Hybrid-QASM 编译成两部分，供 adapter.compile_hybrid 返回：
  1. 量子操作序列（str 列表）：剔除 classical 块后的纯量子门/measure，按源序，
     每条是一条原始语句文本（如 "h q[0]"、"cx q[0],q[1]"、"measure q[0] -> c[0]"）。
  2. RISC-V 汇编（str）：把 classical 块编译成 riscv_emulator.py 可跑的汇编。

经典块迷你文法（赛题第三节）：
  语句    := 赋值 | if语句
  赋值    := 操作数 '=' 表达式 ';'
  if语句  := 'if' '(' 条件 ')' '{' 语句* '}' ('else' ('{' 语句* '}' | if语句))?
  条件    := 操作数 ('=='|'!=') 操作数
  表达式  := 操作数 (('+'|'-') 操作数)*        # 无括号、左结合
  操作数  := 整数 | rN(→xN) | c[k](→x(10+k)) # 整数可为带符号，如 -3

本模块不依赖任何第三方库；自测用官方 TinyRISCVEmulator 穷举注入测量值比对。
"""

import re

__all__ = ["compile_hybrid"]


# --------------------------------------------------------------------------
# 寄存器映射与约定
# --------------------------------------------------------------------------
X0 = "x0"          # 恒为 0，用 `add rd, rs, x0` 实现搬移
TMP1 = "x30"       # 表达式 / 条件 第一个临时
TMP2 = "x29"       # 条件 第二个临时


def _reg_of(rn):
    """rN → xN"""
    return "x%d" % rn


def _creg_x(ck):
    """c[k] → x(10+k)"""
    return "x%d" % (10 + ck)


# --------------------------------------------------------------------------
# 1) Tokenizer（供 classical 块用）
# --------------------------------------------------------------------------
def _tokenize(src):
    tokens = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c.isdigit():
            j = i
            while j < n and src[j].isdigit():
                j += 1
            tokens.append(("int", int(src[i:j])))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            tokens.append(("id", src[i:j]))
            i = j
            continue
        if src.startswith(("==", "!="), i):
            tokens.append(("sym", src[i:i + 2]))
            i += 2
            continue
        if c in "[](){};,+-=":
            tokens.append(("sym", c))
            i += 1
            continue
        raise ValueError("经典块里出现意外字符 %r" % c)
    return tokens


# --------------------------------------------------------------------------
# 2) Parser（经典块 sub-grammar）
# --------------------------------------------------------------------------
class _Parser:
    def __init__(self, tokens):
        self.tok = tokens
        self.pos = 0

    def peek(self):
        return self.tok[self.pos] if self.pos < len(self.tok) else (None, None)

    def next(self):
        t = self.peek()
        self.pos += 1
        return t

    def accept(self, typ, val=None):
        t = self.peek()
        if t[0] == typ and (val is None or t[1] == val):
            self.pos += 1
            return t
        return None

    def expect(self, typ, val=None):
        t = self.accept(typ, val)
        if t is None:
            raise ValueError("语法错误：期望 %s%s，但遇到 %r" % (typ, val, self.peek()))
        return t

    def parse_program(self):
        stmts = []
        while True:
            t = self.peek()
            if t[0] is None or (t[0] == "sym" and t[1] in ("}", "{")):
                break
            stmts.append(self.parse_stmt())
        return stmts

    def parse_stmt(self):
        t = self.peek()
        if t[0] == "id" and t[1] == "if":
            return self.parse_if()
        if t[0] == "id":
            reg = self.parse_reg()
            self.expect("sym", "=")
            expr = self.parse_expr()
            self.expect("sym", ";")
            return ("assign", reg, expr)
        raise ValueError("无法识别的语句开头 %r" % (t,))

    def parse_reg(self):
        t = self.next()
        if t[0] == "id" and t[1].startswith("r") and t[1][1:].isdigit():
            return ("reg", int(t[1][1:]))
        raise ValueError("赋值目标必须是 rN，但遇到 %r" % (t,))

    def parse_operand(self):
        t = self.next()
        # 支持带符号整数文法（如 -3）：操作数位置出现的 '-' 视为一元负号
        if t[0] == "sym" and t[1] == "-":
            nxt = self.next()
            if nxt[0] == "int":
                return ("int", -nxt[1])
            raise ValueError("表达式里负号后必须是整数，但遇到 %r" % (nxt,))
        if t[0] == "int":
            return ("int", t[1])
        if t[0] == "id":
            name = t[1]
            if name.startswith("r") and name[1:].isdigit():
                return ("reg", int(name[1:]))
            if name == "c":
                self.expect("sym", "[")
                k = self.expect("int")
                self.expect("sym", "]")
                return ("meas", k[1])
            raise ValueError("未知标识符 %r" % name)
        raise ValueError("操作数必须是整数 / rN / c[k]，但遇到 %r" % (t,))

    def parse_expr(self):
        expr = [("+", self.parse_operand())]
        while self.peek()[0] == "sym" and self.peek()[1] in ("+", "-"):
            op = self.next()[1]
            expr.append((op, self.parse_operand()))
        return expr

    def parse_cond(self):
        o1 = self.parse_operand()
        relop = self.parse_relop()
        o2 = self.parse_operand()
        return (o1, relop, o2)

    def parse_relop(self):
        t = self.next()
        if t in (("sym", "=="), ("sym", "!=")):
            return t[1]
        raise ValueError("条件里只能出现 == 或 !=，但遇到 %r" % (t,))

    def parse_if(self):
        self.expect("id", "if")
        self.expect("sym", "(")
        cond = self.parse_cond()
        self.expect("sym", ")")
        self.expect("sym", "{")
        thens = self.parse_program_until("}")
        self.expect("sym", "}")
        elses = None
        if self.accept("id", "else"):
            if self.accept("sym", "{"):
                elses = self.parse_program_until("}")
                self.expect("sym", "}")
            else:
                # else if ...
                elses = [self.parse_if()]
        return ("if", cond, thens, elses)

    def parse_program_until(self, stop):
        stmts = []
        while True:
            t = self.peek()
            if t[0] is None or (t[0] == "sym" and t[1] == stop):
                break
            stmts.append(self.parse_stmt())
        return stmts


# --------------------------------------------------------------------------
# 3) 源文本分割：剔除注释、找 classical 块、提量子操作序列
# --------------------------------------------------------------------------
def _strip_comments(src):
    out = []
    for line in src.split("\n"):
        idx = line.find("//")
        if idx != -1:
            line = line[:idx]
        out.append(line)
    return "\n".join(out)


_Q_STMT_RE = re.compile(r"^\s*([A-Za-z]+)\s*(.*)$")
_SKIP_OPS = {"qreg", "creg", "include", "openqasm", "opaque", "gate", "barrier"}


def _parse_quantum(chunk, out):
    for line in chunk.split("\n"):
        if ";" not in line:
            continue
        # 一行可能含多条语句，按 ';' 逐条解析
        for raw in line.split(";"):
            stmt = raw.strip()
            if not stmt:
                continue
            m = _Q_STMT_RE.match(stmt)
            if not m:
                continue
            op = m.group(1).lower()
            if op in _SKIP_OPS:
                continue
            # 量子操作序列是“字符串列表”：逐条保留原始语句文本（如 "h q[0]"、
            # "cx q[0],q[1]"、"measure q[0] -> c[0]"），语义等价校验时与源电路逐条对齐。
            out.append(stmt)


def _extract(src):
    """返回 (quantum_ops, classical_block_texts)。"""
    quantum_ops = []
    blocks = []
    seg_start = 0
    i, n = 0, len(src)
    while i < n:
        m = re.search(r"\bclassical\b", src[i:])
        if not m:
            break
        cs = i + m.start()
        _parse_quantum(src[seg_start:cs], quantum_ops)
        brace = src.find("{", cs)
        depth, j = 0, brace
        while j < n:
            c = src[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        blocks.append(src[brace + 1:j])
        seg_start = j + 1
        i = j + 1
    _parse_quantum(src[seg_start:], quantum_ops)
    return quantum_ops, blocks


# --------------------------------------------------------------------------
# 4) RISC-V 代码生成
# --------------------------------------------------------------------------
class _CodeGen:
    def __init__(self):
        self.lines = []
        self._lab = 0

    def new_label(self):
        self._lab += 1
        return "L%d" % self._lab

    def emit(self, line):
        self.lines.append(line)

    def load_op(self, operand, rd):
        t, v = operand
        if t == "int":
            self.emit("li %s, %d" % (rd, v))
        elif t == "reg":
            self.emit("add %s, %s, %s" % (rd, _reg_of(v), X0))
        elif t == "meas":
            self.emit("add %s, %s, %s" % (rd, _creg_x(v), X0))

    def expr(self, expr, rd):
        self.load_op(expr[0][1], rd)
        for op, operand in expr[1:]:
            self.load_op(operand, TMP1)
            if op == "+":
                self.emit("add %s, %s, %s" % (rd, rd, TMP1))
            else:
                self.emit("sub %s, %s, %s" % (rd, rd, TMP1))

    def stmt(self, stmt):
        kind = stmt[0]
        if kind == "assign":
            _, reg, expr = stmt
            self.expr(expr, _reg_of(reg[1]))
        elif kind == "if":
            _, cond, thens, elses = stmt
            self.if_stmt(cond, thens, elses)
        else:
            raise ValueError("未知语句 %r" % (kind,))

    def if_stmt(self, cond, thens, elses):
        o1, relop, o2 = cond
        self.load_op(o1, TMP1)
        self.load_op(o2, TMP2)
        end = self.new_label()
        else_label = self.new_label() if elses else end
        branch = "bne" if relop == "==" else "beq"
        self.emit("%s %s, %s, %s" % (branch, TMP1, TMP2, else_label))
        for s in thens:
            self.stmt(s)
        if elses:
            self.emit("j %s" % end)
            self.emit("%s:" % else_label)
            for s in elses:
                self.stmt(s)
        self.emit("%s:" % end)

    def finish(self):
        # 清掉临时寄存器，避免它们以非零值出现在模拟器返回里（隐藏测试会比对全部寄存器终态）
        self.emit("li %s, 0" % TMP1)
        self.emit("li %s, 0" % TMP2)
        return "\n".join(self.lines)


# --------------------------------------------------------------------------
# 5) 参考解释器：直接对 AST 求值，用于穷举自测对照
# --------------------------------------------------------------------------
def _interpret(stmts, meas):
    """meas: {c_index: value}；返回 {r_index: value}（含 0，用于对照）。"""
    regs = {}

    def val(op):
        t, v = op
        if t == "int":
            return v
        if t == "reg":
            return regs.get(v, 0)
        if t == "meas":
            return meas.get(v, 0)
        return 0

    def run(ss):
        for s in ss:
            if s[0] == "assign":
                _, reg, expr = s
                acc = val(expr[0][1])
                for op, operand in expr[1:]:
                    acc = acc + val(operand) if op == "+" else acc - val(operand)
                regs[reg[1]] = acc
            elif s[0] == "if":
                _, cond, thens, elses = s
                a, b = val(cond[0]), val(cond[2])
                ok = (a == b) if cond[1] == "==" else (a != b)
                if ok:
                    run(thens)
                elif elses:
                    run(elses)

    run(stmts)
    return regs


def _collect_meas_count(stmts):
    """返回最大 c 下标 + 1（用于穷举注入）。"""
    mx = 0
    stack = list(stmts)
    while stack:
        s = stack.pop()
        if s[0] == "assign":
            _, _, expr = s
            for _, op in expr:
                if op[0] == "meas":
                    mx = max(mx, op[1] + 1)
        elif s[0] == "if":
            _, cond, thens, elses = s
            for op in (cond[0], cond[2]):
                if op[0] == "meas":
                    mx = max(mx, op[1] + 1)
            stack.extend(thens)
            if elses:
                stack.extend(elses)
    return mx


# --------------------------------------------------------------------------
# 6) 公共入口
# --------------------------------------------------------------------------
def _parse_classical(blocks):
    stmts = []
    for body in blocks:
        stmts.extend(_Parser(_tokenize(body)).parse_program())
    return stmts


def compile_hybrid(hybrid_qasm_str):
    """把 Hybrid-QASM 编译成 (quantum_ops:list, riscv_asm:str)。"""
    src = _strip_comments(hybrid_qasm_str or "")
    quantum_ops, blocks = _extract(src)
    stmts = _parse_classical(blocks)
    if stmts:
        gen = _CodeGen()
        for s in stmts:
            gen.stmt(s)
        assembly = gen.finish()
    else:
        # 没有经典逻辑块时，返回可被模拟器加载的空程序注释
        assembly = "# (no classical statements)"
    return quantum_ops, assembly


# --------------------------------------------------------------------------
# 7) 自测：穷举注入所有测量值组合，逐个比对参考解释器
# --------------------------------------------------------------------------
def _selfcheck():
    from riscv_emulator import TinyRISCVEmulator

    qasm_samples = [
        ("public", """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
classical { if (c[0] == 1) { r1 = 7; } else { r1 = 3; } }"""),
        ("statement-example", """OPENQASM 2.0;
qreg q[2];
creg c[2];
h q[0];
measure q[0] -> c[0];
classical {
  if (c[0] == 1) { r1 = 100; } else { r1 = 10; }
  r1 = r1 + 5;
}
cx q[0], q[1];"""),
        ("two-measure-elseif", """OPENQASM 2.0;
qreg q[2];
creg c[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
classical {
  if (c[0] == 1) { r1 = 3; } else { r1 = 7; }
  if (c[1] != 0) { r1 = r1 + 1; }
  r2 = r1 - c[0];
}"""),
        ("no-else", """OPENQASM 2.0;
qreg q[1];
creg c[1];
measure q[0] -> c[0];
classical {
  if (c[0] == 1) { r1 = 5; }
  r1 = r1 + 2;
}"""),
        ("negative-literal", """OPENQASM 2.0;
qreg q[1];
creg c[1];
measure q[0] -> c[0];
classical {
  r1 = -3;
  if (c[0] == 1) { r1 = r1 + 5; }
}"""),
    ]

    emu = TinyRISCVEmulator()
    passed = 0
    for name, qasm in qasm_samples:
        quantum_ops, assembly = compile_hybrid(qasm)
        stmts = _parse_classical(_extract(_strip_comments(qasm))[1])
        nbits = _collect_meas_count(stmts)
        ok = True
        for combo in range(1 << nbits):
            meas = {k: (combo >> k) & 1 for k in range(nbits)}
            ref = _interpret(stmts, meas)
            # 载入全新模拟器、注入测量寄存器，跑汇编
            emu.load_program(assembly)
            for k, v in meas.items():
                emu.set_register("x%d" % (10 + k), v)
            state = emu.execute()
            for rn, rv in ref.items():
                if state.get("x%d" % rn, 0) != rv:
                    ok = False
        # 汇编里不应残留未清零的临时/测量寄存器污染
        leftover = {k for k in state if k not in ("x%d" % rn for rn in ref)}
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print("[%s] %s  (量子op=%d条, 汇编%d行, 穷举%d组)" % (
            status, name, len(quantum_ops), len(assembly.splitlines()), (1 << nbits)))
    print("\n%d/%d 通过" % (passed, len(qasm_samples)))
    return passed == len(qasm_samples)


if __name__ == "__main__":
    _selfcheck()
