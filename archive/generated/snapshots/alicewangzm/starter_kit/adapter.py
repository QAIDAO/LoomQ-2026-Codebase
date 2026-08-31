#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

The graded entry points. transpile/run delegate to the loomq package; L2/L3
remain optional and raise NotImplementedError until implemented.
"""

import os
import sys
from typing import Any, Dict, List, Tuple

# The loomq package uses flat imports (``from parser import ...``) so its modules
# run as standalone scripts for testing. Put that directory on sys.path so this
# adapter can import them whether it is loaded as ``starter_kit.adapter`` or run
# directly by the evaluator.
_LOOMQ_DIR = os.path.join(os.path.dirname(__file__), "loomq")
if _LOOMQ_DIR not in sys.path:
    sys.path.insert(0, _LOOMQ_DIR)

from agent import agent_chat as _agent_chat  # noqa: E402
from runtime import run as _run  # noqa: E402
from runtime import transpile as _transpile  # noqa: E402


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
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    raise NotImplementedError(
        "L3 is optional; implement compile_hybrid(hybrid_qasm_str) to enter"
    )
