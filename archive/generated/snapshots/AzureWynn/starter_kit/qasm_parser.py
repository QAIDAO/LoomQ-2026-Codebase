#!/usr/bin/env python3
"""OpenQASM 2.0 whitelist-subset parser shared by all backends.

The evaluator only ever feeds the 12 whitelist gates, but the parser is also
used by the L2 agent's self-verification loop, so it tolerates common QASM
spelling variants (uppercase gate names, whitespace, comments).
"""

import ast
import math
import operator
import re
from dataclasses import dataclass
from typing import List, Tuple

# whitelist gate -> (qubit count, has parameter)
GATE_ARITY = {
    "h": (1, False), "x": (1, False), "s": (1, False), "sdg": (1, False),
    "t": (1, False), "tdg": (1, False), "rz": (1, True), "ry": (1, True),
    "cx": (2, False), "cu1": (2, True), "swap": (2, False), "ccx": (3, False),
}

_ALLOWED_BINOP = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
}
_ALLOWED_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


@dataclass
class ParsedCircuit:
    nq: int
    nc: int
    ops: List[Tuple[str, List[float], List[int]]]   # (gate, params, qubit indices)
    measures: List[Tuple[int, int]]                  # (qubit, clbit)


def eval_param(expr: str) -> float:
    """Safely evaluate a QASM real expression (pi, numbers, + - * /, parens)."""
    node = ast.parse(expr.strip(), mode="eval").body

    def _eval(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.Name) and n.id == "pi":
            return math.pi
        if isinstance(n, ast.BinOp) and type(n.op) in _ALLOWED_BINOP:
            return _ALLOWED_BINOP[type(n.op)](_eval(n.left), _eval(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _ALLOWED_UNARY:
            return _ALLOWED_UNARY[type(n.op)](_eval(n.operand))
        raise ValueError("unsupported expression: %r" % expr)

    return _eval(node)


def fmt_param(p: float) -> str:
    """Format a gate parameter compactly (pi fractions when exact, else decimal)."""
    if abs(p) < 1e-12:
        return "0"
    q = p / math.pi
    if abs(q - round(q)) < 1e-9:
        n = int(round(q))
        return "pi" if n == 1 else "-pi" if n == -1 else "%d*pi" % n
    for den in (2, 3, 4, 6, 8):
        num = q * den
        if abs(num - round(num)) < 1e-9:
            n = int(round(num))
            head = "" if n == 1 else ("-" if n == -1 else "%d*" % n)
            return "%spi/%d" % (head, den)
    return "%.10g" % p


def fmt_decimal(p: float) -> str:
    """Decimal-only formatting for IRs whose parsers may not take expressions."""
    if abs(p) < 1e-12:
        return "0"
    return "%.10g" % p


def _strip_comments(text: str) -> List[str]:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    lines = []
    for line in text.splitlines():
        idx = line.find("//")
        if idx >= 0:
            line = line[:idx]
        if line.strip():
            lines.append(line.strip())
    return lines


_GATE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*(?:\((.*?)\))?\s*(.*?)\s*$")
_QREG_RE = re.compile(r"^qreg\s+q\s*\[\s*(\d+)\s*\]\s*")
_CREG_RE = re.compile(r"^creg\s+c\s*\[\s*(\d+)\s*\]\s*")
_MEAS_BIT_RE = re.compile(r"^measure\s+q\s*\[\s*(\d+)\s*\]\s*->\s*c\s*\[\s*(\d+)\s*\]\s*")
_MEAS_REG_RE = re.compile(r"^measure\s+q\s*->\s*c\s*")


def parse_qasm(qasm_str: str) -> ParsedCircuit:
    """Parse the OpenQASM 2.0 whitelist subset into a structured circuit."""
    nq = nc = 0
    ops: List[Tuple[str, List[float], List[int]]] = []
    measures: List[Tuple[int, int]] = []

    for raw in _strip_comments(qasm_str):
        line = raw.rstrip(";")
        if not line:
            continue
        m = _QREG_RE.match(line)
        if m:
            nq = int(m.group(1))
            continue
        m = _CREG_RE.match(line)
        if m:
            nc = int(m.group(1))
            continue
        m = _MEAS_BIT_RE.match(line)
        if m:
            measures.append((int(m.group(1)), int(m.group(2))))
            continue
        m = _MEAS_REG_RE.match(line)
        if m:
            for i in range(nq):
                measures.append((i, i))
            continue
        if line.startswith("OPENQASM") or line.startswith("include"):
            continue
        m = _GATE_RE.match(line)
        if m:
            name = m.group(1).lower()
            if name not in GATE_ARITY:
                raise ValueError("unsupported gate: %s" % name)
            params = [eval_param(p) for p in re.split(r",", m.group(2))] if m.group(2) else []
            args = [a.strip() for a in re.split(r",", m.group(3)) if a.strip()]
            qubits = []
            for a in args:
                qm = re.match(r"^q\s*\[\s*(\d+)\s*\]$", a)
                if not qm:
                    raise ValueError("unexpected gate argument: %r" % a)
                qubits.append(int(qm.group(1)))
            arity, has_param = GATE_ARITY[name]
            if len(qubits) != arity:
                raise ValueError("%s expects %d qubits, got %d" % (name, arity, len(qubits)))
            if has_param and len(params) != 1:
                raise ValueError("%s expects one parameter" % name)
            if not has_param and params:
                raise ValueError("%s takes no parameter" % name)
            ops.append((name, params, qubits))
            continue
        raise ValueError("cannot parse line: %r" % raw)

    if nq <= 0:
        raise ValueError("missing qreg declaration")
    if nc <= 0:
        raise ValueError("missing creg declaration")
    return ParsedCircuit(nq=nq, nc=nc, ops=ops, measures=measures)