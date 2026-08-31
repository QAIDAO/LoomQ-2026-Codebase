"""Readers for the target IR subsets emitted by LoomQ."""

import re
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .expressions import evaluate_angle
from .gates import GATE_SPECS
from .model import BitRef, Circuit, Measurement, Operation, Register
from .qasm2 import parse_qasm2


_BIT = re.compile(r"^([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$")
_QASM3_QREG = re.compile(
    r"^qubit\s*\[\s*(\d+)\s*\]\s+([A-Za-z_]\w*)$", re.I
)
_QASM3_CREG = re.compile(
    r"^bit\s*\[\s*(\d+)\s*\]\s+([A-Za-z_]\w*)$", re.I
)
_GATE = re.compile(r"^([A-Za-z_]\w*)(?:\s*\((.*)\))?\s+(.+)$", re.S)
_QASM3_MEASUREMENT = re.compile(r"^(.+?)\s*=\s*measure\s+(.+)$", re.I | re.S)
_ORIGIN_DECLARATION = re.compile(r"^(QINIT|CREG)\s+(\d+)$", re.I)
_ORIGIN_MEASUREMENT = re.compile(
    r"^MEASURE\s+([^,]+)\s*,\s*(.+)$", re.I
)

_QASM3_ALIASES = {"cnot": "cx", "cp": "cu1"}
_ORIGIN_GATES = {
    "H": "h",
    "X": "x",
    "S": "s",
    "SDAG": "sdg",
    "T": "t",
    "TDAG": "tdg",
    "RY": "ry",
    "RZ": "rz",
    "CNOT": "cx",
    "CU1": "cu1",
    "CR": "cu1",
    "SWAP": "swap",
    "TOFFOLI": "ccx",
    "CCX": "ccx",
}


def parse_spinq_ir(source: str) -> Circuit:
    """Read the SpinQ OpenQASM 2 target subset."""
    return parse_qasm2(source)


def parse_braket_ir(source: str) -> Circuit:
    """Read the Braket OpenQASM 3 target subset."""
    statements = _semicolon_statements(source)
    if not statements or statements[0].lower() != "openqasm 3.0":
        raise ValueError("Expected OPENQASM 3.0 header")

    quantum: List[Register] = []
    classical: List[Register] = []
    operations: List[Operation] = []
    measurements: List[Measurement] = []
    q_by_name: Dict[str, Register] = {}
    c_by_name: Dict[str, Register] = {}

    for statement in statements[1:]:
        if statement.lower().startswith("include "):
            continue
        declaration = _QASM3_QREG.match(statement)
        if declaration:
            size_text, name = declaration.groups()
            _add_register(name, int(size_text), quantum, q_by_name, c_by_name)
            continue
        declaration = _QASM3_CREG.match(statement)
        if declaration:
            size_text, name = declaration.groups()
            _add_register(name, int(size_text), classical, c_by_name, q_by_name)
            continue
        measurement = _QASM3_MEASUREMENT.match(statement)
        if measurement:
            classical_text, quantum_text = (
                part.strip() for part in measurement.groups()
            )
            measurements.extend(
                _measurement_pairs(
                    quantum_text, classical_text, q_by_name, c_by_name
                )
            )
            continue
        operations.extend(_parse_qasm3_operations(statement, q_by_name))

    return _build_circuit(quantum, classical, operations, measurements)


def parse_origin_ir(source: str) -> Circuit:
    """Read the OriginIR subset defined by the target contract."""
    lines = _origin_lines(source)
    quantum: List[Register] = []
    classical: List[Register] = []
    operations: List[Operation] = []
    measurements: List[Measurement] = []
    q_by_name: Dict[str, Register] = {}
    c_by_name: Dict[str, Register] = {}

    for line in lines:
        declaration = _ORIGIN_DECLARATION.match(line)
        if declaration:
            kind, size_text = declaration.groups()
            if kind.upper() == "QINIT":
                _add_register("q", int(size_text), quantum, q_by_name, c_by_name)
            else:
                _add_register("c", int(size_text), classical, c_by_name, q_by_name)
            continue
        measurement = _ORIGIN_MEASUREMENT.match(line)
        if measurement:
            quantum_text, classical_text = (
                part.strip() for part in measurement.groups()
            )
            measurements.extend(
                _measurement_pairs(
                    quantum_text, classical_text, q_by_name, c_by_name
                )
            )
            continue
        operations.append(_parse_origin_operation(line, q_by_name))

    return _build_circuit(quantum, classical, operations, measurements)


TARGET_IR_READERS: Dict[str, Callable[[str], Circuit]] = {
    "spinq": parse_spinq_ir,
    "originq": parse_origin_ir,
    "braket": parse_braket_ir,
}


def parse_target_ir(source: str, target: str) -> Circuit:
    """Read one supported target IR into the canonical circuit model."""
    if not isinstance(target, str):
        raise ValueError("target must be a string")
    normalized = target.strip().lower()
    if normalized not in TARGET_IR_READERS:
        raise ValueError(f"Unsupported target: {target}")
    return TARGET_IR_READERS[normalized](source)


def _parse_qasm3_operations(
    statement: str, registers: Dict[str, Register]
) -> Sequence[Operation]:
    match = _GATE.match(statement)
    if not match:
        raise ValueError(f"Invalid OpenQASM 3 gate statement: {statement}")
    raw_name, parameter_text, operand_text = match.groups()
    name = _QASM3_ALIASES.get(raw_name.lower(), raw_name.lower())
    if name not in GATE_SPECS:
        raise ValueError(f"Unsupported OpenQASM 3 gate: {raw_name}")
    return _expand_operation(name, parameter_text, operand_text, registers)


def _parse_origin_operation(
    line: str, registers: Dict[str, Register]
) -> Operation:
    match = _GATE.match(line)
    if not match:
        raise ValueError(f"Invalid OriginIR statement: {line}")
    raw_name, parameter_text, operand_text = match.groups()
    name = _ORIGIN_GATES.get(raw_name.upper())
    if name is None:
        raise ValueError(f"Unsupported OriginIR gate: {raw_name}")

    arity, parameter_required = GATE_SPECS[name]
    if parameter_text is None and parameter_required:
        trailing = re.match(r"^(.*),\s*\((.*)\)\s*$", operand_text, re.S)
        if not trailing:
            raise ValueError(f"Gate {raw_name} requires an angle")
        operand_text, parameter_text = trailing.groups()
    if parameter_required != (parameter_text is not None):
        raise ValueError(f"Gate {raw_name} has an invalid parameter list")

    operands = tuple(part.strip() for part in operand_text.split(","))
    if len(operands) != arity:
        raise ValueError(f"Gate {raw_name} expects {arity} operands")
    qubits = tuple(_checked_bit(item, registers, "quantum") for item in operands)
    if len(set(qubits)) != len(qubits):
        raise ValueError(f"Gate {raw_name} requires distinct qubits")
    parameter = evaluate_angle(parameter_text) if parameter_text is not None else None
    return Operation(name, qubits, parameter)


def _expand_operation(
    name: str,
    parameter_text: Optional[str],
    operand_text: str,
    registers: Dict[str, Register],
) -> Sequence[Operation]:
    arity, parameter_required = GATE_SPECS[name]
    if parameter_required != (parameter_text is not None):
        raise ValueError(f"Gate {name} has an invalid parameter list")
    operand_groups = tuple(
        _operand_group(part.strip(), registers) for part in operand_text.split(",")
    )
    if len(operand_groups) != arity:
        raise ValueError(f"Gate {name} expects {arity} operands")
    width = max(len(group) for group in operand_groups)
    if any(len(group) not in (1, width) for group in operand_groups):
        raise ValueError(f"Gate {name} register operands must have compatible sizes")
    parameter = evaluate_angle(parameter_text) if parameter_text is not None else None
    operations = []
    for index in range(width):
        qubits = tuple(
            group[0] if len(group) == 1 else group[index]
            for group in operand_groups
        )
        if len(set(qubits)) != len(qubits):
            raise ValueError(f"Gate {name} requires distinct qubits")
        operations.append(Operation(name, qubits, parameter))
    return operations


def _measurement_pairs(
    quantum_text: str,
    classical_text: str,
    quantum: Dict[str, Register],
    classical: Dict[str, Register],
) -> Sequence[Measurement]:
    quantum_bit = _BIT.match(quantum_text)
    classical_bit = _BIT.match(classical_text)
    if quantum_bit or classical_bit:
        if not quantum_bit or not classical_bit:
            raise ValueError(
                "Measurement must map a bit to a bit or a register to a register"
            )
        return [
            Measurement(
                _checked_bit(quantum_text, quantum, "quantum"),
                _checked_bit(classical_text, classical, "classical"),
            )
        ]
    if quantum_text not in quantum or classical_text not in classical:
        raise ValueError(
            f"Unknown measurement register: {quantum_text} -> {classical_text}"
        )
    if quantum[quantum_text].size != classical[classical_text].size:
        raise ValueError("Measured registers must have equal sizes")
    return [
        Measurement(BitRef(quantum_text, index), BitRef(classical_text, index))
        for index in range(quantum[quantum_text].size)
    ]


def _operand_group(
    text: str, registers: Dict[str, Register]
) -> Tuple[BitRef, ...]:
    if text in registers:
        return tuple(BitRef(text, index) for index in range(registers[text].size))
    return (_checked_bit(text, registers, "quantum"),)


def _checked_bit(
    text: str, registers: Dict[str, Register], kind: str
) -> BitRef:
    match = _BIT.match(text)
    if not match:
        raise ValueError(f"Expected an indexed {kind} bit: {text}")
    name, index_text = match.groups()
    if name not in registers:
        raise ValueError(f"Unknown {kind} register: {name}")
    index = int(index_text)
    if not 0 <= index < registers[name].size:
        raise ValueError(f"Index outside register {name}: {index}")
    return BitRef(name, index)


def _add_register(
    name: str,
    size: int,
    registers: List[Register],
    own_names: Dict[str, Register],
    other_names: Dict[str, Register],
) -> None:
    if size <= 0:
        raise ValueError(f"Register {name} must have a positive size")
    if name in own_names or name in other_names:
        raise ValueError(f"Duplicate register name: {name}")
    register = Register(name, size, sum(item.size for item in registers))
    registers.append(register)
    own_names[name] = register


def _build_circuit(
    quantum: List[Register],
    classical: List[Register],
    operations: List[Operation],
    measurements: List[Measurement],
) -> Circuit:
    if not quantum:
        raise ValueError("At least one quantum register declaration is required")
    if not classical:
        raise ValueError("At least one classical register declaration is required")
    if not measurements:
        raise ValueError("At least one measurement is required")
    return Circuit(
        tuple(quantum), tuple(classical), tuple(operations), tuple(measurements)
    )


def _semicolon_statements(source: str) -> List[str]:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Target IR source must be a non-empty string")
    without_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    without_comments = re.sub(r"//[^\r\n]*", "", without_blocks)
    return [part.strip() for part in without_comments.split(";") if part.strip()]


def _origin_lines(source: str) -> List[str]:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Target IR source must be a non-empty string")
    without_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    without_comments = re.sub(r"//[^\r\n]*", "", without_blocks)
    return [
        statement.strip()
        for line in without_comments.splitlines()
        for statement in line.split(";")
        if statement.strip()
    ]
