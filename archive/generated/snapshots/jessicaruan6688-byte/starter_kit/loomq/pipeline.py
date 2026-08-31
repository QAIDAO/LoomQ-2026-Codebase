"""High-level transpile / run pipeline."""

from __future__ import annotations

from typing import Any, Dict

from .backends import run_backend
from .emit import emit
from .parse_qasm import parse_qasm

SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile_circuit(qasm_str: str, target: str) -> str:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            f"unsupported target '{target}', expected one of {SUPPORTED_TARGETS}"
        )
    circuit = parse_qasm(qasm_str)
    return emit(circuit, target)


def run_circuit(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            f"unsupported target '{target}', expected one of {SUPPORTED_TARGETS}"
        )
    circuit = parse_qasm(qasm_str)
    return run_backend(circuit, target, shots)
