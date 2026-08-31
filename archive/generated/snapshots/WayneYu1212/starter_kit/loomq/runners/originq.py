"""Real pyQPanda CPUQVM runner using the emitted OriginIR artifact."""

from __future__ import annotations

import hashlib
import uuid

from ..compiler.ir import Circuit
from ..compiler.metrics import circuit_metrics
from ..emitters import emit_originq
from .result import build_result


_IMPORT_ERROR: ImportError | None
try:
    import pyqpanda as pq  # type: ignore[import-untyped]
except ImportError as exc:  # pragma: no cover - exercised in clean-env diagnostics
    pq = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


def run_originq(circuit: Circuit, shots: int) -> dict[str, object]:
    if _IMPORT_ERROR is not None:
        raise RuntimeError(
            "pyQPanda is unavailable. Run .\\starter_kit\\scripts\\setup.ps1 in this repository, "
            "then launch with .\\starter_kit\\scripts\\run_web.ps1."
        ) from _IMPORT_ERROR
    source = emit_originq(circuit)
    machine = pq.CPUQVM()
    machine.init_qvm()
    try:
        program, _qubits, cbits = pq.convert_originir_str_to_qprog(source, machine)
        counts = machine.run_with_configuration(program, cbits, shots)
    finally:
        machine.finalize()
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
    job_id = f"originq-local-{digest}-{uuid.uuid4().hex[:8]}"
    meta = {
        **circuit_metrics(circuit),
        "engine": "pyqpanda_cpuqvm",
        "qubits": circuit.qubit_count,
    }
    return build_result("originq", job_id, shots, counts, circuit.cbit_count, meta)
