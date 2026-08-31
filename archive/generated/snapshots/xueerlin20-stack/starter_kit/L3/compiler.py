"""Public deterministic compiler pipeline for LoomQ L3."""

from __future__ import annotations

from typing import List, Tuple

from .quantum import parse_hybrid_program
from .riscv_compiler import compile_riscv


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Compile Hybrid-QASM into ordered quantum operations and RISC-V text."""
    program = parse_hybrid_program(hybrid_qasm_str)
    assembly = compile_riscv(
        program.classical_statements, program.classical_bit_count
    )
    return list(program.quantum_operations), assembly

