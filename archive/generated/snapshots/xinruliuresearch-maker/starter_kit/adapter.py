#!/usr/bin/env python3
"""Thin LoomQ submission adapter for contract v1.0."""

from typing import Any, Dict, List, Tuple

try:
    from .loomq.agent import agent_chat as _agent_chat
    from .loomq.facade import run as _run
    from .loomq.facade import transpile as _transpile
    from .loomq.hybrid import compile_hybrid_program as _compile_hybrid
except ImportError:  # Direct execution from the starter_kit working directory.
    from loomq.agent import agent_chat as _agent_chat
    from loomq.facade import run as _run
    from loomq.facade import transpile as _transpile
    from loomq.hybrid import compile_hybrid_program as _compile_hybrid


SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    return _transpile(qasm_str, target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    return _run(qasm_str, target, shots)


def agent_chat(prompt: str) -> str:
    """Run the bounded L2 workflow using the documented LOOMQ_LLM_* environment."""
    return _agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    if not isinstance(hybrid_qasm_str, str):
        raise TypeError("hybrid_qasm_str must be a string")
    if not hybrid_qasm_str.strip():
        raise ValueError("hybrid_qasm_str must not be empty")
    if len(hybrid_qasm_str.encode("utf-8")) > 256_000:
        raise ValueError("hybrid_qasm_str exceeds the 256000-byte safety limit")
    return _compile_hybrid(hybrid_qasm_str)
