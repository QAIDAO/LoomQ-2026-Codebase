"""Instruction definitions for the optional LoomQ quantum RISC-V extension."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Tuple


CUSTOM_0_OPCODE = 0x0B
CUSTOM_1_OPCODE = 0x2B
QUANTUM_FUNCT3 = 0
ANGLE_STEP = math.pi / 1024.0
ANGLE_UNITS_MIN = -2048
ANGLE_UNITS_MAX = 2047
MAX_ENCODED_QUBITS = 31
MAX_SIMULATED_QUBITS = 20


@dataclass(frozen=True)
class InstructionSpec:
    mnemonic: str
    function: int
    operands: Tuple[str, ...]
    parameterized: bool = False


INSTRUCTION_SPECS = (
    InstructionSpec("qinit", 1, ("qubit_count",)),
    InstructionSpec("qh", 2, ("qubit",)),
    InstructionSpec("qx", 3, ("qubit",)),
    InstructionSpec("qs", 4, ("qubit",)),
    InstructionSpec("qsdg", 5, ("qubit",)),
    InstructionSpec("qt", 6, ("qubit",)),
    InstructionSpec("qtdg", 7, ("qubit",)),
    InstructionSpec("qry", 8, ("qubit",), True),
    InstructionSpec("qrz", 9, ("qubit",), True),
    InstructionSpec("qcx", 10, ("control", "target")),
    InstructionSpec("qcu1", 11, ("control", "target"), True),
    InstructionSpec("qswap", 12, ("first", "second")),
    InstructionSpec("qccx", 13, ("control_a", "control_b", "target")),
    InstructionSpec("qmeasure", 14, ("qubit", "register")),
)

SPECS_BY_MNEMONIC: Dict[str, InstructionSpec] = {
    item.mnemonic: item for item in INSTRUCTION_SPECS
}
SPECS_BY_FUNCTION: Dict[int, InstructionSpec] = {
    item.function: item for item in INSTRUCTION_SPECS
}


def angle_to_units(angle: float) -> int:
    """Quantize a radian angle into the signed 12-bit fixed-point field."""
    if not isinstance(angle, (int, float)) or isinstance(angle, bool):
        raise ValueError("Quantum rotation angle must be numeric")
    value = float(angle)
    if not math.isfinite(value):
        raise ValueError("Quantum rotation angle must be finite")
    units = int(round(value / ANGLE_STEP))
    if not ANGLE_UNITS_MIN <= units <= ANGLE_UNITS_MAX:
        raise ValueError("Quantum rotation angle is outside the encodable range")
    return units


def units_to_angle(units: int) -> float:
    """Convert a signed 12-bit fixed-point field into radians."""
    if not isinstance(units, int) or isinstance(units, bool):
        raise ValueError("Quantum angle units must be an integer")
    if not ANGLE_UNITS_MIN <= units <= ANGLE_UNITS_MAX:
        raise ValueError("Quantum angle units are outside signed 12-bit range")
    return units * ANGLE_STEP
