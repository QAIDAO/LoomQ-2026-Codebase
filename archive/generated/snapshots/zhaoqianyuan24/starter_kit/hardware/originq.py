"""Origin Quantum Cloud / Wukong real-chip adapter."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Tuple

from .common import (
    HardwareInterfaceError,
    extract_counts,
    extract_job_id,
    measured_width,
    normalize_counts,
    positive_shots,
    required_env,
    standard_result,
)


def _call_with_signature_fallback(method: Any, variants: Tuple[tuple, ...]) -> Any:
    last_error: Exception | None = None
    for args in variants:
        try:
            return method(*args)
        except TypeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise HardwareInterfaceError("provider method has no supported signature")


def _cloud_machine(pq: Any) -> Any:
    for name in ("QCloudMachine", "QCloud"):
        constructor = getattr(pq, name, None)
        if callable(constructor):
            return constructor()
    raise HardwareInterfaceError(
        "installed pyqpanda does not expose QCloudMachine or QCloud"
    )


def _initialize(machine: Any, token: str) -> None:
    init_qvm = getattr(machine, "init_qvm", None)
    if callable(init_qvm):
        _call_with_signature_fallback(
            init_qvm,
            ((token, False), (token,)),
        )
        return

    init = getattr(machine, "init", None)
    if callable(init):
        _call_with_signature_fallback(
            init,
            ((token, False), (token,)),
        )
        return

    raise HardwareInterfaceError(
        "installed pyqpanda cloud machine has no init_qvm/init method"
    )


def _chip_type(pq: Any) -> Any:
    enum = getattr(pq, "real_chip_type", None)
    if enum is None:
        enum = getattr(pq, "RealChipType", None)
    if enum is None:
        raise HardwareInterfaceError(
            "installed pyqpanda does not expose real_chip_type/RealChipType"
        )

    requested = os.environ.get("LOOMQ_ORIGINQ_CHIP", "ORIGIN_72").strip()
    candidates = [
        requested,
        requested.lower(),
        requested.upper(),
        "ORIGIN_72",
        "origin_72",
        "origin_wukong",
        "origin_wuyuan_d4",
    ]
    members = {name.lower(): name for name in dir(enum)}
    for candidate in candidates:
        actual_name = members.get(candidate.lower())
        if actual_name is not None:
            return getattr(enum, actual_name)
    raise HardwareInterfaceError(
        f"cannot find OriginQ chip enum {requested!r}; "
        f"available values include: {', '.join(sorted(members))}"
    )


def _build_program(machine: Any, pq: Any, qasm_str: str) -> tuple[Any, Any]:
    try:
        try:
            from ..l1.backends.originq import build_originq_gate
            from ..l1.ir import Gate, Measurement
            from ..l1.parser import parse_qasm2
        except ImportError:
            # Product Service may import adapter from inside starter_kit/.
            from l1.backends.originq import build_originq_gate
            from l1.ir import Gate, Measurement
            from l1.parser import parse_qasm2
    except ImportError as exc:
        raise HardwareInterfaceError("cannot load the LoomQ OriginQ IR adapter") from exc

    circuit = parse_qasm2(qasm_str)
    qubits = machine.qAlloc_many(circuit.num_qubits)
    cbits = machine.cAlloc_many(circuit.num_clbits)
    program = pq.QProg()
    for operation in circuit.operations:
        if isinstance(operation, Gate):
            program << build_originq_gate(operation, qubits)
        elif isinstance(operation, Measurement):
            program << pq.Measure(
                qubits[operation.qubit_idx],
                cbits[operation.cbit_idx],
            )
        else:
            raise HardwareInterfaceError(
                f"unsupported OriginQ operation: {type(operation).__name__}"
            )
    return circuit, program


def _status_and_payload(value: Any) -> tuple[Any, Any]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return value[0], value[1]
    if isinstance(value, dict):
        status = value.get("status", value.get("taskStatus"))
        payload = value.get("result", value.get("data", value))
        return status, payload
    return None, value


def _is_finished(status: Any) -> bool:
    if isinstance(status, str):
        return status.strip().lower() in {
            "3",
            "finished",
            "completed",
            "success",
            "succeeded",
            "done",
        }
    return status == 3


def _is_failed(status: Any) -> bool:
    if isinstance(status, str):
        return status.strip().lower() in {
            "4",
            "failed",
            "error",
            "cancelled",
            "canceled",
        }
    return status in {4, 7, 8}


def _wait_for_origin_result(machine: Any, task_id: str) -> Any:
    query = getattr(machine, "query_task_state_result", None)
    if not callable(query):
        query = getattr(machine, "query_state_result", None)
    if not callable(query):
        raise HardwareInterfaceError(
            "OriginQ async task was created, but the installed SDK has no "
            "query_task_state_result/query_state_result method"
        )

    timeout = float(os.environ.get("LOOMQ_ORIGINQ_TIMEOUT_SECONDS", "3600"))
    interval = float(os.environ.get("LOOMQ_ORIGINQ_POLL_SECONDS", "2"))
    deadline = time.monotonic() + max(1.0, timeout)
    while time.monotonic() < deadline:
        response = query(task_id)
        status, payload = _status_and_payload(response)
        if _is_failed(status):
            raise HardwareInterfaceError(f"OriginQ task {task_id} failed with status {status}")
        if _is_finished(status):
            return payload
        try:
            extract_counts(payload)
            return payload
        except HardwareInterfaceError:
            time.sleep(max(0.1, interval))
    raise HardwareInterfaceError(
        f"OriginQ task {task_id} did not finish within {timeout:g} seconds"
    )


def run_originq_wukong(
    qasm_str: str,
    shots: int,
    *,
    task_name: str = "LoomQ experiment",
) -> Dict[str, Any]:
    """Submit a measured circuit to OriginQ's Wukong real chip."""

    positive_shots(shots)
    token = required_env("LOOMQ_ORIGINQ_API_TOKEN")
    try:
        import pyqpanda as pq
    except ImportError as exc:
        raise HardwareInterfaceError(
            "OriginQ remote support requires pyqpanda; install the pinned "
            "requirements.txt in the Python 3.10 environment"
        ) from exc

    machine = _cloud_machine(pq)
    task_id: str | None = None
    used_async = False
    try:
        _initialize(machine, token)
        circuit, program = _build_program(machine, pq, qasm_str)
        chip = _chip_type(pq)

        async_measure = getattr(machine, "async_real_chip_measure", None)
        if callable(async_measure):
            task_id = _call_with_signature_fallback(
                async_measure,
                (
                    (program, shots, chip, True, True, True, task_name),
                    (program, shots, chip, True, True, True),
                    (program, shots, chip),
                ),
            )
            task_id = extract_job_id(task_id) or str(task_id)
            raw_result = _wait_for_origin_result(machine, task_id)
            used_async = True
        else:
            sync_measure = getattr(machine, "real_chip_measure", None)
            if not callable(sync_measure):
                raise HardwareInterfaceError(
                    "installed pyqpanda cloud machine exposes neither "
                    "async_real_chip_measure nor real_chip_measure"
                )
            raw_result = _call_with_signature_fallback(
                sync_measure,
                (
                    (program, shots, chip, True, True, True, task_name),
                    (program, shots, chip, True, True, True),
                    (program, shots, chip),
                ),
            )
            task_id = extract_job_id(raw_result)
            if not task_id:
                task_id = os.environ.get("LOOMQ_ORIGINQ_JOB_ID", "").strip() or None

        counts = extract_counts(raw_result)
        normalized = normalize_counts(
            counts,
            width=measured_width(circuit),
            shots=shots,
        )
        if not task_id:
            raise HardwareInterfaceError(
                "OriginQ returned a result without a traceable job ID; "
                "use the async SDK or set LOOMQ_ORIGINQ_JOB_ID after recording "
                "the provider task ID"
            )
        return standard_result(
            backend="originq_wukong",
            job_id=task_id,
            shots=shots,
            counts=normalized,
            meta={
                "provider": "originq",
                "chip": os.environ.get("LOOMQ_ORIGINQ_CHIP", "ORIGIN_72"),
                "task_name": task_name,
                "async": used_async,
                "job_id_traceable": True,
            },
        )
    finally:
        finalize = getattr(machine, "finalize", None)
        if callable(finalize):
            finalize()
