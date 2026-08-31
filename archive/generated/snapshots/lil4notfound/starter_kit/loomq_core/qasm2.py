"""Parser for the OpenQASM 2.0 subset defined by the competition."""

import re
from typing import Dict, List, Sequence, Tuple

from .expressions import evaluate_angle
from .gates import GATE_SPECS
from .model import BitRef, Circuit, Measurement, Operation, Register


SUPPORTED_GATES = GATE_SPECS

_DECLARATION = re.compile(r"^(qreg|creg)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$", re.I)
_BIT = re.compile(r"^([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$")
_GATE = re.compile(r"^([A-Za-z_]\w*)(?:\s*\((.*)\))?\s+(.+)$", re.S)


def parse_qasm2(source: str) -> Circuit:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("QASM source must be a non-empty string")
    statements = _statements(source)
    if not statements or statements[0].lower() != "openqasm 2.0":
        raise ValueError("Expected OPENQASM 2.0 header")

    quantum: List[Register] = []
    classical: List[Register] = []
    operations: List[Operation] = []
    measurements: List[Measurement] = []
    q_by_name: Dict[str, Register] = {}
    c_by_name: Dict[str, Register] = {}

    for statement in statements[1:]:
        lowered = statement.lower()
        if lowered.startswith("include "):
            continue
        declaration = _DECLARATION.match(statement)
        if declaration:
            kind, name, size_text = declaration.groups()
            size = int(size_text)
            if size <= 0:
                raise ValueError(f"Register {name} must have a positive size")
            if name in q_by_name or name in c_by_name:
                raise ValueError(f"Duplicate register name: {name}")
            registers = quantum if kind.lower() == "qreg" else classical
            register = Register(name, size, sum(item.size for item in registers))
            registers.append(register)
            (q_by_name if kind.lower() == "qreg" else c_by_name)[name] = register
            continue
        if lowered.startswith("measure "):
            measurements.extend(_parse_measurement(statement, q_by_name, c_by_name))
            continue
        operations.extend(_parse_operations(statement, q_by_name))

    if not quantum:
        raise ValueError("At least one qreg declaration is required")
    if not classical:
        raise ValueError("At least one creg declaration is required")
    if not measurements:
        raise ValueError("At least one measurement is required")
    return Circuit(tuple(quantum), tuple(classical), tuple(operations), tuple(measurements))


def _statements(source: str) -> List[str]:
    without_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    without_comments = re.sub(r"//[^\r\n]*", "", without_blocks)
    return [part.strip() for part in without_comments.split(";") if part.strip()]


def _parse_measurement(
    statement: str,
    q_registers: Dict[str, Register],
    c_registers: Dict[str, Register],
) -> Sequence[Measurement]:
    payload = statement[len("measure") :].strip()
    if "->" not in payload:
        raise ValueError(f"Invalid measurement: {statement}")
    left, right = (part.strip() for part in payload.split("->", 1))
    left_bit = _BIT.match(left)
    right_bit = _BIT.match(right)
    if left_bit or right_bit:
        if not left_bit or not right_bit:
            raise ValueError("Measurement must map a bit to a bit or a register to a register")
        qubit = _checked_bit(left_bit.groups(), q_registers, "quantum")
        classical = _checked_bit(right_bit.groups(), c_registers, "classical")
        return [Measurement(qubit, classical)]
    if left not in q_registers or right not in c_registers:
        raise ValueError(f"Unknown measurement register: {left} -> {right}")
    if q_registers[left].size != c_registers[right].size:
        raise ValueError("Measured registers must have equal sizes")
    return [Measurement(BitRef(left, index), BitRef(right, index)) for index in range(q_registers[left].size)]


def _parse_operations(
    statement: str, q_registers: Dict[str, Register]
) -> Sequence[Operation]:
    match = _GATE.match(statement)
    if not match:
        raise ValueError(f"Invalid gate statement: {statement}")
    name, parameter_text, operand_text = match.groups()
    name = name.lower()
    if name not in SUPPORTED_GATES:
        raise ValueError(f"Unsupported gate: {name}")
    arity, parameter_required = SUPPORTED_GATES[name]
    if parameter_required != (parameter_text is not None):
        raise ValueError(f"Gate {name} has an invalid parameter list")
    operand_groups = tuple(
        _parse_operand(part.strip(), q_registers) for part in operand_text.split(",")
    )
    if len(operand_groups) != arity:
        raise ValueError(f"Gate {name} expects {arity} operands")
    width = max(len(group) for group in operand_groups)
    for group in operand_groups:
        if len(group) not in (1, width):
            raise ValueError(f"Gate {name} register operands must have compatible sizes")
    parameter = evaluate_angle(parameter_text) if parameter_text is not None else None
    operations = []
    for index in range(width):
        operands = tuple(group[0] if len(group) == 1 else group[index] for group in operand_groups)
        if len(set(operands)) != len(operands):
            raise ValueError(f"Gate {name} requires distinct qubits")
        operations.append(Operation(name, operands, parameter))
    return operations


def _parse_operand(
    text: str, registers: Dict[str, Register]
) -> Tuple[BitRef, ...]:
    if text in registers:
        return tuple(BitRef(text, index) for index in range(registers[text].size))
    return (_parse_bit(text, registers, "quantum"),)


def _parse_bit(text: str, registers: Dict[str, Register], kind: str) -> BitRef:
    match = _BIT.match(text)
    if not match:
        raise ValueError(f"Expected an indexed {kind} bit: {text}")
    return _checked_bit(match.groups(), registers, kind)


def _checked_bit(parts: Tuple[str, str], registers: Dict[str, Register], kind: str) -> BitRef:
    name, index_text = parts
    if name not in registers:
        raise ValueError(f"Unknown {kind} register: {name}")
    index = int(index_text)
    if not 0 <= index < registers[name].size:
        raise ValueError(f"Index outside register {name}: {index}")
    return BitRef(name, index)
