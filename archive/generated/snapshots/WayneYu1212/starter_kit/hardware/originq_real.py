#!/usr/bin/env python3
"""Submit and preserve a traceable Origin Quantum real-chip Bell task."""

from __future__ import annotations

import argparse
import os
import time
from typing import Any

from starter_kit.hardware.common import (
    BELL_QASM2, normalize_distribution, normalized_result, package_version,
    save_completed_evidence, utc_now,
)


def configuration() -> dict[str, Any]:
    return {
        "token_configured": bool(os.environ.get("LOOMQ_ORIGINQ_TOKEN")),
        "chip_id": int(os.environ.get("LOOMQ_ORIGINQ_CHIP_ID", "72")),
        "device_name": os.environ.get("LOOMQ_ORIGINQ_DEVICE_NAME", "Origin Wukong / chip 72"),
    }


def doctor() -> int:
    config = configuration()
    try:
        import pyqpanda as pq
        async_available = hasattr(pq.QCloud, "async_real_chip_measure") and hasattr(pq.QCloud, "query_task_state_result")
    except ImportError:
        async_available = False
    print(f"pyqpanda={package_version('pyqpanda')}")
    print(f"token_configured={str(config['token_configured']).lower()}")
    print(f"async_traceable_api={str(async_available).lower()}")
    print(f"chip_id={config['chip_id']}")
    return 0 if config["token_configured"] and async_available else 2


def submit(*, shots: int, timeout: int, poll_interval: int, confirm: bool) -> dict[str, str]:
    token = os.environ.get("LOOMQ_ORIGINQ_TOKEN")
    if not token:
        raise RuntimeError("LOOMQ_ORIGINQ_TOKEN is not configured locally")
    if not confirm:
        raise RuntimeError("real hardware submission requires --confirm-real-hardware")
    import pyqpanda as pq

    config = configuration()
    cloud = pq.QCloud()
    submitted_at = utc_now()
    cloud.init_qvm(token, enable_logging=False)
    try:
        qubits = cloud.qAlloc_many(2)
        cbits = cloud.cAlloc_many(2)
        program = pq.QProg()
        program << pq.H(qubits[0]) << pq.CNOT(qubits[0], qubits[1])
        program << pq.Measure(qubits[0], cbits[0]) << pq.Measure(qubits[1], cbits[1])
        task_id = str(
            cloud.async_real_chip_measure(
                program,
                shots,
                chip_id=config["chip_id"],
                task_name="LoomQ",
            )
        )
        if not task_id:
            raise RuntimeError("Origin Quantum returned no traceable task ID")
        print(f"task_id={task_id}")
        deadline = time.monotonic() + timeout
        final_response: Any | None = None
        while time.monotonic() < deadline:
            response = cloud.query_task_state_result(task_id, True)
            status = int(response[0])
            if status == cloud.TaskStatus.FINISHED.value:
                final_response = response
                break
            if status == cloud.TaskStatus.FAILED.value:
                raise RuntimeError(f"Origin Quantum task failed: {task_id}")
            time.sleep(poll_interval)
        if final_response is None:
            raise TimeoutError(f"Origin Quantum task did not finish within {timeout}s: {task_id}")
        distribution = final_response[1]
        counts, source_kind = normalize_distribution(distribution, shots)
        completed_at = utc_now()
        result = normalized_result(
            provider="originq", backend="originq_real_qpu", job_id=task_id, shots=shots,
            counts=counts, submitted_at=submitted_at, completed_at=completed_at,
            device=config["device_name"], source_kind=source_kind,
        )
        return save_completed_evidence(
            provider="originq", qasm=BELL_QASM2,
            raw={"task_id": task_id, "sdk_response": final_response}, result=result,
            metadata={
                "provider": "originq", "platform": "Origin Quantum Cloud",
                "device": config["device_name"], "chip_id": config["chip_id"],
                "job_id": task_id, "shots": shots, "submitted_at": submitted_at,
                "completed_at": completed_at, "sdk_versions": {"pyqpanda": package_version("pyqpanda")},
                "command": "python -m starter_kit.hardware.originq_real --confirm-real-hardware",
            },
        )
    finally:
        cloud.finalize()


def main() -> int:
    parser = argparse.ArgumentParser(description="Origin Quantum real-chip Bell evidence runner")
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-real-hardware", action="store_true")
    parser.add_argument("--shots", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--poll-interval", type=int, default=10)
    args = parser.parse_args()
    if args.doctor:
        return doctor()
    if args.shots <= 0 or args.timeout <= 0 or args.poll_interval <= 0:
        raise SystemExit("shots, timeout, and poll interval must be positive")
    config = configuration()
    if args.dry_run:
        print(f"provider=originq\ndevice={config['device_name']}\nchip_id={config['chip_id']}\nshots={args.shots}\nwill_submit=false")
        return 0
    paths = submit(
        shots=args.shots, timeout=args.timeout, poll_interval=args.poll_interval,
        confirm=args.confirm_real_hardware,
    )
    for name, path in paths.items():
        print(f"{name}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
