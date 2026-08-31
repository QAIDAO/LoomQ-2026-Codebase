"""Backend runners for SpinQ / Braket / OriginQ simulators."""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .circuit import Circuit
from .emit import (
    emit_braket_native_qasm3,
    emit_braket_qasm3,
    emit_originir,
    emit_spinq_qasm2,
)
from .result import build_result, normalize_classical_counts, remap_counts, utc_now


def _measure_map(circuit: Circuit) -> Tuple[int, List[Tuple[int, int]]]:
    """Return the output width and the (qubit, cbit) pairs the circuit measures."""
    measured = [
        (circuit.qubit_index(op.qubit), circuit.cbit_index(op.cbit))
        for op in circuit.measure_ops()
    ]
    if measured:
        return circuit.n_clbits(), measured
    # An unmeasured circuit is reported as if every qubit mapped to its own bit.
    n = circuit.n_qubits()
    return n, [(index, index) for index in range(n)]


def _spinq_wants_cloud() -> bool:
    mode = (os.environ.get("LOOMQ_SPINQ_MODE") or "local").strip().lower()
    return mode in {"cloud", "qpu", "real", "nmr", "gemini"}


def _compile_spinq_qasm(qasm: str) -> Any:
    from spinqit import get_compiler

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".qasm", delete=False, encoding="utf-8"
    )
    try:
        tmp.write(qasm)
        tmp.close()
        return get_compiler("qasm").compile(tmp.name, 0)
    finally:
        os.unlink(tmp.name)


def _spinq_counts_from_result(result: Any, shots: int, n_bits: int) -> Dict[str, int]:
    raw = getattr(result, "counts", None)
    if raw:
        return {str(key): int(value) for key, value in dict(raw).items()}
    probs = getattr(result, "probabilities", None)
    if not probs:
        raise RuntimeError("spinqit result has neither counts nor probabilities")
    # Scale probabilities into integer counts that sum exactly to shots.
    items = [(str(key), float(value)) for key, value in dict(probs).items()]
    total_p = sum(max(0.0, p) for _, p in items) or 1.0
    scaled = [max(0.0, p) / total_p * shots for _, p in items]
    floors = [int(v) for v in scaled]
    remainders = sorted(
        ((scaled[i] - floors[i], i) for i in range(len(floors))), reverse=True
    )
    missing = shots - sum(floors)
    for _, index in remainders[:missing]:
        floors[index] += 1
    out: Dict[str, int] = {}
    for (key, _), count in zip(items, floors):
        if count:
            out[key.zfill(n_bits)[-n_bits:]] = count
    if sum(out.values()) != shots and out:
        # Last-resort fix if floating dust remains.
        first = next(iter(out))
        out[first] += shots - sum(out.values())
    return out


def run_spinq_cloud(circuit: Circuit, shots: int) -> Dict[str, Any]:
    """Submit to SpinQ Cloud when LOOMQ_SPINQ_MODE=cloud.

    Requires cloud.spinq.cn account + SSH key registered on the platform:
    LOOMQ_SPINQ_USERNAME, LOOMQ_SPINQ_KEYFILE (path to private key).
    Optional: LOOMQ_SPINQ_PLATFORM (default gemini_vp for 2-qubit NMR).
    """
    try:
        from spinqit import SpinQCloudConfig, get_spinq_cloud
    except ImportError as exc:
        raise ImportError(
            "spinqit is required for SpinQ cloud. "
            "Install with: pip install spinqit==0.2.4"
        ) from exc

    username = (os.environ.get("LOOMQ_SPINQ_USERNAME") or "").strip()
    keyfile = (os.environ.get("LOOMQ_SPINQ_KEYFILE") or "").strip()
    if not username or not keyfile:
        raise RuntimeError(
            "LOOMQ_SPINQ_MODE requests cloud but LOOMQ_SPINQ_USERNAME / "
            "LOOMQ_SPINQ_KEYFILE are not set. Register an SSH public key on "
            "https://cloud.spinq.cn and export the private key path."
        )
    if not os.path.isfile(keyfile):
        raise FileNotFoundError(f"LOOMQ_SPINQ_KEYFILE not found: {keyfile}")

    platform_name = (
        os.environ.get("LOOMQ_SPINQ_PLATFORM") or "gemini_vp"
    ).strip() or "gemini_vp"
    qasm = emit_spinq_qasm2(circuit)
    ir = _compile_spinq_qasm(qasm)

    host = (os.environ.get("LOOMQ_SPINQ_HOST") or "").strip() or None
    backend = (
        get_spinq_cloud(username, keyfile, host=host)
        if host
        else get_spinq_cloud(username, keyfile)
    )
    platform = backend.get_platform(platform_name)
    available = platform.available() if callable(getattr(platform, "available", None)) else getattr(platform, "available", False)
    if not available:
        raise RuntimeError(
            f"SpinQ platform {platform_name!r} is not available right now"
        )

    config = SpinQCloudConfig()
    config.configure_platform(platform_name)
    config.configure_shots(shots)
    task_name = os.environ.get("LOOMQ_SPINQ_TASK_NAME") or "loomq-bell"
    task_desc = os.environ.get("LOOMQ_SPINQ_TASK_DESC") or "LoomQ hardware evidence"
    config.configure_task(task_name, task_desc)

    result = backend.execute(ir, config)
    n_bits, measured = _measure_map(circuit)
    raw_counts = _spinq_counts_from_result(result, shots, n_bits)
    counts = remap_counts(
        raw_counts, n_bits=n_bits, n_qubits=circuit.n_qubits(), measured=measured
    )
    job_id = (
        getattr(result, "job_id", None)
        or getattr(result, "task_id", None)
        or getattr(result, "task_code", None)
        or os.environ.get("LOOMQ_SPINQ_JOB_ID")
        or f"spinq-cloud-{abs(hash(qasm)) % 10_000_000:07d}"
    )
    return build_result(
        backend="spinq_cloud_qpu",
        job_id=str(job_id),
        shots=shots,
        counts=counts,
        meta={
            "transpiled_gates": len(circuit.gate_ops()),
            "qubits": circuit.n_qubits(),
            "target_ir": "openqasm2",
            "platform": platform_name,
            "mode": "cloud",
        },
    )


def run_spinq_local(circuit: Circuit, shots: int) -> Dict[str, Any]:
    try:
        from spinqit import BasicSimulatorConfig, get_basic_simulator
    except ImportError as exc:
        raise ImportError(
            "spinqit is required for target=spinq. "
            "Install with: pip install spinqit==0.2.4"
        ) from exc

    qasm = emit_spinq_qasm2(circuit)
    ir = _compile_spinq_qasm(qasm)

    engine = get_basic_simulator()
    config = BasicSimulatorConfig()
    config.configure_shots(shots)
    result = engine.execute(ir, config)
    raw = getattr(result, "counts", None)
    if raw is None:
        raise RuntimeError("spinqit result has no counts")

    n_bits, measured = _measure_map(circuit)
    counts = remap_counts(
        raw, n_bits=n_bits, n_qubits=circuit.n_qubits(), measured=measured
    )
    job_id = (
        getattr(result, "job_id", None)
        or getattr(result, "task_id", None)
        or f"spinq-local-{abs(hash(qasm)) % 10_000_000:07d}"
    )
    return build_result(
        backend="spinq_basic_simulator",
        job_id=str(job_id),
        shots=shots,
        counts=counts,
        meta={
            "transpiled_gates": len(circuit.gate_ops()),
            "qubits": circuit.n_qubits(),
            "target_ir": "openqasm2",
        },
    )


def run_spinq(circuit: Circuit, shots: int) -> Dict[str, Any]:
    if _spinq_wants_cloud():
        return run_spinq_cloud(circuit, shots)
    return run_spinq_local(circuit, shots)


def run_braket(circuit: Circuit, shots: int) -> Dict[str, Any]:
    try:
        from braket.devices import LocalSimulator
        from braket.ir.openqasm import Program
    except ImportError as exc:
        raise ImportError(
            "amazon-braket-sdk is required for target=braket. "
            "Install with: pip install amazon-braket-sdk==1.50.0"
        ) from exc

    qasm3 = emit_braket_native_qasm3(circuit)
    device = LocalSimulator()
    program = Program(source=qasm3)
    task = device.run(program, shots=shots)
    result = task.result()
    n_bits, measured = _measure_map(circuit)
    counts = remap_counts(
        dict(result.measurement_counts),
        n_bits=n_bits,
        n_qubits=circuit.n_qubits(),
        measured=measured,
    )

    job_id = getattr(getattr(result, "task_metadata", None), "id", None) or f"braket-local-{abs(hash(qasm3)) % 10_000_000:07d}"
    timestamp = utc_now()
    try:
        start = result.additional_metadata.action.startTime
        if start is not None:
            timestamp = str(start)
    except Exception:  # noqa: BLE001
        pass

    return build_result(
        backend="braket_local_simulator",
        job_id=str(job_id),
        shots=shots,
        counts=counts,
        timestamp=timestamp,
        meta={
            "transpiled_gates": len(circuit.gate_ops()),
            "qubits": circuit.n_qubits(),
            "target_ir": "openqasm3",
        },
    )


def _originq_api_token() -> Optional[str]:
    return (
        os.environ.get("LOOMQ_ORIGINQ_API_KEY")
        or os.environ.get("ORIGINQ_API_KEY")
        or os.environ.get("QCLOUD_API_TOKEN")
        or ""
    ).strip() or None


def _originq_wants_cloud() -> bool:
    mode = (os.environ.get("LOOMQ_ORIGINQ_MODE") or "local").strip().lower()
    return mode in {"wukong", "cloud", "qpu", "real", "chip"}


# Live Wukong QPU is chipId 180. pyqpanda's real_chip_type.origin_72 still points
# at the retired 72-qubit resource; wrong/unknown chips often reply "under
# maintenance", which must not be read as a platform-wide outage.
ORIGINQ_DEFAULT_CHIP_ID = 180
ORIGINQ_CHIP_ALIASES = {
    "180": 180,
    "wk_c180": 180,
    "wk_c180_2": 180,
    "wukong": 180,
    "wukong_180": 180,
    "origin_wukong": 180,
    "origin_180": 180,
    "72": 72,
    "origin_72": 72,
    "wukong_72": 72,
}


def _resolve_originq_chip_id(chip_name: str, pq: Any) -> int:
    """Return the numeric chipId the OriginQ cloud API expects."""
    text = (chip_name or "").strip()
    if not text:
        return ORIGINQ_DEFAULT_CHIP_ID
    alias = ORIGINQ_CHIP_ALIASES.get(text) or ORIGINQ_CHIP_ALIASES.get(text.lower())
    if alias is not None:
        return alias
    try:
        return int(text)
    except ValueError:
        pass
    member = getattr(getattr(pq, "real_chip_type", None), text, None)
    if member is not None:
        return int(getattr(member, "value", member))
    raise ValueError(
        f"unknown OriginQ chip {chip_name!r}; use numeric chipId "
        f"(live Wukong is {ORIGINQ_DEFAULT_CHIP_ID}) or one of "
        f"{sorted(ORIGINQ_CHIP_ALIASES)}"
    )


def _probs_to_counts(raw: Mapping[Any, Any], shots: int, n_bits: int) -> Dict[str, int]:
    """Convert cloud probability maps (or already-integer counts) into shot counts."""
    items: List[Tuple[str, float]] = []
    for key, value in raw.items():
        bits = str(key).strip()
        cleaned = "".join(ch for ch in bits if ch in "01")
        if cleaned and set(bits.replace(" ", "")) <= {"0", "1"}:
            bitstring = cleaned.zfill(n_bits)[-n_bits:]
        elif str(key).isdigit():
            bitstring = format(int(key), f"0{n_bits}b")
        else:
            bitstring = cleaned.zfill(n_bits)[-n_bits:] if cleaned else bits
        items.append((bitstring, float(value)))

    total = sum(weight for _, weight in items)
    if total <= 0:
        raise ValueError("originq cloud returned empty measurement payload")

    # Values already look like shot counts.
    if abs(total - shots) <= max(1, shots * 0.01) and all(
        abs(weight - round(weight)) < 1e-6 for _, weight in items
    ):
        return normalize_classical_counts(
            {key: int(round(weight)) for key, weight in items}, n_bits
        )

    # Largest-remainder so the integers sum to shots exactly.
    scaled = [(key, weight / total * shots) for key, weight in items]
    floors = [(key, int(value)) for key, value in scaled]
    remainders = sorted(
        ((value - floor, key) for (key, value), (_, floor) in zip(scaled, floors)),
        reverse=True,
    )
    assigned = {key: floor for key, floor in floors}
    missing = shots - sum(assigned.values())
    for index in range(missing):
        assigned[remainders[index % len(remainders)][1]] += 1
    return normalize_classical_counts(assigned, n_bits)


def _qprog_from_qasm(pq: Any, machine: Any, qasm2: str) -> Any:
    converted = pq.convert_qasm_string_to_qprog(qasm2, machine)
    if isinstance(converted, (list, tuple)):
        return converted[0]
    return converted


def run_originq_local(circuit: Circuit, shots: int) -> Dict[str, Any]:
    try:
        import pyqpanda as pq
    except ImportError as exc:
        raise ImportError(
            "pyqpanda is required for target=originq. "
            "Install with: pip install pyqpanda"
        ) from exc

    # Feed OpenQASM 2 into pyqpanda; OriginIR remains what transpile() returns.
    # pyqpanda already returns classical little-endian keys that honour the
    # measure map, so remapping as if they were qubit-indexed would corrupt them.
    qasm2 = emit_spinq_qasm2(circuit)
    machine = pq.CPUQVM()
    machine.init_qvm()
    try:
        converted = pq.convert_qasm_string_to_qprog(qasm2, machine)
        if isinstance(converted, (list, tuple)) and len(converted) >= 3:
            prog, _qreg, creg = converted[0], converted[1], converted[2]
        elif isinstance(converted, (list, tuple)):
            prog = converted[0]
            creg = machine.get_allocate_cbits()
        else:
            prog = converted
            creg = machine.get_allocate_cbits()
        raw = machine.run_with_configuration(prog, creg, shots)
    finally:
        machine.finalize()

    n_bits, _measured = _measure_map(circuit)
    counts = normalize_classical_counts(raw, n_bits)
    return build_result(
        backend="originq_cpu_simulator",
        job_id=f"originq-sim-{abs(hash(qasm2)) % 10_000_000:07d}",
        shots=shots,
        counts=counts,
        meta={
            "transpiled_gates": len(circuit.gate_ops()),
            "qubits": circuit.n_qubits(),
            "target_ir": "originir",
            "originir_preview": emit_originir(circuit).splitlines()[:8],
        },
    )


def run_originq_wukong(circuit: Circuit, shots: int) -> Dict[str, Any]:
    """Submit to Origin Wukong via QCloud when LOOMQ_ORIGINQ_MODE=wukong."""
    token = _originq_api_token()
    if not token:
        raise RuntimeError(
            "LOOMQ_ORIGINQ_MODE requests the Wukong chip but no API key is set. "
            "Export LOOMQ_ORIGINQ_API_KEY (from console.originqc.com.cn API Key)."
        )
    try:
        import pyqpanda as pq
    except ImportError as exc:
        raise ImportError(
            "pyqpanda is required for OriginQ cloud execution. "
            "Install with: pip install pyqpanda"
        ) from exc

    qasm2 = emit_spinq_qasm2(circuit)
    originir = emit_originir(circuit)
    machine = pq.QCloud()
    # Do NOT call set_configure(72, 72): it can clear QCloud init state and make
    # later submits look like permanent "maintenance" (see public competitor notes).
    machine.init_qvm(token, False)
    chip_name = (os.environ.get("LOOMQ_ORIGINQ_CHIP") or str(ORIGINQ_DEFAULT_CHIP_ID)).strip()
    chip_id = _resolve_originq_chip_id(chip_name, pq)
    job_id = None
    raw: Any = None
    poll_errors: List[str] = []
    try:
        # Prefer OriginIR when the cloud accepts strings; fall back to QProg.
        payload: Any = originir
        try:
            if hasattr(machine, "async_real_chip_measure"):
                job_id = machine.async_real_chip_measure(
                    payload, shots, chip_id=chip_id, task_name="LoomQ-L1"
                )
            else:
                raw = machine.real_chip_measure(
                    payload, shots, chip_id=chip_id, task_name="LoomQ-L1"
                )
        except Exception as originir_exc:
            try:
                prog = _qprog_from_qasm(pq, machine, qasm2)
                if hasattr(machine, "async_real_chip_measure"):
                    job_id = machine.async_real_chip_measure(
                        prog, shots, chip_id=chip_id, task_name="LoomQ-L1"
                    )
                else:
                    raw = machine.real_chip_measure(
                        prog, shots, chip_id=chip_id, task_name="LoomQ-L1"
                    )
                    job_id = None
            except Exception as qprog_exc:
                raise RuntimeError(
                    "OriginQ Wukong submit failed for both OriginIR and QProg "
                    f"payloads (chip={chip_name!r} resolved_chip_id={chip_id!r}): "
                    f"originir={originir_exc!r}; qprog={qprog_exc!r}. "
                    "Wrong chipId often reports as 'under maintenance' — "
                    f"live Wukong is chipId={ORIGINQ_DEFAULT_CHIP_ID}."
                ) from qprog_exc

        if job_id is not None:
            # Poll the same job_id until finished. On timeout / SDK parse errors,
            # keep the id so the operator can query the console — never resubmit.
            raw = None
            status_fn = getattr(machine, "query_task_state_result", None)
            if status_fn is None:
                raise RuntimeError(
                    f"submitted Wukong task {job_id!r} but query_task_state_result is unavailable; "
                    "do not resubmit — open the console with this job_id"
                )
            import time

            deadline = time.time() + int(os.environ.get("LOOMQ_ORIGINQ_TIMEOUT_SEC", "1800"))
            poll = max(1.0, float(os.environ.get("LOOMQ_ORIGINQ_POLL_SEC", "2")))
            while time.time() < deadline:
                try:
                    state_payload = status_fn(str(job_id), True)
                except Exception as poll_exc:
                    # Old pyqpanda can choke on a harmless errorMessage beside a
                    # finished payload ("value is not string"). Keep polling; if
                    # we never decode, surface job_id for console / REST recovery.
                    poll_errors.append(repr(poll_exc))
                    time.sleep(poll)
                    continue
                if isinstance(state_payload, (tuple, list)) and len(state_payload) >= 2:
                    state, raw = state_payload[0], state_payload[1]
                    finished = getattr(getattr(pq.QCloud, "TaskStatus", object), "FINISHED", None)
                    finished_value = getattr(finished, "value", 3)
                    # Platform taskState 3 == finished (also returned as bare int).
                    if state == finished_value or state == 3 or raw:
                        break
                elif isinstance(state_payload, dict):
                    raw = state_payload
                    break
                time.sleep(poll)
            if raw is None:
                detail = "; ".join(poll_errors[-3:]) if poll_errors else "no result payload"
                raise TimeoutError(
                    f"OriginQ Wukong task {job_id} timed out or SDK failed to parse "
                    f"results ({detail}). Do NOT resubmit — open "
                    f"https://console.originqc.com.cn/ with job_id={job_id} "
                    f"(chip_id={chip_id})."
                )
    finally:
        if hasattr(machine, "finalize"):
            machine.finalize()

    n_bits, _measured = _measure_map(circuit)
    counts = _probs_to_counts(raw, shots, n_bits)
    return build_result(
        backend="originq_wukong",
        job_id=str(job_id or f"originq-wukong-{abs(hash(originir)) % 10_000_000:07d}"),
        shots=shots,
        counts=counts,
        meta={
            "transpiled_gates": len(circuit.gate_ops()),
            "qubits": circuit.n_qubits(),
            "target_ir": "originir",
            "chip": chip_name,
            "chip_id": chip_id,
            "mode": "wukong",
            "submitted_originir": originir,
            "submitted_qasm": qasm2,
        },
    )


def run_originq(circuit: Circuit, shots: int) -> Dict[str, Any]:
    if _originq_wants_cloud():
        return run_originq_wukong(circuit, shots)
    return run_originq_local(circuit, shots)


RUNNERS = {
    "spinq": run_spinq,
    "braket": run_braket,
    "originq": run_originq,
}


def run_backend(circuit: Circuit, target: str, shots: int) -> Dict[str, Any]:
    if target not in RUNNERS:
        raise ValueError(f"unsupported target '{target}'")
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive int")
    return RUNNERS[target](circuit, shots)
