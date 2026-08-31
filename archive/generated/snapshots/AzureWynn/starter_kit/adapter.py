#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0 — thin entrypoints over backends.

Architecture:
  adapter.py   -> contract entrypoints (this file), delegates to factory
  backends.py  -> Strategy classes (spinq/originq/braket) + Factory registry
  qasm_parser.py -> shared OpenQASM 2.0 whitelist parser
  normalize.py -> unified little-endian result schema

The evaluator imports this module and calls transpile() / run(); per the rules
these must keep the documented signatures. L2/L3 entry points are optional.
"""

from typing import Any, Dict, List, Tuple

try:
    from .agent import agent_chat
except ImportError:
    from agent import agent_chat

try:
    from .hybrid import compile_hybrid as _compile_hybrid
except ImportError:
    from hybrid import compile_hybrid as _compile_hybrid

try:
    from .backends import get_backend, supported_targets
    from .normalize import result_payload
    from .qasm_parser import parse_qasm
except ImportError:
    from backends import get_backend, supported_targets
    from normalize import result_payload
    from qasm_parser import parse_qasm

SUPPORTED_TARGETS = supported_targets()


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    pc = parse_qasm(qasm_str)
    return get_backend(target).transpile(pc)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    pc = parse_qasm(qasm_str)
    backend = get_backend(target)
    raw = backend.run_raw(pc, shots)
    return result_payload(pc, backend.backend_id, shots, raw, backend.raw_is_big_endian)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """L3 entry point: return quantum operations and RISC-V assembly."""
    return _compile_hybrid(hybrid_qasm_str)