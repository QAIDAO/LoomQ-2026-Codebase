#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0."""

from typing import Any, Dict, List, Tuple

try:
    from .loomq_core import execute, transpile_circuit
    from .loomq_agent import respond
    from .loomq_hybrid import compile_hybrid_program
except ImportError:
    from loomq_core import execute, transpile_circuit
    from loomq_agent import respond
    from loomq_hybrid import compile_hybrid_program


SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    return transpile_circuit(qasm_str, target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    return execute(qasm_str, target, shots)


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    return respond(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Compile Hybrid-QASM into quantum operations and RISC-V assembly."""
    return compile_hybrid_program(hybrid_qasm_str)
