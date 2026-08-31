"""Isolated custom quantum RISC-V bonus implementation."""

from .compiler import QuantumRISCVProgram, compile_quantum_riscv
from .emulator import QuantumRISCVEmulator
from .encoding import (
    ANGLE_SCALE,
    CUSTOM_0_OPCODE,
    CUSTOM_1_OPCODE,
    DecodedInstruction,
    GateCode,
    QuantumEncodingError,
    decode_word,
    encode_gate,
    encode_parameter,
)

__all__ = [
    "ANGLE_SCALE",
    "CUSTOM_0_OPCODE",
    "CUSTOM_1_OPCODE",
    "DecodedInstruction",
    "GateCode",
    "QuantumEncodingError",
    "QuantumRISCVEmulator",
    "QuantumRISCVProgram",
    "compile_quantum_riscv",
    "decode_word",
    "encode_gate",
    "encode_parameter",
]
