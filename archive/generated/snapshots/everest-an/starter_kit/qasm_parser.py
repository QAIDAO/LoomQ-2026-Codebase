"""OpenQASM 2.0 parser producing the LoomQ circuit IR.

Supports the 12-gate whitelist (h x s sdg t tdg rz ry cx cu1 swap ccx)
plus measure (whole-register and bit-wise), barrier, qreg/creg
declarations (multiple registers are merged into flat index spaces),
comments and blank lines. Unknown gates raise ValueError instead of being
silently dropped: a parser that hides inputs would make the transpiler
unsound.

Parameter expressions are evaluated with a small AST whitelist evaluator
(constants, pi, + - * / and unary minus only) - never Python's eval.
"""

import ast
import math
import re
from typing import Dict, List, Tuple

try:
    from .circuit_ir import Circuit, GateOp
except ImportError:  # standalone-module fallback (evaluator imports by path)
    from circuit_ir import Circuit, GateOp

# Canonical whitelist plus u1 (measurement-equivalent to rz as a standalone
# single-qubit gate; kept under its own name so codegens can pick the
# native spelling per target).
KNOWN_GATES = frozenset(
    {"h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx", "u1"}
)

_QREG_RE = re.compile(r"(qreg|creg)\s+(\w+)\s*\[\s*(\d+)\s*\]", re.IGNORECASE)
_GATE_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(([^)]*)\))?\s*(.*)$")
_QARG_RE = re.compile(r"(\w+)\s*\[\s*(\d+)\s*\]")
_MEASURE_RE = re.compile(
    r"measure\s+(\w+)(?:\[(\d+)\])?\s*->\s*(\w+)(?:\[(\d+)\])?", re.IGNORECASE
)


class QasmParseError(ValueError):
    """Raised when a QASM 2.0 statement cannot be parsed."""


def _eval_expr(expr: str) -> float:
    """Safely evaluate a QASM parameter expression (pi, numbers, + - * /)."""
    expr = expr.strip()
    if not expr:
        raise QasmParseError("empty parameter expression")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise QasmParseError("bad parameter expression %r" % expr) from exc

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id == "pi":
            return math.pi
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
        raise QasmParseError("unsupported expression %r" % expr)

    return ev(tree)


def _parse_qubit_args(text: str, base: Dict[str, int]) -> List[int]:
    """Parse ``q[0], q[1], ...`` into global qubit indices."""
    text = text.strip()
    if not text:
        raise QasmParseError("gate applied with no qubit arguments")
    qubits: List[int] = []
    for piece in text.split(","):
        piece = piece.strip()
        match = _QARG_RE.fullmatch(piece)
        if not match:
            raise QasmParseError("bad qubit argument %r" % piece)
        name, index = match.group(1), int(match.group(2))
        if name not in base:
            raise QasmParseError("unknown qubit register %r" % name)
        qubits.append(base[name] + index)
    return qubits


def parse_qasm2(text: str) -> Circuit:
    """Parse OpenQASM 2.0 text into a :class:`Circuit`."""
    q_bases: Dict[str, int] = {}
    c_bases: Dict[str, int] = {}
    q_sizes: Dict[str, int] = {}
    c_sizes: Dict[str, int] = {}
    num_qubits = 0
    num_cbits = 0
    ops: List[GateOp] = []
    measures: List[Tuple[int, int]] = []

    for raw_line in text.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        if ";" not in line:
            raise QasmParseError("missing ';' in statement: %r" % line)
        stmt = line.rsplit(";", 1)[0].strip()
        lower = stmt.lower()
        if lower.startswith("openqasm"):
            continue
        if lower.startswith("include"):
            continue
        if lower.startswith("barrier"):
            continue

        decl = _QREG_RE.fullmatch(stmt)
        if decl:
            kind, name, size = decl.group(1).lower(), decl.group(2), int(decl.group(3))
            if kind == "qreg":
                if name in q_bases:
                    raise QasmParseError("duplicate qreg %r" % name)
                q_bases[name] = num_qubits
                q_sizes[name] = size
                num_qubits += size
            else:
                if name in c_bases:
                    raise QasmParseError("duplicate creg %r" % name)
                c_bases[name] = num_cbits
                c_sizes[name] = size
                num_cbits += size
            continue

        measure = _MEASURE_RE.fullmatch(stmt)
        if measure:
            q_name, q_idx, c_name, c_idx = measure.groups()
            if q_idx is None and c_idx is None:
                # Whole-register measurement: sizes must match.
                if q_sizes.get(q_name) != c_sizes.get(c_name):
                    raise QasmParseError(
                        "register size mismatch in measure %r" % stmt
                    )
                for offset in range(q_sizes[q_name]):
                    measures.append(
                        (q_bases[q_name] + offset, c_bases[c_name] + offset)
                    )
            else:
                if q_idx is None or c_idx is None:
                    raise QasmParseError(
                        "mixed register/bit measurement %r" % stmt
                    )
                if q_name not in q_bases or c_name not in c_bases:
                    raise QasmParseError("unknown register in %r" % stmt)
                q_global = q_bases[q_name] + int(q_idx)
                c_global = c_bases[c_name] + int(c_idx)
                measures.append((q_global, c_global))
            continue

        gate = _GATE_RE.fullmatch(stmt)
        if not gate:
            raise QasmParseError("unparseable statement: %r" % stmt)
        name = gate.group(1).lower()
        if name not in KNOWN_GATES:
            raise QasmParseError("unsupported gate %r (whitelist: %s)" % (
                name, ", ".join(sorted(KNOWN_GATES))))
        params = [_eval_expr(p) for p in gate.group(2).split(",")] if gate.group(2) else []
        qubits = _parse_qubit_args(gate.group(3), q_bases)
        ops.append(GateOp(name=name, params=params, qubits=qubits))

    return Circuit(num_qubits=num_qubits, num_cbits=num_cbits, ops=ops, measures=measures)
