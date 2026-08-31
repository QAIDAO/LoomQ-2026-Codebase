"""Native local backend adapters with an explicit reference-simulator fallback."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import os
import tempfile
from typing import Any, Mapping

from .diagnostics import (
    acceptance_threshold,
    hellinger_fidelity,
    probe_bit_order,
)
from .pipeline import PipelineTrace, trace_transpilation
from .qasm import GateOperation, parse_openqasm2
from .simulator import (
    BACKEND_IDS,
    _operand_index,
    ideal_distribution,
    run_local,
)


class NativeBackendUnavailable(RuntimeError):
    """Raised only when an optional native SDK is not installed."""


def run(qasm_str: str, target: str, shots: int) -> dict[str, Any]:
    """Run on the requested native local simulator, or the bundled reference engine."""

    if target not in BACKEND_IDS:
        raise ValueError(f"Unsupported target: {target}")
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")

    pipeline = trace_transpilation(qasm_str, target)
    release = _release_mode()
    require_native = release or os.environ.get("LOOMQ_REQUIRE_NATIVE") == "1"
    if os.environ.get("LOOMQ_FORCE_REFERENCE_SIMULATOR") == "1":
        if release:
            raise RuntimeError("release mode forbids LOOMQ_FORCE_REFERENCE_SIMULATOR")
        return _reference_result(
            qasm_str,
            target,
            shots,
            pipeline=pipeline,
            fallback_reason="forced by LOOMQ_FORCE_REFERENCE_SIMULATOR",
        )
    try:
        if target == "spinq":
            native = _run_spinq(
                pipeline.runtime_ir, pipeline.canonical_qasm, shots, pipeline
            )
        elif target == "originq":
            native = _run_originq(
                pipeline.runtime_ir, pipeline.canonical_qasm, shots, pipeline
            )
        else:
            native = _run_braket(
                pipeline.runtime_ir, pipeline.canonical_qasm, shots, pipeline
            )
    except NativeBackendUnavailable as exc:
        if require_native:
            raise
        return _reference_result(
            qasm_str,
            target,
            shots,
            pipeline=pipeline,
            fallback_reason=str(exc),
        )

    checked, accepted = _diagnose_native_result(
        qasm_str,
        target,
        shots,
        native,
        pipeline,
    )
    if accepted:
        return checked
    diagnostic = dict(checked.get("meta", {}).get("acceptance", {}))
    if require_native:
        raise RuntimeError(
            f"{target} native result failed semantic acceptance: "
            f"fidelity={diagnostic.get('fidelity')}, "
            f"threshold={diagnostic.get('threshold')}"
        )
    fallback = _reference_result(
        qasm_str,
        target,
        shots,
        pipeline=pipeline,
        fallback_reason="native result fell below the semantic acceptance threshold",
    )
    fallback["meta"]["discarded_native"] = {
        "job_id": checked.get("job_id"),
        "executor": checked.get("meta", {}).get("executor"),
        "acceptance": diagnostic,
        "bit_order_probe": checked.get("meta", {}).get("bit_order_probe"),
    }
    return fallback


def _run_spinq(
    runtime_ir: str,
    canonical_qasm: str,
    shots: int,
    pipeline: PipelineTrace,
) -> dict[str, Any]:
    try:
        from spinqit import BasicSimulatorConfig, get_basic_simulator, get_compiler
    except ImportError as exc:
        raise NativeBackendUnavailable("spinqit is not installed") from exc

    program = parse_openqasm2(canonical_qasm)
    temporary_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".qasm", delete=False, encoding="utf-8"
        ) as temporary:
            temporary.write(runtime_ir)
            temporary_path = temporary.name
        ir = get_compiler("qasm").compile(temporary_path, 0)
    finally:
        if temporary_path:
            os.unlink(temporary_path)

    config = BasicSimulatorConfig()
    config.configure_shots(shots)
    result = get_basic_simulator().execute(ir, config)
    counts = _normalize_spinq_counts(result.counts, program)
    return _result(
        canonical_qasm,
        "spinq",
        shots,
        counts,
        getattr(result, "job_id", None) or getattr(result, "task_id", None),
        {
            "executor": "spinqit.BasicSimulator",
            "qubits": program.quantum_register.size,
            **_artifact_meta(pipeline),
        },
    )


def _run_originq(
    runtime_ir: str,
    canonical_qasm: str,
    shots: int,
    pipeline: PipelineTrace,
) -> dict[str, Any]:
    try:
        import pyqpanda as pq
    except ImportError as exc:
        raise NativeBackendUnavailable("pyqpanda is not installed") from exc

    program = parse_openqasm2(canonical_qasm)
    machine = pq.CPUQVM()
    machine.init_qvm()
    try:
        parsed = _parse_originir_runtime(pq, runtime_ir, machine)
        if not isinstance(parsed, (list, tuple)) or len(parsed) < 3:
            raise RuntimeError("PyQPanda OriginIR parser returned an invalid payload")
        qprog, _qreg, creg = parsed[:3]
        raw_counts = machine.run_with_configuration(qprog, creg, shots)
    finally:
        machine.finalize()
    counts = _normalize_counts(raw_counts, program.classical_register.size, reverse=False)
    return _result(
        canonical_qasm,
        "originq",
        shots,
        counts,
        None,
        {
            "executor": "pyqpanda.CPUQVM",
            "qubits": program.quantum_register.size,
            **_artifact_meta(pipeline),
        },
    )


def _run_braket(
    runtime_ir: str,
    canonical_qasm: str,
    shots: int,
    pipeline: PipelineTrace,
) -> dict[str, Any]:
    try:
        from braket.devices import LocalSimulator
        from braket.ir.openqasm import Program as OpenQASMProgram
    except ImportError as exc:
        raise NativeBackendUnavailable("amazon-braket-sdk is not installed") from exc

    program = parse_openqasm2(canonical_qasm)
    task = LocalSimulator().run(
        OpenQASMProgram(source=runtime_ir), shots=shots
    )
    result = task.result()
    measured_qubits = tuple(int(item) for item in result.measured_qubits)
    counts = _normalize_braket_counts(
        result.measurement_counts, measured_qubits, program
    )
    return _result(
        canonical_qasm,
        "braket",
        shots,
        counts,
        getattr(task, "id", None),
        {
            "executor": "braket.devices.LocalSimulator",
            "qubits": program.quantum_register.size,
            "measured_qubits": list(measured_qubits),
            **_artifact_meta(pipeline),
        },
    )


def _parse_originir_runtime(pq: Any, runtime_ir: str, machine: Any) -> Any:
    for name in (
        "convert_originir_string_to_qprog",
        "convert_originir_str_to_qprog",
    ):
        parser = getattr(pq, name, None)
        if parser is not None:
            return parser(runtime_ir, machine)
    parser = getattr(pq, "convert_originir_to_qprog", None)
    if parser is None:
        raise RuntimeError("installed PyQPanda exposes no OriginIR parser")
    temporary_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".originir", delete=False, encoding="utf-8"
        ) as temporary:
            temporary.write(runtime_ir)
            temporary_path = temporary.name
        return parser(temporary_path, machine)
    finally:
        if temporary_path:
            os.unlink(temporary_path)


def _artifact_meta(pipeline: PipelineTrace) -> dict[str, Any]:
    return {
        "executed_artifact": {
            "dialect": "runtime",
            "sha256": hashlib.sha256(
                pipeline.runtime_ir.encode("utf-8")
            ).hexdigest(),
            "characters": len(pipeline.runtime_ir),
        },
        "public_artifact": {
            "dialect": "target-ir-v1",
            "sha256": hashlib.sha256(
                pipeline.public_ir.encode("utf-8")
            ).hexdigest(),
            "characters": len(pipeline.public_ir),
        },
    }


def _release_mode() -> bool:
    return os.environ.get("LOOMQ_RELEASE_MODE", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _normalize_counts(
    raw_counts: Mapping[object, object], width: int, *, reverse: bool
) -> dict[str, int]:
    normalized: Counter[str] = Counter()
    for raw_key, raw_value in raw_counts.items():
        key = str(raw_key).replace(" ", "")
        if key and set(key) <= {"0", "1"} and len(key) <= width:
            bitstring = key.zfill(width)
        else:
            bitstring = format(int(raw_key), f"0{width}b")
        if reverse:
            bitstring = bitstring[::-1]
        normalized[bitstring] += int(raw_value)
    return dict(sorted(normalized.items()))


def _normalize_spinq_counts(
    raw_counts: Mapping[object, object], program: Any
) -> dict[str, int]:
    assignments: list[tuple[int, int]] = []
    for operation in program.operations:
        if isinstance(operation, GateOperation):
            continue
        if operation.source == program.quantum_register.name:
            assignments.extend(
                (index, index) for index in range(program.quantum_register.size)
            )
        else:
            assignments.append(
                (_operand_index(operation.source), _operand_index(operation.destination))
            )
    normalized: Counter[str] = Counter()
    for raw_key, raw_value in raw_counts.items():
        raw = str(raw_key).replace(" ", "").zfill(program.quantum_register.size)
        quantum = [int(raw[index]) for index in range(program.quantum_register.size)]
        classical = [0] * program.classical_register.size
        for quantum_index, classical_index in assignments:
            classical[classical_index] = quantum[quantum_index]
        bitstring = "".join(
            str(classical[index])
            for index in reversed(range(program.classical_register.size))
        )
        normalized[bitstring] += int(raw_value)
    return dict(sorted(normalized.items()))


def _normalize_braket_counts(
    raw_counts: Mapping[object, object],
    measured_qubits: tuple[int, ...],
    program: Any,
) -> dict[str, int]:
    if not measured_qubits:
        raise RuntimeError("Braket reported no measured qubits")
    assignments: list[tuple[int, int]] = []
    for operation in program.operations:
        if isinstance(operation, GateOperation):
            continue
        if operation.source == program.quantum_register.name:
            assignments.extend(
                (index, index) for index in range(program.quantum_register.size)
            )
        else:
            assignments.append(
                (_operand_index(operation.source), _operand_index(operation.destination))
            )
    normalized: Counter[str] = Counter()
    classical_count = program.classical_register.size
    for raw_key, raw_value in raw_counts.items():
        raw = str(raw_key).replace(" ", "")
        if len(raw) != len(measured_qubits) or set(raw) - {"0", "1"}:
            raise RuntimeError("Braket returned a malformed measurement key")
        quantum = {
            qubit: int(raw[index])
            for index, qubit in enumerate(measured_qubits)
        }
        classical = [0] * classical_count
        for qubit, classical_bit in assignments:
            if qubit not in quantum:
                raise RuntimeError(
                    f"Braket omitted measured qubit {qubit} from its result"
                )
            classical[classical_bit] = quantum[qubit]
        bitstring = "".join(
            str(classical[index]) for index in reversed(range(classical_count))
        )
        normalized[bitstring] += int(raw_value)
    return dict(sorted(normalized.items()))


def _result(
    qasm_str: str,
    target: str,
    shots: int,
    counts: dict[str, int],
    native_job_id: object,
    meta: dict[str, Any],
) -> dict[str, Any]:
    if sum(counts.values()) != shots:
        raise RuntimeError(f"{target} backend counts do not sum to shots")
    return {
        "backend": BACKEND_IDS[target],
        "job_id": str(native_job_id or _local_job_id(qasm_str, target, shots)),
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": _timestamp(),
        "meta": meta,
    }


def _diagnose_native_result(
    qasm_str: str,
    target: str,
    shots: int,
    result: dict[str, Any],
    pipeline: PipelineTrace,
) -> tuple[dict[str, Any], bool]:
    expected_artifact_sha256 = hashlib.sha256(
        pipeline.runtime_ir.encode("utf-8")
    ).hexdigest()
    executed = result.get("meta", {}).get("executed_artifact", {})
    if executed.get("sha256") != expected_artifact_sha256:
        raise RuntimeError(
            f"{target} runner did not attest the pipeline runtime artifact"
        )
    expected = ideal_distribution(qasm_str)
    corrected_counts, bit_probe = probe_bit_order(result["counts"], expected)
    observed = {
        state: count / shots for state, count in corrected_counts.items()
    }
    fidelity = hellinger_fidelity(observed, expected)
    threshold = acceptance_threshold(len(expected), shots)
    checked = dict(result)
    checked["counts"] = corrected_counts
    checked["bit_order"] = "little"
    meta = dict(result.get("meta", {}))
    meta["pipeline"] = pipeline.to_meta()
    meta["bit_order_probe"] = bit_probe.to_meta()
    meta["acceptance"] = {
        "metric": "hellinger-fidelity",
        "fidelity": round(fidelity, 9),
        "threshold": round(threshold, 9),
        "expected_outcomes": len(expected),
        "status": "accepted" if fidelity >= threshold else "rejected",
    }
    meta["target"] = target
    checked["meta"] = meta
    return checked, fidelity >= threshold


def _reference_result(
    qasm_str: str,
    target: str,
    shots: int,
    *,
    pipeline: PipelineTrace,
    fallback_reason: str,
) -> dict[str, Any]:
    result = run_local(qasm_str, target, shots)
    meta = result.setdefault("meta", {})
    meta["executor"] = "loomq.reference_statevector"
    meta["pipeline"] = pipeline.to_meta()
    meta["fallback"] = {
        "used": True,
        "reason": fallback_reason,
    }
    return result


def _local_job_id(qasm_str: str, target: str, shots: int) -> str:
    digest = hashlib.sha256(f"{qasm_str}\0{target}\0{shots}".encode("utf-8")).hexdigest()
    return f"local-{target}-{digest[:16]}"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
