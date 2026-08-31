"""Decoder for LoomQ 32-bit custom quantum instruction words."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from .isa import (
    ANGLE_UNITS_MAX,
    ANGLE_UNITS_MIN,
    CUSTOM_0_OPCODE,
    CUSTOM_1_OPCODE,
    QUANTUM_FUNCT3,
    SPECS_BY_FUNCTION,
    SPECS_BY_MNEMONIC,
)


@dataclass(frozen=True)
class DecodedInstruction:
    mnemonic: str
    operands: Tuple[int, ...]

    def assembly(self) -> str:
        rendered = []
        for index, value in enumerate(self.operands):
            if self.mnemonic == "qmeasure" and index == 1:
                rendered.append(f"x{value}")
            else:
                rendered.append(str(value))
        return self.mnemonic + (" " + ", ".join(rendered) if rendered else "")


def decode_word(word: int) -> DecodedInstruction:
    """Decode one unsigned 32-bit custom instruction and validate reserved fields."""
    if not isinstance(word, int) or isinstance(word, bool) or not 0 <= word <= 0xFFFFFFFF:
        raise ValueError("Machine word must be an unsigned 32-bit integer")
    opcode = word & 0x7F
    if opcode == CUSTOM_1_OPCODE:
        if word & 0x000FFF80:
            raise ValueError("QPARAM reserved fields must be zero")
        raw = (word >> 20) & 0xFFF
        units = raw - 0x1000 if raw & 0x800 else raw
        if not ANGLE_UNITS_MIN <= units <= ANGLE_UNITS_MAX:
            raise ValueError("QPARAM angle field is invalid")
        return DecodedInstruction("qparam", (units,))
    if opcode != CUSTOM_0_OPCODE:
        raise ValueError(f"Unsupported opcode: 0x{opcode:02x}")

    funct3 = (word >> 12) & 0x7
    if funct3 != QUANTUM_FUNCT3:
        raise ValueError("Quantum custom-0 funct3 must be zero")
    rd = (word >> 7) & 0x1F
    rs1 = (word >> 15) & 0x1F
    rs2 = (word >> 20) & 0x1F
    function = (word >> 25) & 0x7F
    spec = SPECS_BY_FUNCTION.get(function)
    if spec is None:
        raise ValueError(f"Unsupported quantum function: {function}")

    if spec.mnemonic == "qinit":
        if rs1 or rs2 or rd == 0:
            raise ValueError("QINIT requires rd=qubit_count and zero source fields")
        operands = (rd,)
    elif spec.mnemonic == "qccx":
        if len({rd, rs1, rs2}) != 3:
            raise ValueError("QCCX requires three distinct qubits")
        operands = (rs1, rs2, rd)
    elif spec.mnemonic == "qmeasure":
        if rs2 or rd == 0:
            raise ValueError("QMEASURE requires rs2=0 and a nonzero destination register")
        operands = (rs1, rd)
    elif len(spec.operands) == 2:
        if rd or rs1 == rs2:
            raise ValueError(f"{spec.mnemonic.upper()} has invalid or repeated operands")
        operands = (rs1, rs2)
    else:
        if rd or rs2:
            raise ValueError(f"{spec.mnemonic.upper()} reserved fields must be zero")
        operands = (rs1,)
    return DecodedInstruction(spec.mnemonic, operands)


def decode_program(words: Iterable[int]) -> Tuple[DecodedInstruction, ...]:
    """Decode and validate an ordered custom instruction stream."""
    decoded = tuple(decode_word(word) for word in words)
    pending_parameter = False
    for instruction in decoded:
        if instruction.mnemonic == "qparam":
            if pending_parameter:
                raise ValueError("QPARAM cannot overwrite an unconsumed angle")
            pending_parameter = True
            continue
        spec = SPECS_BY_MNEMONIC[instruction.mnemonic]
        if pending_parameter != spec.parameterized:
            if pending_parameter:
                raise ValueError("QPARAM must be followed by a parameterized quantum gate")
            raise ValueError(f"{instruction.mnemonic.upper()} requires a preceding QPARAM")
        pending_parameter = False
    if pending_parameter:
        raise ValueError("Instruction stream ends with an unconsumed QPARAM")
    return decoded
