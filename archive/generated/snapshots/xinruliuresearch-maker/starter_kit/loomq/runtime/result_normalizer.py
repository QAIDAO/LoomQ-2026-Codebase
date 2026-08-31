"""Unified result-schema construction with honest execution metadata."""

from datetime import datetime, timezone
from typing import Any, Dict


BACKEND_IDS = {
    "spinq": "loomq_reference_statevector_spinq",
    "originq": "loomq_reference_statevector_originq",
    "braket": "loomq_reference_statevector_braket",
}


def build_result(
    target: str,
    shots: int,
    counts: Dict[str, int],
    digest: str,
    circuit: Any,
) -> Dict[str, Any]:
    return {
        "backend": BACKEND_IDS[target],
        "job_id": "local-sim-%s-%s" % (target, digest[:16]),
        "shots": shots,
        "counts": dict(sorted(counts.items())),
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "meta": {
            "execution_mode": "local_simulator",
            "execution_engine": "loomq_reference_statevector",
            "native_sdk_used": False,
            "qubits": circuit.qubit_count,
            "classical_bits": circuit.classical_count,
            "operation_count": len(circuit.operations),
            "input_sha256": digest,
        },
    }
