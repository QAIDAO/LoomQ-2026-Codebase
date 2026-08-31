"""Application services for transpilation and local execution."""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict

from .qasm2 import parse_qasm2
from .renderers import RENDERERS
from .simulator import circuit_depth, simulate_counts


SUPPORTED_TARGETS = tuple(RENDERERS)


def transpile_circuit(qasm_source: str, target: str) -> str:
    normalized_target = _target(target)
    return RENDERERS[normalized_target](parse_qasm2(qasm_source))


def execute(qasm_source: str, target: str, shots: int) -> Dict[str, Any]:
    normalized_target = _target(target)
    circuit = parse_qasm2(qasm_source)
    digest = hashlib.sha256(
        (normalized_target + "\0" + str(shots) + "\0" + qasm_source).encode("utf-8")
    ).hexdigest()[:20]
    return {
        "backend": f"loomq-{normalized_target}-local-simulator",
        "job_id": f"local-{digest}",
        "shots": shots,
        "counts": simulate_counts(circuit, shots),
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "meta": {
            "target": normalized_target,
            "qubits": circuit.qubit_count,
            "gate_count": len(circuit.operations),
            "depth": circuit_depth(circuit),
            "executor": "statevector",
        },
    }


def _target(target: str) -> str:
    if not isinstance(target, str):
        raise ValueError("target must be a string")
    normalized = target.strip().lower()
    if normalized not in RENDERERS:
        raise ValueError(f"Unsupported target: {target}")
    return normalized
