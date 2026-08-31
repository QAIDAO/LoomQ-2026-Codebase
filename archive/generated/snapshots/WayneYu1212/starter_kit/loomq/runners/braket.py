"""Real Amazon Braket LocalSimulator runner."""

from __future__ import annotations

from ..compiler.ir import Circuit
from ..compiler.metrics import circuit_metrics
from ..emitters import emit_braket
from .result import build_result, remap_measured_qubits


_IMPORT_ERROR: ImportError | None
try:
    from braket.devices import LocalSimulator  # type: ignore[import-untyped]
    from braket.ir.openqasm import Program  # type: ignore[import-untyped]
except ImportError as exc:  # pragma: no cover - exercised in clean-env diagnostics
    LocalSimulator = None
    Program = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


def run_braket(circuit: Circuit, shots: int) -> dict[str, object]:
    if _IMPORT_ERROR is not None:
        raise RuntimeError(
            "Amazon Braket SDK is unavailable. Run .\\starter_kit\\scripts\\setup.ps1 in this repository, "
            "then launch with .\\starter_kit\\scripts\\run_web.ps1."
        ) from _IMPORT_ERROR
    source = emit_braket(circuit)
    executable_source = source.replace('include "stdgates.inc";\n', "", 1)
    task = LocalSimulator().run(Program(source=executable_source), shots=shots)
    result = task.result()
    counts = remap_measured_qubits(
        result.measurement_counts,
        measured_qubits=list(result.measured_qubits),
        measurements=circuit.measurements,
        cbit_count=circuit.cbit_count,
    )
    meta = {
        **circuit_metrics(circuit),
        "engine": "braket_local_simulator",
        "qubits": circuit.qubit_count,
    }
    return build_result(
        "braket",
        str(result.task_metadata.id),
        shots,
        counts,
        circuit.cbit_count,
        meta,
    )
