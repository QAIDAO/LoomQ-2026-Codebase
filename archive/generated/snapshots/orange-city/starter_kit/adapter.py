#!/usr/bin/env python3
"""LoomQ submission adapter - unified transpiler, runner, agent and hybrid compiler."""

from typing import Any, Dict, List, Tuple

try:
    from agent import agent_chat as _agent_chat
    from backends import run as _run
    from hybrid_compiler import compile_hybrid as _compile_hybrid
    from transpilers import SUPPORTED_TARGETS, transpile as _transpile
except ImportError:
    try:
        from starter_kit.agent import agent_chat as _agent_chat
        from starter_kit.backends import run as _run
        from starter_kit.hybrid_compiler import compile_hybrid as _compile_hybrid
        from starter_kit.transpilers import SUPPORTED_TARGETS, transpile as _transpile
    except ImportError:
        from .agent import agent_chat as _agent_chat
        from .backends import run as _run
        from .hybrid_compiler import compile_hybrid as _compile_hybrid
        from .transpilers import SUPPORTED_TARGETS, transpile as _transpile


def transpile(qasm_str: str, target: str) -> str:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")
    return _transpile(qasm_str, target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")
    return _run(qasm_str, target, shots)


def agent_chat(prompt: str) -> str:
    return _agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    return _compile_hybrid(hybrid_qasm_str)
