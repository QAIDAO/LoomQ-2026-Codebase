"""Core OpenQASM parsing, target emission, and result handling for LoomQ L1."""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple


GATE_SIGNATURES = {
    "h": (0, 1), "x": (0, 1), "s": (0, 1), "sdg": (0, 1),
    "t": (0, 1), "tdg": (0, 1), "rz": (1, 1), "ry": (1, 1),
    "cx": (0, 2), "cu1": (1, 2), "swap": (0, 2), "ccx": (0, 3),
}


class QASMError(ValueError):
    """An input program violates the supported LoomQ QASM subset."""


@dataclass(frozen=True)
class BitRef:
    register: str
    index: int


@dataclass(frozen=True)
class Gate:
    name: str
    params: Tuple[float, ...]
    qubits: Tuple[BitRef, ...]


@dataclass(frozen=True)
class Measurement:
    qubit: BitRef
    classical: BitRef


@dataclass(frozen=True)
class Circuit:
    qregs: Tuple[Tuple[str, int], ...]
    cregs: Tuple[Tuple[str, int], ...]
    gates: Tuple[Gate, ...]
    measurements: Tuple[Measurement, ...]

    @property
    def qubit_count(self) -> int:
        return sum(size for _, size in self.qregs)

    @property
    def classical_count(self) -> int:
        return sum(size for _, size in self.cregs)


_DECL_RE = re.compile(r"^(qreg|creg)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$", re.I)
_REF_RE = re.compile(r"^([A-Za-z_]\w*)\s*(?:\[\s*(\d+)\s*\])?$")
_GATE_RE = re.compile(r"^([A-Za-z_]\w*)\s*(?:\((.*)\))?\s+(.+)$", re.S)


def _error(kind: str, statement: str, detail: str) -> QASMError:
    return QASMError("%s in statement %r: %s" % (kind, statement.strip(), detail))


def _eval_angle(source: str, statement: str) -> float:
    try:
        tree = ast.parse(source.strip(), mode="eval")
    except SyntaxError as exc:
        raise _error("invalid parameter", statement, source) from exc

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id == "pi":
            return math.pi
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            return left / right
        raise _error("unsupported parameter", statement, source)

    try:
        value = visit(tree)
    except (ZeroDivisionError, OverflowError) as exc:
        raise _error("invalid parameter", statement, source) from exc
    if not math.isfinite(value):
        raise _error("invalid parameter", statement, "angle must be finite")
    return value


def _split_csv(source: str) -> List[str]:
    items, start, depth = [], 0, 0
    for index, char in enumerate(source):
        if char == "(": depth += 1
        elif char == ")": depth -= 1
        elif char == "," and depth == 0:
            items.append(source[start:index].strip()); start = index + 1
    items.append(source[start:].strip())
    return items


def parse_qasm(source: str) -> Circuit:
    if not isinstance(source, str):
        raise QASMError("QASM input must be text")
    cleaned = re.sub(r"//[^\r\n]*", "", source)
    statements = [item.strip() for item in cleaned.split(";") if item.strip()]
    if not statements or not re.fullmatch(r"OPENQASM\s+2\.0", statements[0], re.I):
        raise QASMError("missing or invalid OPENQASM 2.0 declaration")
    qregs: Dict[str, int] = {}
    cregs: Dict[str, int] = {}
    gates: List[Gate] = []
    measurements: List[Measurement] = []

    def refs(token: str, registers: Mapping[str, int], statement: str) -> List[BitRef]:
        match = _REF_RE.fullmatch(token.strip())
        if not match or match.group(1) not in registers:
            raise _error("invalid register reference", statement, token)
        name, raw_index = match.groups()
        if raw_index is None:
            return [BitRef(name, index) for index in range(registers[name])]
        index = int(raw_index)
        if index >= registers[name]:
            raise _error("register index out of range", statement, token)
        return [BitRef(name, index)]

    for statement in statements[1:]:
        if re.fullmatch(r'include\s+"qelib1\.inc"', statement, re.I):
            continue
        declaration = _DECL_RE.fullmatch(statement)
        if declaration:
            kind, name, raw_size = declaration.groups()
            if name in qregs or name in cregs:
                raise _error("duplicate declaration", statement, name)
            size = int(raw_size)
            if size <= 0:
                raise _error("invalid declaration", statement, "size must be positive")
            (qregs if kind.lower() == "qreg" else cregs)[name] = size
            continue
        measurement = re.fullmatch(r"measure\s+(.+?)\s*->\s*(.+)", statement, re.I | re.S)
        if measurement:
            left = refs(measurement.group(1), qregs, statement)
            right = refs(measurement.group(2), cregs, statement)
            if len(left) != len(right):
                raise _error("measurement width mismatch", statement, "quantum and classical widths differ")
            measurements.extend(Measurement(q, c) for q, c in zip(left, right))
            continue
        gate_match = _GATE_RE.fullmatch(statement)
        if not gate_match:
            raise _error("unsupported syntax", statement, "expected declaration, gate, or measurement")
        name, raw_params, raw_operands = gate_match.groups()
        name = name.lower()
        if name not in GATE_SIGNATURES:
            raise _error("unsupported gate", statement, name)
        expected_params, expected_qubits = GATE_SIGNATURES[name]
        param_tokens = [] if raw_params is None else _split_csv(raw_params)
        if len(param_tokens) != expected_params:
            raise _error("wrong parameter count", statement, name)
        operand_groups = [refs(item, qregs, statement) for item in _split_csv(raw_operands)]
        if len(operand_groups) != expected_qubits:
            raise _error("wrong qubit count", statement, name)
        width = max(len(group) for group in operand_groups)
        if any(len(group) not in (1, width) for group in operand_groups):
            raise _error("register width mismatch", statement, name)
        params = tuple(_eval_angle(item, statement) for item in param_tokens)
        for offset in range(width):
            qubits = tuple(group[0] if len(group) == 1 else group[offset] for group in operand_groups)
            if len(set(qubits)) != len(qubits):
                raise _error("duplicate gate operand", statement, name)
            gates.append(Gate(name, params, qubits))
    return Circuit(tuple(qregs.items()), tuple(cregs.items()), tuple(gates), tuple(measurements))


def _angle(value: float) -> str:
    text = format(value, ".17g")
    return "0" if text == "-0" else text


def _ref(bit: BitRef) -> str:
    return "%s[%d]" % (bit.register, bit.index)


def emit_spinq(circuit: Circuit) -> str:
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";']
    lines += ["qreg %s[%d];" % item for item in circuit.qregs]
    lines += ["creg %s[%d];" % item for item in circuit.cregs]
    for gate in circuit.gates:
        params = "(" + ",".join(_angle(x) for x in gate.params) + ")" if gate.params else ""
        lines.append("%s%s %s;" % (gate.name, params, ",".join(map(_ref, gate.qubits))))
    lines += ["measure %s -> %s;" % (_ref(item.qubit), _ref(item.classical)) for item in circuit.measurements]
    return "\n".join(lines) + "\n"


def emit_originq(circuit: Circuit) -> str:
    qoffset, coffset, total = {}, {}, 0
    for name, size in circuit.qregs:
        qoffset[name], total = total, total + size
    ctotal = 0
    for name, size in circuit.cregs:
        coffset[name], ctotal = ctotal, ctotal + size
    q = lambda bit: "q[%d]" % (qoffset[bit.register] + bit.index)
    c = lambda bit: "c[%d]" % (coffset[bit.register] + bit.index)
    names = {"cx": "CNOT", "swap": "SWAP", "ccx": "TOFFOLI", "cu1": "CR"}
    lines = ["QINIT %d" % total, "CREG %d" % ctotal]
    for gate in circuit.gates:
        if gate.name in {"sdg", "tdg"}:
            angle = -math.pi / (2 if gate.name == "sdg" else 4)
            lines.append("RZ %s,(%s)" % (q(gate.qubits[0]), _angle(angle)))
            continue
        name = names.get(gate.name, gate.name.upper())
        operands = ", ".join(q(bit) for bit in gate.qubits)
        if gate.params:
            lines.append(
                "%s %s,(%s)"
                % (name, operands, ",".join(_angle(x) for x in gate.params))
            )
        else:
            lines.append("%s %s" % (name, operands))
    lines += ["MEASURE %s, %s" % (q(item.qubit), c(item.classical)) for item in circuit.measurements]
    return "\n".join(lines) + "\n"


def emit_braket(circuit: Circuit) -> str:
    qoffset, coffset, total = {}, {}, 0
    for name, size in circuit.qregs:
        qoffset[name], total = total, total + size
    ctotal = 0
    for name, size in circuit.cregs:
        coffset[name], ctotal = ctotal, ctotal + size
    q = lambda bit: "q[%d]" % (qoffset[bit.register] + bit.index)
    c = lambda bit: "c[%d]" % (coffset[bit.register] + bit.index)
    lines = ['OPENQASM 3.0;', 'include "stdgates.inc";', "qubit[%d] q;" % total, "bit[%d] c;" % ctotal]
    for gate in circuit.gates:
        name = {"cx": "cnot", "cu1": "cp"}.get(gate.name, gate.name)
        params = "(" + ",".join(_angle(x) for x in gate.params) + ")" if gate.params else ""
        lines.append("%s%s %s;" % (name, params, ", ".join(q(bit) for bit in gate.qubits)))
    lines += ["%s = measure %s;" % (c(item.classical), q(item.qubit)) for item in circuit.measurements]
    return "\n".join(lines) + "\n"


EMITTERS = {"spinq": emit_spinq, "originq": emit_originq, "braket": emit_braket}


def transpile(source: str, target: str) -> str:
    if target not in EMITTERS:
        raise ValueError("unsupported L1 target: %s" % target)
    return EMITTERS[target](parse_qasm(source))


def normalize_counts(raw: Mapping[Any, Any], shots: int, width: int) -> Dict[str, int]:
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
        raise ValueError("classical width must be a positive integer")
    if not isinstance(raw, Mapping) or not raw:
        raise ValueError("counts must be a non-empty mapping")
    normalized: Dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("counts values must be non-negative integers")
        if isinstance(key, int) and not isinstance(key, bool):
            if key < 0:
                raise ValueError("counts keys must be non-negative")
            bits = format(key, "b")
        elif isinstance(key, str):
            token = key.replace(" ", "")
            if token.startswith("0b"):
                bits = token[2:]
            elif token.isdigit() and set(token) <= {"0", "1"}:
                bits = token
            elif token.isdigit():
                bits = format(int(token), "b")
            else:
                raise ValueError("unsupported counts key: %r" % key)
        else:
            raise ValueError("unsupported counts key: %r" % key)
        if not bits or set(bits) - {"0", "1"}:
            raise ValueError("counts keys must be binary")
        if len(bits) > width:
            raise ValueError("counts key exceeds classical width")
        bits = bits.zfill(width)
        normalized[bits] = normalized.get(bits, 0) + value
    if sum(normalized.values()) != shots:
        raise ValueError("counts total must equal shots")
    return normalized


Runner = Callable[[Circuit, int], Tuple[Mapping[Any, Any], str, str, Optional[Dict[str, Any]]]]
RUNNERS: Dict[str, Runner] = {}


def run(source: str, target: str, shots: int) -> Dict[str, Any]:
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    if target not in EMITTERS:
        raise ValueError("unsupported L1 target: %s" % target)
    circuit = parse_qasm(source)
    runner = RUNNERS.get(target)
    if runner is None:
        raise RuntimeError("L1 runner is not installed for target: %s" % target)
    raw, backend, job_id, meta = runner(circuit, shots)
    result: Dict[str, Any] = {
        "backend": backend,
        "job_id": str(job_id),
        "shots": shots,
        "counts": normalize_counts(raw, shots, circuit.classical_count),
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if meta:
        result["meta"] = meta
    return result
