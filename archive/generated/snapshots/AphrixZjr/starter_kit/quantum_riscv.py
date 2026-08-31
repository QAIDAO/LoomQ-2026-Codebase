"""Compatibility imports for the official RISC-V emulator extension.

LoomQ-QISA-v1 now lives in :mod:`riscv_emulator`, as required by the Bonus
delivery contract.  This module keeps the original public import path working
for downstream users and older tests.
"""

from riscv_emulator import (
    Decoded,
    GATE_ARITY,
    GATE_NAMES,
    GATES,
    MASK32,
    OP_B,
    OP_I,
    OP_J,
    OP_QCTRL,
    OP_QGATE,
    OP_R,
    OP_U,
    QISAError,
    QuantumBackend,
    QuantumRISCVEmulator,
    assemble,
    decode,
    reference_backend,
)


__all__ = [
    "Decoded",
    "GATE_ARITY",
    "GATE_NAMES",
    "GATES",
    "MASK32",
    "OP_B",
    "OP_I",
    "OP_J",
    "OP_QCTRL",
    "OP_QGATE",
    "OP_R",
    "OP_U",
    "QISAError",
    "QuantumBackend",
    "QuantumRISCVEmulator",
    "assemble",
    "decode",
    "reference_backend",
]
