#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This file intentionally contains no scoring implementation. Teams may implement
the functions directly or delegate to another language/runtime with subprocess.
"""

from typing import Any, Dict, List, Tuple

if __package__:
    from .loomq.backends import run as run_backend
    from .loomq.l2 import agent_chat as run_agent_chat
    from .loomq.hybrid import compile_hybrid as compile_hybrid_program
    from .loomq.pipeline import trace_transpilation
else:
    from loomq.backends import run as run_backend
    from loomq.l2 import agent_chat as run_agent_chat
    from loomq.hybrid import compile_hybrid as compile_hybrid_program
    from loomq.pipeline import trace_transpilation


SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"Unsupported target: {target}")
    return trace_transpilation(qasm_str, target).public_ir


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    return run_backend(qasm_str, target, shots)


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    return run_agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Compile Hybrid-QASM into quantum operations and executable RISC-V."""
    return compile_hybrid_program(hybrid_qasm_str)