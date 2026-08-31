#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

All public entry points delegate to the same typed intermediate representation.
There are no target-specific source parsers and no sample-specific result paths.
"""

from typing import Any, Dict, List, Tuple

try:  # Package import from the repository root.
    from .loomq.agent import chat as _agent_chat
    from .loomq.emitters import emit_target
    from .loomq.hybrid import compile_hybrid_program
    from .loomq.ir import parse_qasm2
    from .loomq.pipeline import verified_run
except ImportError:  # Direct evaluator.py execution from starter_kit/.
    from loomq.agent import chat as _agent_chat
    from loomq.emitters import emit_target
    from loomq.hybrid import compile_hybrid_program
    from loomq.ir import parse_qasm2
    from loomq.pipeline import verified_run


SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    circuit = parse_qasm2(qasm_str)
    return emit_target(circuit, target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Certify, independently reparse, and execute the emitted target program."""
    result, _ = verified_run(qasm_str, target, shots)
    return result


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    return _agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    return compile_hybrid_program(hybrid_qasm_str)
