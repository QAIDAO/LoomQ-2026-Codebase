"""Stable 32-bit encoding for the LoomQ experimental quantum RISC-V ISA.

The encoding occupies RISC-V's ``custom-0`` major opcode (binary 0001011).
It deliberately uses GPR *register operands*: the integer stored in ``rs1``
or ``rs2`` selects a quantum bit at execution time.  ``rd`` is used only by a
measurement and receives 0 or 1.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import struct
from typing import Dict, Tuple


CUSTOM_0_OPCODE = 0b0001011
ANGLE_FRACTION_BITS = 16
ANGLE_SCALE = 1 << ANGLE_FRACTION_BITS
_WORD_MASK = (1 << 32) - 1


class QuantumISAError(ValueError):
    """Base error for malformed or unsupported LoomQ quantum instructions."""


class QuantumEncodingError(QuantumISAError):
    """Raised when an instruction cannot be encoded."""


class QuantumDecodingError(QuantumISAError):
    """Raised when a machine word is not a canonical LoomQ instruction."""


@dataclass(frozen=True)
class _OpcodeSpec:
    mnemonic: str
    funct3: int
    funct7: int
    operand_form: str


_SPECS: Tuple[_OpcodeSpec, ...] = (
    _OpcodeSpec("qh", 0b000, 0, "single"),
    _OpcodeSpec("qx", 0b000, 1, "single"),
    _OpcodeSpec("qs", 0b000, 2, "single"),
    _OpcodeSpec("qt", 0b000, 3, "single"),
    _OpcodeSpec("qcx", 0b001, 0, "double"),
    _OpcodeSpec("qswap", 0b001, 1, "double"),
    _OpcodeSpec("qmeasure", 0b010, 0, "measure"),
    _OpcodeSpec("qinit", 0b011, 0, "init"),
    _OpcodeSpec("qry", 0b100, 0, "rotation"),
    _OpcodeSpec("qrz", 0b100, 1, "rotation"),
    _OpcodeSpec("qccx", 0b101, 0, "triple"),
)
_BY_MNEMONIC: Dict[str, _OpcodeSpec] = {spec.mnemonic: spec for spec in _SPECS}
_BY_FUNCTION: Dict[Tuple[int, int], _OpcodeSpec] = {
    (spec.funct3, spec.funct7): spec for spec in _SPECS
}
_REGISTER_RE = re.compile(r"^[xX]([0-9]|[12][0-9]|3[01])$")


def _register_index(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise QuantumEncodingError(f"{field} must be a GPR index, not bool")
    if isinstance(value, int):
        index = value
    elif isinstance(value, str):
        match = _REGISTER_RE.fullmatch(value.strip())
        if match is None:
            raise QuantumEncodingError(f"invalid {field} register: {value!r}")
        index = int(match.group(1))
    else:
        raise QuantumEncodingError(f"invalid {field} register: {value!r}")
    if not 0 <= index <= 31:
        raise QuantumEncodingError(f"{field} register index must be in x0..x31")
    return index


@dataclass(frozen=True)
class QuantumInstruction:
    """Decoded canonical instruction with register indices and raw word."""

    mnemonic: str
    rd: int
    rs1: int
    rs2: int
    word: int

    @property
    def operand_form(self) -> str:
        return _BY_MNEMONIC[self.mnemonic].operand_form

    def to_assembly(self) -> str:
        if self.operand_form in {"single", "init"}:
            return f"{self.mnemonic} x{self.rs1}"
        if self.operand_form in {"double", "rotation"}:
            return f"{self.mnemonic} x{self.rs1}, x{self.rs2}"
        if self.operand_form == "triple":
            return f"{self.mnemonic} x{self.rs1}, x{self.rs2}, x{self.rd}"
        return f"{self.mnemonic} x{self.rd}, x{self.rs1}"


def encode_instruction(
    mnemonic: str,
    *,
    rs1: object,
    rs2: object = 0,
    rd: object = 0,
) -> int:
    """Encode one canonical quantum instruction into an unsigned 32-bit word.

    Unused fields must remain x0.  Requiring canonical zero fields makes the
    binary representation stable and catches accidental operand loss.
    """

    if not isinstance(mnemonic, str):
        raise QuantumEncodingError("mnemonic must be text")
    normalized = mnemonic.strip().lower()
    spec = _BY_MNEMONIC.get(normalized)
    if spec is None:
        raise QuantumEncodingError(f"unsupported quantum mnemonic: {mnemonic!r}")
    rd_index = _register_index(rd, field="rd")
    rs1_index = _register_index(rs1, field="rs1")
    rs2_index = _register_index(rs2, field="rs2")

    if spec.operand_form in {"single", "init"} and (
        rd_index != 0 or rs2_index != 0
    ):
        raise QuantumEncodingError(f"{normalized} requires rd=x0 and rs2=x0")
    if spec.operand_form in {"double", "rotation"} and rd_index != 0:
        raise QuantumEncodingError(f"{normalized} requires rd=x0")
    if spec.operand_form == "measure" and rs2_index != 0:
        raise QuantumEncodingError("qmeasure requires rs2=x0")
    if spec.operand_form == "measure" and rd_index == 0:
        raise QuantumEncodingError("qmeasure destination cannot be x0")

    return (
        (spec.funct7 << 25)
        | (rs2_index << 20)
        | (rs1_index << 15)
        | (spec.funct3 << 12)
        | (rd_index << 7)
        | CUSTOM_0_OPCODE
    )


def decode_instruction(word: object) -> QuantumInstruction:
    """Decode and validate a canonical LoomQ quantum custom instruction."""

    if isinstance(word, bool) or not isinstance(word, int):
        raise QuantumDecodingError("machine word must be an unsigned 32-bit integer")
    if not 0 <= word <= _WORD_MASK:
        raise QuantumDecodingError("machine word must be in range 0..0xffffffff")
    opcode = word & 0x7F
    if opcode != CUSTOM_0_OPCODE:
        raise QuantumDecodingError(
            f"expected custom-0 opcode 0x{CUSTOM_0_OPCODE:02x}, got 0x{opcode:02x}"
        )
    rd = (word >> 7) & 0x1F
    funct3 = (word >> 12) & 0x7
    rs1 = (word >> 15) & 0x1F
    rs2 = (word >> 20) & 0x1F
    funct7 = (word >> 25) & 0x7F
    spec = _BY_FUNCTION.get((funct3, funct7))
    if spec is None:
        raise QuantumDecodingError(
            f"unsupported quantum function funct3={funct3:#x}, funct7={funct7:#x}"
        )
    if spec.operand_form in {"single", "init"} and (rd != 0 or rs2 != 0):
        raise QuantumDecodingError(f"non-canonical {spec.mnemonic}: rd/rs2 must be x0")
    if spec.operand_form in {"double", "rotation"} and rd != 0:
        raise QuantumDecodingError(f"non-canonical {spec.mnemonic}: rd must be x0")
    if spec.operand_form == "measure" and rs2 != 0:
        raise QuantumDecodingError("non-canonical qmeasure: rs2 must be x0")
    if spec.operand_form == "measure" and rd == 0:
        raise QuantumDecodingError("non-canonical qmeasure: rd cannot be x0")
    return QuantumInstruction(spec.mnemonic, rd, rs1, rs2, word)


def assemble_quantum_line(line: str) -> int:
    """Assemble one quantum mnemonic line (comments are permitted)."""

    if not isinstance(line, str):
        raise QuantumEncodingError("assembly line must be text")
    code = line.split("#", 1)[0].strip()
    if not code:
        raise QuantumEncodingError("assembly line is empty")
    parts = code.replace(",", " ").split()
    mnemonic = parts[0].lower()
    spec = _BY_MNEMONIC.get(mnemonic)
    if spec is None:
        raise QuantumEncodingError(f"unsupported quantum mnemonic: {parts[0]!r}")
    if spec.operand_form in {"single", "init"}:
        expected = 2
    elif spec.operand_form == "triple":
        expected = 4
    else:
        expected = 3
    if len(parts) != expected:
        operand_count = expected - 1
        raise QuantumEncodingError(
            f"{mnemonic} expects {operand_count} operand(s), got {len(parts) - 1}"
        )
    if spec.operand_form in {"single", "init"}:
        return encode_instruction(mnemonic, rs1=parts[1])
    if spec.operand_form in {"double", "rotation"}:
        return encode_instruction(mnemonic, rs1=parts[1], rs2=parts[2])
    if spec.operand_form == "triple":
        return encode_instruction(
            mnemonic, rs1=parts[1], rs2=parts[2], rd=parts[3]
        )
    return encode_instruction(mnemonic, rd=parts[1], rs1=parts[2])


def disassemble_word(word: object) -> str:
    """Return the canonical assembly spelling for a machine word."""

    return decode_instruction(word).to_assembly()


def word_to_little_endian_bytes(word: object) -> bytes:
    """Serialize one validated instruction word in RISC-V little-endian order."""

    instruction = decode_instruction(word)
    return struct.pack("<I", instruction.word)


def radians_to_fixed(radians: object) -> int:
    """Encode radians as a signed Q16.16 value suitable for a GPR operand."""

    if isinstance(radians, bool) or not isinstance(radians, (int, float)):
        raise QuantumEncodingError("angle must be a finite number of radians")
    numeric = float(radians)
    if not math.isfinite(numeric):
        raise QuantumEncodingError("angle must be a finite number of radians")
    encoded = round(numeric * ANGLE_SCALE)
    if not -(1 << 31) <= encoded <= (1 << 31) - 1:
        raise QuantumEncodingError("Q16.16 angle is outside signed 32-bit range")
    return encoded


def fixed_to_radians(value: object) -> float:
    """Decode a signed or unsigned-two's-complement Q16.16 GPR value."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise QuantumDecodingError("angle GPR value must be a 32-bit integer")
    if value < -(1 << 31) or value > _WORD_MASK:
        raise QuantumDecodingError("angle GPR value is outside 32-bit range")
    signed = value
    if signed > (1 << 31) - 1:
        signed -= 1 << 32
    return signed / ANGLE_SCALE
