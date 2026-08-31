#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This file is the evaluator's entry point. All transpile/run logic
is delegated to the transpiler module.
"""

from typing import Any, Dict, List, Tuple

from . import transpiler
from . import engine
from . import agent
from . import compiler


SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    return transpiler.transpile(qasm_str, target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    return engine.run(qasm_str, target, shots)


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    return agent.agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """L3 entry point. Return quantum operations and RISC-V assembly."""
    return compiler.compile_hybrid(hybrid_qasm_str)
