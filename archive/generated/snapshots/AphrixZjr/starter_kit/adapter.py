#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This file intentionally contains no scoring implementation. Teams may implement
the functions directly or delegate to another language/runtime with subprocess.
"""

from typing import Any, Dict, List, Tuple

try:
    from .loomq_l1 import RUNNERS
    from .loomq_l1 import run as _run
    from .loomq_l1 import transpile as _transpile
    from .l1_braket import run_braket
    from .l1_originq import run_originq
    from .l1_spinq import run_spinq
    from .loomq_l2 import agent_chat as _agent_chat
    from .loomq_l3 import compile_hybrid as _compile_hybrid
except ImportError:
    from loomq_l1 import RUNNERS
    from loomq_l1 import run as _run
    from loomq_l1 import transpile as _transpile
    from l1_braket import run_braket
    from l1_originq import run_originq
    from l1_spinq import run_spinq
    from loomq_l2 import agent_chat as _agent_chat
    from loomq_l3 import compile_hybrid as _compile_hybrid


RUNNERS["spinq"] = run_spinq
RUNNERS["originq"] = run_originq
RUNNERS["braket"] = run_braket

SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    return _transpile(qasm_str, target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    return _run(qasm_str, target, shots)


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    return _agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Compile Hybrid-QASM into quantum operations and Tiny RISC-V assembly."""
    return _compile_hybrid(hybrid_qasm_str)
