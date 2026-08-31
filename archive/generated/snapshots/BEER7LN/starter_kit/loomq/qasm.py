"""Restricted OpenQASM 2.0 parser for the LoomQ L1 gate contract."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Sequence, Tuple

from .gate_policy import (
    PARAMETERIZED_GATES,
    PUBLIC_GATE_ARITY,
    PUBLIC_GATE_WHITELIST,
    lower_to_public_basis,
)

SUPPORTED_GATES = PUBLIC_GATE_WHITELIST

_REGISTER = re.compile(r"^(?P<kind>[qc])reg\s+(?P<name>[A-Za-z_]\w*)\[(?P<size>\d+)\]$")
_GATE = re.compile(
    r"^(?P<name>[A-Za-z_]\w*)(?:\((?P<parameter>.+)\))?\s+(?P<operands>.+)$"
)
_INDEXED = re.compile(r"^(?P<register>[A-Za-z_]\w*)\[(?P<index>\d+)\]$")
_MEASURE = re.compile(r"^measure\s+(?P<source>.+)\s*->\s*(?P<destination>.+)$", re.IGNORECASE)


class QasmParseError(ValueError):
    """Raised when input is outside the public L1 OpenQASM subset."""


@dataclass(frozen=True)
class Register:
    kind: str
    name: str
    size: int


@dataclass(frozen=True)
class GateOperation:
    name: str
    operands: Tuple[str, ...]
    parameter: Optional[str] = None


@dataclass(frozen=True)
class MeasureOperation:
    source: str
    destination: str


Operation = GateOperation | MeasureOperation


@dataclass(frozen=True)
class Program:
    quantum_register: Register
    classical_register: Register
    operations: Tuple[Operation, ...]


def parse_openqasm2(source: str) -> Program:
    """Parse the competition's OpenQASM 2.0 subset into an immutable AST."""

    if not isinstance(source, str) or not source.strip():
        raise QasmParseError("QASM source must be a non-empty string")

    statements = _statements(source)
    if len(statements) < 4 or statements[0].upper() != "OPENQASM 2.0":
        raise QasmParseError("source must begin with OPENQASM 2.0;")
    if statements[1] != 'include "qelib1.inc"':
        raise QasmParseError('source must include "qelib1.inc";')

    registers: list[Register] = []
    operations: list[Operation] = []
    for statement in statements[2:]:
        register = _parse_register(statement)
        if register is not None:
            if operations:
                raise QasmParseError("register declarations must precede operations")
            registers.append(register)
            continue
        operations.append(_parse_operation(statement))

    qregs = [register for register in registers if register.kind == "q"]
    cregs = [register for register in registers if register.kind == "c"]
    if len(qregs) != 1 or len(cregs) != 1:
        raise QasmParseError("exactly one qreg and one creg are required")
    if not operations:
        raise QasmParseError("program must contain at least one operation")

    program = Program(qregs[0], cregs[0], tuple(operations))
    _validate_program(program)
    lowered, _report = lower_to_public_basis(program)
    return lowered


def serialize_openqasm2(program: Program) -> str:
    """Render the parsed AST as deterministic, complete OpenQASM 2.0."""

    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg {program.quantum_register.name}[{program.quantum_register.size}];",
        f"creg {program.classical_register.name}[{program.classical_register.size}];",
    ]
    for operation in program.operations:
        if isinstance(operation, GateOperation):
            parameter = f"({operation.parameter})" if operation.parameter is not None else ""
            lines.append(f"{operation.name}{parameter} {', '.join(operation.operands)};")
        else:
            lines.append(f"measure {operation.source} -> {operation.destination};")
    return "\n".join(lines) + "\n"


def _statements(source: str) -> Sequence[str]:
    without_comments = re.sub(r"//[^\n]*", "", source)
    if not without_comments.rstrip().endswith(";"):
        raise QasmParseError("each QASM statement must end with a semicolon")
    raw = [item.strip() for item in without_comments.split(";")]
    if raw and raw[-1] == "":
        raw.pop()
    if not raw or any(not item for item in raw):
        raise QasmParseError("each QASM statement must be non-empty and end with a semicolon")
    return raw


def _parse_register(statement: str) -> Optional[Register]:
    match = _REGISTER.fullmatch(statement)
    if match is None:
        return None
    size = int(match.group("size"))
    if size <= 0:
        raise QasmParseError("register size must be positive")
    return Register(match.group("kind"), match.group("name"), size)


def _parse_operation(statement: str) -> Operation:
    measurement = _MEASURE.fullmatch(statement)
    if measurement is not None:
        return MeasureOperation(measurement.group("source").strip(), measurement.group("destination").strip())

    match = _GATE.fullmatch(statement)
    if match is None:
        raise QasmParseError(f"unsupported QASM statement: {statement}")
    name = match.group("name").lower()
    if name not in SUPPORTED_GATES:
        raise QasmParseError(f"unsupported gate: {name}")
    operands = tuple(operand.strip() for operand in match.group("operands").split(","))
    if not all(operands):
        raise QasmParseError("gate operands must be non-empty")
    parameter = match.group("parameter")
    if name in PARAMETERIZED_GATES and parameter is None:
        raise QasmParseError(f"{name} requires one parameter")
    if name not in PARAMETERIZED_GATES and parameter is not None:
        raise QasmParseError(f"{name} does not accept parameters")
    return GateOperation(name, operands, parameter.strip() if parameter else None)


def _validate_program(program: Program) -> None:
    measurement_seen = False
    for operation in program.operations:
        if isinstance(operation, GateOperation):
            if measurement_seen:
                raise QasmParseError("quantum gates after measurement are not supported")
            if len(operation.operands) != PUBLIC_GATE_ARITY[operation.name]:
                raise QasmParseError(f"{operation.name} has an invalid operand count")
            if len(set(operation.operands)) != len(operation.operands):
                raise QasmParseError(f"{operation.name} requires distinct quantum operands")
            for operand in operation.operands:
                _validate_indexed_operand(operand, program.quantum_register)
        else:
            measurement_seen = True
            _validate_measurement(operation, program)


def _validate_indexed_operand(operand: str, register: Register) -> None:
    match = _INDEXED.fullmatch(operand)
    if match is None or match.group("register") != register.name:
        raise QasmParseError(f"invalid quantum operand: {operand}")
    if int(match.group("index")) >= register.size:
        raise QasmParseError(f"quantum operand out of range: {operand}")


def _validate_measurement(operation: MeasureOperation, program: Program) -> None:
    source, destination = operation.source, operation.destination
    qreg, creg = program.quantum_register, program.classical_register
    if source == qreg.name and destination == creg.name:
        if qreg.size != creg.size:
            raise QasmParseError("whole-register measurement requires equal register sizes")
        return
    _validate_indexed_operand(source, qreg)
    match = _INDEXED.fullmatch(destination)
    if match is None or match.group("register") != creg.name:
        raise QasmParseError(f"invalid classical measurement destination: {destination}")
    if int(match.group("index")) >= creg.size:
        raise QasmParseError(f"classical operand out of range: {destination}")
