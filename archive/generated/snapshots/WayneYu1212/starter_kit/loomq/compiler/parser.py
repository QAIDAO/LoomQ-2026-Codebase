"""Parser for the exact OpenQASM 2.0 subset used by LoomQ scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .expressions import parse_parameter
from .ir import Circuit, Gate, Measurement, Operation
from .validator import CircuitValidationError, validate_circuit


_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_DECLARATION_RE = re.compile(rf"^(qreg|creg)\s+({_IDENTIFIER})\s*\[\s*(\d+)\s*\]$", re.I)
_REFERENCE_RE = re.compile(rf"^({_IDENTIFIER})\s*\[\s*(\d+)\s*\]$")
_MEASURE_RE = re.compile(r"^measure\s+(.+?)\s*->\s*(.+)$", re.I)
_GATE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)(?:\s*\((.*)\))?\s+(.+)$", re.S)


class QASMParseError(ValueError):
    """Raised when source text is outside the published QASM subset."""


@dataclass(frozen=True, slots=True)
class _Register:
    offset: int
    size: int


def _strip_comments(source: str) -> str:
    without_blocks = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    return re.sub(r"//[^\r\n]*", "", without_blocks)


def _canonical(statement: str) -> str:
    return " ".join(statement.strip().split())


def _statements(source: str) -> list[str]:
    cleaned = _strip_comments(source).strip()
    if not cleaned:
        raise QASMParseError("QASM source is empty")
    if not cleaned.endswith(";"):
        raise QASMParseError("every QASM statement must end with a semicolon")
    return [_canonical(part) for part in cleaned.split(";") if part.strip()]


def _resolve_reference(reference: str, registers: dict[str, _Register], kind: str) -> int:
    match = _REFERENCE_RE.fullmatch(reference.strip())
    if match is None:
        raise QASMParseError(f"invalid {kind} reference `{reference.strip()}`")
    name, raw_index = match.groups()
    register = registers.get(name)
    if register is None:
        raise QASMParseError(f"undeclared {kind} register `{name}`")
    index = int(raw_index)
    if index >= register.size:
        raise CircuitValidationError(f"{kind} index {index} is out of range for `{name}`")
    return register.offset + index


def _parse_measurement(
    statement: str,
    qregs: dict[str, _Register],
    cregs: dict[str, _Register],
) -> list[Measurement] | None:
    match = _MEASURE_RE.fullmatch(statement)
    if match is None:
        return None
    quantum, classical = (part.strip() for part in match.groups())
    if quantum in qregs or classical in cregs:
        if quantum not in qregs or classical not in cregs:
            raise QASMParseError("register measurement must name declared quantum and classical registers")
        qreg = qregs[quantum]
        creg = cregs[classical]
        if qreg.size != creg.size:
            raise CircuitValidationError("register measurement widths must match")
        return [
            Measurement(qreg.offset + index, creg.offset + index, statement)
            for index in range(qreg.size)
        ]
    return [
        Measurement(
            _resolve_reference(quantum, qregs, "quantum"),
            _resolve_reference(classical, cregs, "classical"),
            statement,
        )
    ]


def _parse_gate(statement: str, qregs: dict[str, _Register]) -> Gate:
    match = _GATE_RE.fullmatch(statement)
    if match is None:
        raise QASMParseError(f"unsupported QASM statement `{statement}`")
    raw_name, raw_parameter, raw_operands = match.groups()
    name = raw_name.lower()
    operands = [part.strip() for part in raw_operands.split(",")]
    if not operands or any(not operand for operand in operands):
        raise QASMParseError(f"gate `{name}` has invalid operands")
    qubits = tuple(_resolve_reference(operand, qregs, "quantum") for operand in operands)
    if raw_parameter is None:
        params: tuple[float, ...] = ()
    else:
        try:
            params = (parse_parameter(raw_parameter.strip()),)
        except ValueError as exc:
            raise QASMParseError(f"invalid gate parameter in `{statement}`: {exc}") from exc
    return Gate(name=name, qubits=qubits, params=params, source=statement)


def parse_qasm(source: str) -> Circuit:
    """Parse and validate a complete LoomQ OpenQASM 2.0 program."""

    if not isinstance(source, str):
        raise QASMParseError("QASM source must be a string")
    statements = _statements(source)
    if not re.fullmatch(r"OPENQASM\s+2\.0", statements[0], flags=re.I):
        raise QASMParseError("first statement must be OPENQASM 2.0")
    if len(statements) < 2 or not re.fullmatch(
        r'include\s+"qelib1\.inc"', statements[1], flags=re.I
    ):
        raise QASMParseError('second statement must be include "qelib1.inc"')

    qregs: dict[str, _Register] = {}
    cregs: dict[str, _Register] = {}
    qubit_count = 0
    cbit_count = 0
    operations: list[Operation] = []
    operations_started = False

    for statement in statements[2:]:
        declaration = _DECLARATION_RE.fullmatch(statement)
        if declaration is not None:
            if operations_started:
                raise QASMParseError("register declarations must precede operations")
            kind, name, raw_size = declaration.groups()
            size = int(raw_size)
            if size <= 0:
                raise QASMParseError("register size must be positive")
            register_map = qregs if kind.lower() == "qreg" else cregs
            if name in register_map:
                raise QASMParseError(f"register `{name}` is declared more than once")
            if kind.lower() == "qreg":
                register_map[name] = _Register(qubit_count, size)
                qubit_count += size
            else:
                register_map[name] = _Register(cbit_count, size)
                cbit_count += size
            continue

        operations_started = True
        measurements = _parse_measurement(statement, qregs, cregs)
        if measurements is not None:
            operations.extend(measurements)
        else:
            operations.append(_parse_gate(statement, qregs))

    if not qregs or not cregs:
        raise QASMParseError("QASM must declare quantum and classical registers")
    circuit = Circuit(qubit_count, cbit_count, tuple(operations))
    validate_circuit(circuit)
    return circuit
