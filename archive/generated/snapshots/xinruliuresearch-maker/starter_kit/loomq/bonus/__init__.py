"""LoomQ's experimental quantum extension for the official TinyRISCV API.

The extension is a local simulator and instruction-set demonstrator.  It does
not claim to execute on physical RISC-V or quantum hardware.
"""

from .emulator import QuantumRISCVEmulator
from .isa import (
    ANGLE_FRACTION_BITS,
    ANGLE_SCALE,
    CUSTOM_0_OPCODE,
    QuantumInstruction,
    assemble_quantum_line,
    decode_instruction,
    disassemble_word,
    encode_instruction,
    fixed_to_radians,
    radians_to_fixed,
    word_to_little_endian_bytes,
)

__all__ = [
    "CUSTOM_0_OPCODE",
    "ANGLE_FRACTION_BITS",
    "ANGLE_SCALE",
    "QuantumInstruction",
    "QuantumRISCVEmulator",
    "assemble_quantum_line",
    "decode_instruction",
    "disassemble_word",
    "encode_instruction",
    "fixed_to_radians",
    "radians_to_fixed",
    "word_to_little_endian_bytes",
]
