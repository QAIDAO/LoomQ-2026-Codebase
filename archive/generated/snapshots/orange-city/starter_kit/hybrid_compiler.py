"""Hybrid-QASM → (quantum ops, RISC-V) compiler for L3."""

from __future__ import annotations

import re
from typing import List, Tuple

try:
    from qasm_engine import parse_qasm
except ImportError:
    from starter_kit.qasm_engine import parse_qasm


def _extract_classical_block(source: str) -> str:
    match = re.search(r"classical\s*\{", source, re.IGNORECASE)
    if not match:
        return ""
    start = source.find("{", match.start())
    depth = 0
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1 : i]
    return ""


def _tokenize(text: str) -> List[str]:
    spec = [
        ("IF", r"if\b"),
        ("ELSE", r"else\b"),
        ("CREG", r"c\[\d+\]"),
        ("REG", r"r[1-9]\b"),
        ("EQ", r"=="),
        ("NE", r"!="),
        ("NUM", r"-?\d+"),
        ("LP", r"\("),
        ("RP", r"\)"),
        ("LB", r"\{"),
        ("RB", r"\}"),
        ("SEMI", r";"),
        ("PLUS", r"\+"),
        ("MINUS", r"-"),
        ("EQSIGN", r"="),
        ("SKIP", r"\s+"),
        ("MISMATCH", r"."),
    ]
    regex = re.compile("|".join("(?P<%s>%s)" % pair for pair in spec))
    tokens: List[str] = []
    for mo in regex.finditer(text):
        kind = mo.lastgroup
        value = mo.group()
        if kind == "SKIP":
            continue
        if kind == "MISMATCH":
            raise ValueError("unsupported classical token: %r" % value)
        tokens.append(value)
    return tokens


class _Compiler:
    def __init__(self) -> None:
        self.lines: List[str] = []
        self.counter = 0
        self.tokens: List[str] = []
        self.pos = 0

    def fresh(self, prefix: str) -> str:
        self.counter += 1
        return "%s_%d" % (prefix, self.counter)

    def peek(self) -> str:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ""

    def take(self, expected: str | None = None) -> str:
        if self.pos >= len(self.tokens):
            raise ValueError("unexpected end of classical block")
        tok = self.tokens[self.pos]
        if expected is not None and tok != expected:
            raise ValueError("expected %r, got %r" % (expected, tok))
        self.pos += 1
        return tok

    def xreg(self, token: str) -> str:
        if token.startswith("r"):
            return "x%s" % token[1:]
        match = re.fullmatch(r"c\[(\d+)\]", token)
        if match:
            return "x%d" % (10 + int(match.group(1)))
        raise ValueError("not a register: %s" % token)

    def compile(self, block: str) -> str:
        self.tokens = _tokenize(block)
        self.pos = 0
        self.statements()
        return "\n".join(self.lines) + ("\n" if self.lines else "")

    def statements(self) -> None:
        while self.pos < len(self.tokens) and self.peek() != "}":
            self.statement()

    def statement(self) -> None:
        if self.peek() == "if":
            self.if_stmt()
            return
        self.assign_stmt()
        if self.peek() == ";":
            self.take(";")

    def if_stmt(self) -> None:
        self.take("if")
        self.take("(")
        left = self.take()
        op = self.take()
        if op not in {"==", "!="}:
            raise ValueError("unsupported comparison: %s" % op)
        right = self.take()
        self.take(")")
        then_label_else = self.fresh("else")
        end_label = self.fresh("endif")
        left_x = self.xreg(left) if left.startswith(("r", "c")) else None
        if left_x is None:
            raise ValueError("if condition left must be c[k] or rN")
        if re.fullmatch(r"-?\d+", right):
            tmp = "x31"
            self.lines.append("li %s, %s" % (tmp, right))
            right_x = tmp
        else:
            right_x = self.xreg(right)
        branch = "bne" if op == "==" else "beq"
        self.lines.append("%s %s, %s, %s" % (branch, left_x, right_x, then_label_else))
        self.take("{")
        self.statements()
        self.take("}")
        self.lines.append("j %s" % end_label)
        self.lines.append("%s:" % then_label_else)
        if self.peek() == "else":
            self.take("else")
            self.take("{")
            self.statements()
            self.take("}")
        self.lines.append("%s:" % end_label)

    def assign_stmt(self) -> None:
        dest = self.take()
        self.take("=")
        lhs = self.take()
        if self.peek() in {"+", "-"}:
            op = self.take()
            rhs = self.take()
            self.emit_binop(dest, lhs, op, rhs)
            return
        self.emit_move(dest, lhs)

    def emit_move(self, dest: str, src: str) -> None:
        xd = self.xreg(dest)
        if re.fullmatch(r"-?\d+", src):
            self.lines.append("li %s, %s" % (xd, src))
            return
        self.lines.append("addi %s, %s, 0" % (xd, self.xreg(src)))

    def emit_binop(self, dest: str, lhs: str, op: str, rhs: str) -> None:
        xd = self.xreg(dest)
        if re.fullmatch(r"-?\d+", lhs) and re.fullmatch(r"-?\d+", rhs):
            value = int(lhs) + int(rhs) if op == "+" else int(lhs) - int(rhs)
            self.lines.append("li %s, %d" % (xd, value))
            return
        if re.fullmatch(r"-?\d+", rhs):
            imm = int(rhs) if op == "+" else -int(rhs)
            self.lines.append("addi %s, %s, %d" % (xd, self.xreg(lhs), imm))
            return
        if re.fullmatch(r"-?\d+", lhs):
            self.lines.append("li x30, %s" % lhs)
            instr = "add" if op == "+" else "sub"
            self.lines.append("%s %s, x30, %s" % (instr, xd, self.xreg(rhs)))
            return
        instr = "add" if op == "+" else "sub"
        self.lines.append("%s %s, %s, %s" % (instr, xd, self.xreg(lhs), self.xreg(rhs)))


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    circuit = parse_qasm(hybrid_qasm_str)
    quantum_ops = ["%s %s %s" % (gate, qubits, params) for gate, qubits, params in circuit.gates]
    classical = _Compiler().compile(_extract_classical_block(hybrid_qasm_str))
    return quantum_ops, classical
