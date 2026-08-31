"""Encoding tools for the LoomQ RISC-V custom-0 quantum extension."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .ir import Gate, Measure, parse_qasm2


CUSTOM_0_OPCODE = 0x0B
# Base profile: funct7=0. Parameter profile: funct7=1 and rd names the
# classical register holding a signed micro-radian angle.
ANGLE_SCALE = 1_000_000
ANGLE_REGISTER = 31
FUNCT3 = {
    "qh": 0b000,
    "qx": 0b001,
    "qs": 0b010,
    "qt": 0b011,
    "qcx": 0b100,
    "qswap": 0b101,
    "qccx": 0b110,
    "qmeasure": 0b111,
}
PARAM_FUNCT3 = {"qry": 0b000, "qrz": 0b001, "qcu1": 0b010}
NAMES = {value: key for key, value in FUNCT3.items()}
PARAM_NAMES = {value: key for key, value in PARAM_FUNCT3.items()}


@dataclass(frozen=True)
class QuantumInstruction:
    name: str
    q0: int
    q1: int = 0
    destination: int = 0


def _field(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 31:
        raise ValueError(f"{name} must fit an unsigned five-bit field")
    return value


def encode(instruction: QuantumInstruction) -> int:
    name = instruction.name.lower()
    if name not in FUNCT3 and name not in PARAM_FUNCT3:
        raise ValueError(f"unknown LoomQ quantum instruction: {instruction.name}")
    q0 = _field(instruction.q0, "q0")
    q1 = _field(instruction.q1, "q1")
    destination = _field(instruction.destination, "destination")
    if name in {"qh", "qx", "qs", "qt"} and (q1 or destination):
        raise ValueError(f"{name} requires reserved q1 and destination fields to be zero")
    if name in {"qcx", "qswap"} and destination:
        raise ValueError(f"{name} requires the reserved destination field to be zero")
    if name in {"qcx", "qswap", "qcu1"} and q0 == q1:
        raise ValueError(f"{name} requires distinct qubits")
    if name == "qccx" and len({q0, q1, destination}) != 3:
        raise ValueError("qccx requires three distinct qubits")
    if name == "qmeasure" and q1:
        raise ValueError("qmeasure requires the reserved q1 field to be zero")
    if name in {"qry", "qrz"} and q1:
        raise ValueError(f"{name} requires the reserved q1 field to be zero")
    funct7 = 1 if name in PARAM_FUNCT3 else 0
    funct3 = PARAM_FUNCT3[name] if funct7 else FUNCT3[name]
    return (
        CUSTOM_0_OPCODE
        | (destination << 7)
        | (funct3 << 12)
        | (q0 << 15)
        | (q1 << 20)
        | (funct7 << 25)
    )


def decode(word: int) -> QuantumInstruction:
    if isinstance(word, bool) or not isinstance(word, int) or not 0 <= word <= 0xFFFFFFFF:
        raise ValueError("instruction word must be an unsigned 32-bit integer")
    if word & 0x7F != CUSTOM_0_OPCODE:
        raise ValueError("instruction does not use the RISC-V custom-0 opcode")
    funct7 = word >> 25
    if funct7 not in {0, 1}:
        raise ValueError("unsupported funct7 quantum profile")
    funct3 = (word >> 12) & 0x7
    names = PARAM_NAMES if funct7 else NAMES
    if funct3 not in names:
        raise ValueError("reserved funct3 value for selected quantum profile")
    instruction = QuantumInstruction(
        names[funct3],
        q0=(word >> 15) & 0x1F,
        q1=(word >> 20) & 0x1F,
        destination=(word >> 7) & 0x1F,
    )
    # Re-encoding applies per-instruction reserved-field validation.
    encode(instruction)
    return instruction


def _word(instruction: QuantumInstruction, comment: str) -> str:
    return f".word 0x{encode(instruction):08x}  # {comment}"


def quantize_angle(theta: float) -> int:
    """Normalize modulo 2π and encode with absolute error at most 0.5 µrad."""
    if not math.isfinite(theta):
        raise ValueError("quantum angle must be finite")
    return int(round(math.remainder(theta, 2 * math.pi) * ANGLE_SCALE))


def assemble_qasm(qasm: str) -> str:
    """Compile the extension's documented base profile into encoded words."""
    circuit = parse_qasm2(qasm)
    lines = [f".qinit {circuit.total_qubits}"]
    names = {"h": "qh", "x": "qx", "s": "qs", "t": "qt", "cx": "qcx", "swap": "qswap", "ccx": "qccx"}
    for operation in circuit.operations:
        if isinstance(operation, Measure):
            q0 = circuit.qubit_index(operation.qubit)
            destination = 10 + circuit.cbit_index(operation.cbit)
            lines.append(_word(QuantumInstruction("qmeasure", q0, destination=destination), f"measure q[{q0}] -> x{destination}"))
            continue
        qubits = [circuit.qubit_index(ref) for ref in operation.qubits]
        if operation.name in {"ry", "rz", "cu1"}:
            encoded_angle = quantize_angle(operation.parameters[0])
            name = {"ry": "qry", "rz": "qrz", "cu1": "qcu1"}[operation.name]
            lines.append(
                f"li x{ANGLE_REGISTER}, {encoded_angle}  # angle={encoded_angle}/{ANGLE_SCALE} rad"
            )
            q1 = qubits[1] if name == "qcu1" else 0
            lines.append(
                _word(
                    QuantumInstruction(name, qubits[0], q1, ANGLE_REGISTER),
                    operation.name + " " + ", ".join(f"q[{q}]" for q in qubits),
                )
            )
            continue
        if operation.name == "sdg":
            for _ in range(3):
                lines.append(_word(QuantumInstruction("qs", qubits[0]), f"s q[{qubits[0]}] (sdg decomposition)"))
            continue
        if operation.name == "tdg":
            for _ in range(7):
                lines.append(_word(QuantumInstruction("qt", qubits[0]), f"t q[{qubits[0]}] (tdg decomposition)"))
            continue
        name = names.get(operation.name)
        if name is None:
            raise ValueError(f"quantum RISC-V profiles cannot encode {operation.name}")
        if name in {"qh", "qx", "qs", "qt"}:
            instruction = QuantumInstruction(name, qubits[0])
        elif name in {"qcx", "qswap"}:
            instruction = QuantumInstruction(name, qubits[0], qubits[1])
        else:
            instruction = QuantumInstruction(name, qubits[0], qubits[1], qubits[2])
        lines.append(_word(instruction, operation.name + " " + ", ".join(f"q[{q}]" for q in qubits)))
    return "\n".join(lines) + "\n"
