#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This file intentionally contains no scoring implementation. Teams may implement
the functions directly or delegate to another language/runtime with subprocess.
"""

from typing import Any, Dict, List, Tuple
import re

from targets.braket import transpile_braket, run_braket
from targets.spinq import transpile_spinq, run_spinq
from targets.originq import transpile_originq, run_originq

from l2 import agent_chat as ac

import compiler

SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    target_lower = target.lower().strip()

    if target_lower == "braket":
        return transpile_braket(qasm_str)
    if target_lower == "spinq":
        return transpile_spinq(qasm_str)
    elif target_lower == "originq":
        return transpile_originq(qasm_str)
    else:
        raise ValueError(f"不支持的 target 后端: '{target}'")


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    target_lower = target.lower().strip()
    
    if target_lower == "braket":
        return run_braket(qasm_str, shots=shots)
    if target_lower == "spinq":
        return run_spinq(qasm_str, shots=shots)
    elif target_lower == "originq":
        return run_originq(qasm_str, shots=shots)
    else:
        raise ValueError(f"不支持的 target 后端: '{target}'")


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    return ac(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    return compiler.compile_hybrid(hybrid_qasm_str)
