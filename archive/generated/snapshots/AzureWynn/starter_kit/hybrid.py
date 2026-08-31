#!/usr/bin/env python3
"""L3: Hybrid-QASM -> (quantum ops, RISC-V assembly).

The classical block is a mini-language on registers r1..r9 with integer
literals, +/-, if/else over measured bits c[k], and sequential assignment.
Measurement c[k] is mapped to RISC-V register x10+k; r1..r9 map to x1..x9.

compile_hybrid(source) -> (quantum_ops, assembly) where quantum_ops is the
ordered list of quantum gate/measure instructions and assembly runs on the
official TinyRISCVEmulator (li/add/sub/addi/beq/bne/j subset).
"""

import re
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# tokenizer / parser for the classical mini-language
# --------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"\s*(?:(?P<reg>r[1-9])|(?P<cbit>c\[\d+\])|(?P<int>-?\d+)|"
    r"(?P<op>==|!=|=|\+|-|\(|\)|\{|\}|;)|(?P<kw>if|else)|(?P<bad>\S))"
)


class _SyntaxError(ValueError):
    pass


class _Tokens:
    def __init__(self, source: str):
        self.items = []
        pos = 0
        while pos < len(source):
            m = _TOKEN_RE.match(source, pos)
            if not m or m.lastgroup == "bad":
                if not source[pos:].strip():
                    break
                raise _SyntaxError("unexpected token near: %r" % source[pos:pos + 12])
            if m.lastgroup == "reg":
                self.items.append(("reg", int(m.group("reg")[1:])))
            elif m.lastgroup == "cbit":
                self.items.append(("cbit", int(m.group("cbit")[2:-1])))
            elif m.lastgroup == "int":
                self.items.append(("int", int(m.group("int"))))
            else:
                self.items.append((m.lastgroup, m.group(m.lastgroup)))
            pos = m.end()
        self.pos = 0

    def peek(self):
        return self.items[self.pos] if self.pos < len(self.items) else (None, None)

    def next(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def expect(self, kind, value=None):
        tok = self.next()
        if tok[0] != kind or (value is not None and tok[1] != value):
            raise _SyntaxError("expected %r got %r" % (value or kind, tok))
        return tok

    def eof(self):
        return self.pos >= len(self.items)


def _parse_expr(tokens: _Tokens):
    """expr := term (('+'|'-') term)* ; term := int | reg"""
    tok = tokens.next()
    if tok[0] == "int":
        left: Any = ("int", tok[1])
    elif tok[0] == "reg":
        left = ("reg", tok[1])
    else:
        raise _SyntaxError("expected expression term, got %r" % (tok,))
    while tokens.peek()[0] == "op" and tokens.peek()[1] in ("+", "-"):
        op = tokens.next()[1]
        r = tokens.next()
        if r[0] == "int":
            right = ("int", r[1])
        elif r[0] == "reg":
            right = ("reg", r[1])
        else:
            raise _SyntaxError("expected term after %s" % op)
        left = ("binop", op, left, right)
    return left


def _parse_stmt(tokens: _Tokens) -> Any:
    tok = tokens.peek()
    if tok[0] == "kw" and tok[1] == "if":
        tokens.next()
        tokens.expect("op", "(")
        cbit = tokens.expect("cbit")[1]
        cmp_op = tokens.expect("op")[1]
        if cmp_op not in ("==", "!="):
            raise _SyntaxError("unsupported comparison %r" % cmp_op)
        value = tokens.expect("int")[1]
        tokens.expect("op", ")")
        then_branch = _parse_block(tokens)
        else_branch = []
        if tokens.peek() == ("kw", "else"):
            tokens.next()
            else_branch = _parse_block(tokens)
        return ("if", cbit, cmp_op, value, then_branch, else_branch)
    if tok[0] == "reg":
        tokens.next()
        tokens.expect("op", "=")
        expr = _parse_expr(tokens)
        tokens.expect("op", ";")
        return ("assign", tok[1], expr)
    raise _SyntaxError("expected statement, got %r" % (tok,))


def _parse_block(tokens: _Tokens) -> List[Any]:
    tokens.expect("op", "{")
    stmts = []
    while tokens.peek() != ("op", "}"):
        if tokens.eof():
            raise _SyntaxError("unterminated block")
        stmts.append(_parse_stmt(tokens))
    tokens.expect("op", "}")
    return stmts


def parse_classical(source: str) -> List[Any]:
    tokens = _Tokens(source)
    stmts = []
    while not tokens.eof():
        stmts.append(_parse_stmt(tokens))
    return stmts


# --------------------------------------------------------------------------
# reference interpreter (used for local verification mirroring the evaluator)
# --------------------------------------------------------------------------

def interpret_classical(ast: List[Any], cvalues: List[int]) -> Dict[int, int]:
    regs = {i: 0 for i in range(1, 10)}

    def value_of(expr):
        kind = expr[0]
        if kind == "int":
            return expr[1]
        if kind == "reg":
            return regs[expr[1]]
        if kind == "binop":
            _, op, l, r = expr
            lv, rv = value_of(l), value_of(r)
            return lv + rv if op == "+" else lv - rv
        raise _SyntaxError("bad expression %r" % (expr,))

    def run(stmts):
        for stmt in stmts:
            if stmt[0] == "assign":
                _, idx, expr = stmt
                regs[idx] = value_of(expr)
            else:
                _, cbit, cmp_op, value, then_branch, else_branch = stmt
                cond = cvalues[cbit] == value if cmp_op == "==" else cvalues[cbit] != value
                run(then_branch if cond else else_branch)

    run(ast)
    return regs


# --------------------------------------------------------------------------
# RISC-V code generation
# --------------------------------------------------------------------------

_SCRATCH = "x20"          # scratch register (c[k] uses x10..x19, r1..r9 use x1..x9)


def _reg_name(idx: int) -> str:
    return "x%d" % idx


def _emit_assign(reg_idx: int, expr) -> List[str]:
    out = []
    kind = expr[0]
    rd = _reg_name(reg_idx)
    if kind == "int":
        out.append("li %s, %d" % (rd, expr[1]))
    elif kind == "reg":
        out.append("add %s, %s, x0" % (rd, _reg_name(expr[1])))
    elif kind == "binop":
        _, op, left, right = expr
        lk, rk = left[0], right[0]
        if lk == "int" and rk == "reg":
            out.append("li %s, %d" % (_SCRATCH, left[1]))
            out.append("%s %s, %s, %s" % ("add" if op == "+" else "sub", rd, _SCRATCH, _reg_name(right[1])))
        elif lk == "reg" and rk == "int":
            imm = right[1]
            if op == "+":
                out.append("addi %s, %s, %d" % (rd, _reg_name(left[1]), imm))
            else:
                out.append("addi %s, %s, %d" % (rd, _reg_name(left[1]), -imm))
        elif lk == "reg" and rk == "reg":
            mnemonic = "add" if op == "+" else "sub"
            out.append("%s %s, %s, %s" % (mnemonic, rd, _reg_name(left[1]), _reg_name(right[1])))
        elif lk == "int" and rk == "int":
            out.append("li %s, %d" % (rd, left[1] + right[1] if op == "+" else left[1] - right[1]))
    else:
        raise _SyntaxError("bad expression %r" % (expr,))
    return out


def _compile_stmts(stmts: List[Any], out: List[str], label_counter: List[int]):
    for stmt in stmts:
        if stmt[0] == "assign":
            out.extend(_emit_assign(stmt[1], stmt[2]))
        else:
            _, cbit, cmp_op, value, then_branch, else_branch = stmt
            n = label_counter[0]
            label_counter[0] += 1
            else_lbl = "L%d_ELSE" % n
            end_lbl = "L%d_END" % n
            out.append("li %s, %d" % (_SCRATCH, value))
            out.append("%s %s, %s, %s" % ("bne" if cmp_op == "==" else "beq",
                                          _reg_name(10 + cbit), _SCRATCH, else_lbl))
            _compile_stmts(then_branch, out, label_counter)
            out.append("j %s" % end_lbl)
            out.append("%s:" % else_lbl)
            _compile_stmts(else_branch, out, label_counter)
            out.append("%s:" % end_lbl)


def compile_classical(ast: List[Any]) -> str:
    out: List[str] = []
    _compile_stmts(ast, out, [0])
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Hybrid-QASM splitting
# --------------------------------------------------------------------------

_CLASSICAL_RE = re.compile(r"classical\s*\{", re.IGNORECASE)


def split_hybrid(source: str) -> Tuple[str, str]:
    """Return (quantum_part, classical_body). Supports at most one classical block."""
    idx = _CLASSICAL_RE.search(source)
    if not idx:
        raise _SyntaxError("no classical block found")
    start = idx.end()
    depth, end = 1, -1
    i = start
    while i < len(source):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
        i += 1
    if end < 0:
        raise _SyntaxError("unterminated classical block")
    quantum = (source[:idx.start()] + source[end + 1:])
    body = source[start:end]
    return quantum, body


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def _canonical_quantum_ops(qasm_str: str) -> List[str]:
    """Parse the quantum part back into an ordered list of canonical ops."""
    try:
        from .qasm_parser import parse_qasm
    except ImportError:
        from qasm_parser import parse_qasm
    pc = parse_qasm(qasm_str)
    names = {"h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T", "tdg": "TDAG",
             "rz": "RZ", "ry": "RY", "cx": "CNOT", "cu1": "CU1",
             "swap": "SWAP", "ccx": "TOFFOLI"}
    ops = []
    for gate, params, qubits in pc.ops:
        head = names[gate]
        if params:
            head += "(" + ",".join("%g" % p for p in params) + ")"
        ops.append("%s q[%s]" % (head, ", q[".join(str(q) for q in qubits)))
    ops.extend("MEASURE q[%d], c[%d]" % (q, c) for q, c in pc.measures)
    return ops


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    quantum, body = split_hybrid(hybrid_qasm_str)
    ast = parse_classical(body)
    assembly = compile_classical(ast)
    quantum_ops = _canonical_quantum_ops(quantum)
    return quantum_ops, assembly