"""Optional quantum RISC-V extension services."""

from .compiler import QuantumBonusProgram, compile_hybrid_bonus, compile_quantum_qasm
from .decoder import DecodedInstruction, decode_program, decode_word
from .emulator import QuantumRISCVEmulator
from .encoder import encode_assembly, encode_instruction

__all__ = [
    "DecodedInstruction",
    "QuantumBonusProgram",
    "QuantumRISCVEmulator",
    "compile_hybrid_bonus",
    "compile_quantum_qasm",
    "decode_program",
    "decode_word",
    "encode_assembly",
    "encode_instruction",
]
