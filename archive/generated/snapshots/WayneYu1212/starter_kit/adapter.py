#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This file intentionally contains no scoring implementation. Teams may implement
the functions directly or delegate to another language/runtime with subprocess.
"""

import importlib
from typing import Any, Dict, List, Tuple

_PREFIX = "starter_kit." if __package__ == "starter_kit" else ""
_agent_service = importlib.import_module(_PREFIX + "loomq.agent.service")
_parser = importlib.import_module(_PREFIX + "loomq.compiler.parser")
_emitters = importlib.import_module(_PREFIX + "loomq.emitters")
_hybrid = importlib.import_module(_PREFIX + "loomq.hybrid")
_runners = importlib.import_module(_PREFIX + "loomq.runners")

SUPPORTED_TARGETS = _emitters.SUPPORTED_TARGETS


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")
    return _emitters.emit(_parser.parse_qasm(qasm_str), target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    return _runners.run_circuit(_parser.parse_qasm(qasm_str), target, shots)


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    return _agent_service.agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Compile Hybrid-QASM into ordered quantum operations and stock RISC-V."""
    return _hybrid.compile_hybrid(hybrid_qasm_str)
