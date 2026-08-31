"""Real SpinQit BasicSimulator runner."""

from __future__ import annotations

import hashlib
import os
import tempfile
import uuid

from ..compiler.ir import Circuit
from ..compiler.metrics import circuit_metrics
from ..emitters import emit_spinq
from .result import _state_value, build_result, remap_measured_qubits


def _extract_measured_spinq_counts(
    raw: dict, measured_qubits: list[int], qubit_count: int
) -> dict[str, int]:
    """Reduce SpinQit BasicSimulator keys to measurement-ordered keys.

    SpinQit reports every shot as a full-width key over ALL qubits (qubit 0 is
    the leftmost bit), including wires that are never measured. The shared
    remapper expects keys whose i-th bit is the value of ``measured_qubits[i]``,
    so extract exactly those bits. When every qubit is measured this is the
    identity mapping, preserving the previously working behavior.
    """
    reduced: dict[str, int] = {}
    for raw_key, count in raw.items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("count values must be non-negative integers")
        value = _state_value(raw_key, qubit_count)
        full = f"{value:0{qubit_count}b}"
        measured_key = "".join(full[qubit] for qubit in measured_qubits)
        reduced[measured_key] = reduced.get(measured_key, 0) + count
    return reduced


_IMPORT_ERROR: ImportError | None
try:
    from spinqit import BasicSimulatorConfig, get_basic_simulator, get_compiler  # type: ignore[import-untyped]
except ImportError as exc:  # pragma: no cover - exercised in clean-env diagnostics
    BasicSimulatorConfig = None
    get_basic_simulator = None
    get_compiler = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


def run_spinq(circuit: Circuit, shots: int) -> dict[str, object]:
    if _IMPORT_ERROR is not None:
        raise RuntimeError(
            "SpinQit is unavailable. Run .\\starter_kit\\scripts\\setup.ps1 in this repository, "
            "then launch with .\\starter_kit\\scripts\\run_web.ps1."
        ) from _IMPORT_ERROR
    source = emit_spinq(circuit)
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".qasm", delete=False, encoding="utf-8"
    )
    try:
        handle.write(source)
        handle.close()
        compiler = get_compiler("qasm")
        program = compiler.compile(handle.name, 0)
    finally:
        if not handle.closed:
            handle.close()
        os.unlink(handle.name)

    config = BasicSimulatorConfig()
    config.configure_shots(shots)
    result = get_basic_simulator().execute(program, config)
    measured_qubits = [measurement.qubit for measurement in circuit.measurements]
    reduced = _extract_measured_spinq_counts(
        result.counts, measured_qubits, circuit.qubit_count
    )
    counts = remap_measured_qubits(
        reduced,
        measured_qubits=measured_qubits,
        measurements=circuit.measurements,
        cbit_count=circuit.cbit_count,
    )
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
    job_id = f"spinq-local-{digest}-{uuid.uuid4().hex[:8]}"
    meta = {
        **circuit_metrics(circuit),
        "engine": "spinqit_basic_simulator",
        "qubits": circuit.qubit_count,
    }
    return build_result("spinq", job_id, shots, counts, circuit.cbit_count, meta)
