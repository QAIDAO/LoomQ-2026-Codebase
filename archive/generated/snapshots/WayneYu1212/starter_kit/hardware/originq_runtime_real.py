#!/usr/bin/env python3
"""Submit and preserve a traceable Origin Quantum real-chip task via the
official QPanda3 Runtime (qpanda3_runtime) API.

This runner is the modern replacement for the legacy ``originq_real.py``
path. The legacy ``pyqpanda.QCloud`` gateway (``chip_id=72``) returned
"Quantum computer under maintenance" for the current Origin Wukong 180-2
QPU, so this module uses the official ``qpanda3_runtime.RuntimeService``
against device id ``WK_C180_2``.

IMPORTANT (compatibility workaround): the high-level ``RuntimeService.sample()``
returned ``None`` on this machine for QPanda3 Runtime 1.0.2. This module
therefore uses the lower-level ``circuit_chunking_submit`` + ``query_task``
flow. This is an explicit compatibility workaround, not the standard
high-level official flow.

This dependency is OPTIONAL and isolated from the core evaluator:
install via ``requirements-originq-runtime.txt`` only when reproducing the
Origin Wukong Runtime path.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

from starter_kit.hardware.common import (
    BELL_QASM2, normalize_distribution, normalized_result, package_version,
    save_completed_evidence, utc_now,
)

DEFAULT_DEVICE_ID = os.environ.get("LOOMQ_ORIGINQ_DEVICE_ID", "WK_C180_2")
DEFAULT_PHYSICAL_BLOCK = [49, 58]  # same physical qubits as the 2026-08-20 canonical success


def _to_counts_map(result: Any) -> dict[str, float]:
    """Convert a QPanda3 Runtime sample result into a {bitstring: probability} map.

    The SDK returns either a plain {key: value} dict or the array form
    {"key": [...], "value": [...]} where keys are hex strings like "0x0".
    """
    if isinstance(result, dict) and "key" in result and "value" in result:
        return {
            str(int(k, 16)): float(v)
            for k, v in zip(result["key"], result["value"])
        }
    if isinstance(result, dict):
        return {str(k): float(v) for k, v in result.items()}
    raise ValueError(f"unexpected OriginQ sample result type: {type(result)!r}")


def configuration() -> dict[str, Any]:
    return {
        "token_configured": bool(os.environ.get("LOOMQ_ORIGINQ_TOKEN")),
        "device_id": DEFAULT_DEVICE_ID,
        "device_name": "Origin Wukong 180-2",
        "physical_block": list(DEFAULT_PHYSICAL_BLOCK),
    }


def doctor() -> int:
    config = configuration()
    try:
        import qpanda3_runtime  # type: ignore[import-untyped]  # noqa: F401
        import pyqpanda3  # type: ignore[import-untyped]  # noqa: F401
        runtime_available = True
    except ImportError:
        runtime_available = False
    print(f"qpanda3_runtime={package_version('qpanda3_runtime')}")
    print(f"pyqpanda3={package_version('pyqpanda3')}")
    print(f"token_configured={str(config['token_configured']).lower()}")
    print(f"runtime_available={str(runtime_available).lower()}")
    print(f"device_id={config['device_id']}")
    print(f"physical_block={config['physical_block']}")
    return 0 if config["token_configured"] and runtime_available else 2


def submit(*, shots: int, timeout: int, poll_interval: int, confirm: bool) -> dict[str, str]:
    token = os.environ.get("LOOMQ_ORIGINQ_TOKEN")
    if not token:
        raise RuntimeError("LOOMQ_ORIGINQ_TOKEN is not configured locally")
    if not confirm:
        raise RuntimeError("real hardware submission requires --confirm-real-hardware")
    import pyqpanda3 as _pq3  # type: ignore[import-untyped]
    from qpanda3_runtime import RuntimeService  # type: ignore[import-untyped]
    pq3: Any = _pq3

    config = configuration()
    service = RuntimeService()
    submitted_at = utc_now()
    service.login(token, channel="qcloud")
    try:
        device = service.device(config["device_id"], channel="qcloud")
        circuit = pq3.core.QCircuit()
        circuit << pq3.core.H(0) << pq3.core.CNOT(0, 1)
        # Compatibility workaround (QP3 Runtime 1.0.2): lower-level flow.
        ir_list = RuntimeService._preprocess_circuits(
            circuit, update_measure_qubits=[0, 1], specified_block=config["physical_block"]
        )
        task_msg = service._chip_sample_task_msg
        task_msg.build(
            progs=[], chip_id=device.chip_id(), shot=shots,
            is_amend=True, is_mapping=True, is_optimization=True,
            specified_block=config["physical_block"], priority=0, point_label=0,
            token=service.tokens["qcloud"], task_describe="LoomQ-repro",
        )
        resp = service._request_worker.circuit_chunking_submit(
            "qcloud", ir_list, task_msg.msg_dict(), "sample",
            max_byte_num_per_packet=1000, max_cir_num_per_packet=10,
        )
        task_ids = [r["taskId"] for r in resp if isinstance(r, dict) and r.get("taskId")]
        if not task_ids:
            raise RuntimeError(f"Origin Quantum Runtime returned no task ID: {resp!r}")
        task_id = task_ids[0]
        print(f"task_id={task_id}")
        deadline = time.monotonic() + timeout
        final: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            qres = service.query_task("qcloud", [task_id], using_http=True, timeout=60)
            item = qres[0] if qres else {}
            status = item.get("task_status", "Unknown")
            if status == "finished":
                final = item
                break
            if status in ("failed", "canceled"):
                raise RuntimeError(f"Origin Quantum Runtime task failed: {task_id} ({status})")
            time.sleep(poll_interval)
        if final is None:
            raise TimeoutError(f"Origin Quantum Runtime task did not finish within {timeout}s: {task_id}")
        tr = final.get("taskResult")
        distribution = json.loads(tr[0]) if tr else None
        counts_map = _to_counts_map(distribution)
        counts, source_kind = normalize_distribution(counts_map, shots, width=2)
        completed_at = utc_now()
        result = normalized_result(
            provider="originq", backend="originq_wukong_180_2_real_qpu", job_id=task_id,
            shots=shots, counts=counts, submitted_at=submitted_at,
            completed_at=completed_at, device=config["device_name"],
            source_kind=source_kind,
        )
        return save_completed_evidence(
            provider="originq_runtime_bell", qasm=BELL_QASM2,
            raw={"task_id": task_id, "sdk_response": final}, result=result,
            metadata={
                "provider": "originq", "platform": "Origin Quantum Cloud (QP3 Runtime)",
                "device_id": config["device_id"], "device": config["device_name"],
                "physical_qubits": config["physical_block"], "job_id": task_id,
                "shots": shots, "submitted_at": submitted_at, "completed_at": completed_at,
                "sdk_versions": {
                    "qpanda3_runtime": package_version("qpanda3_runtime"),
                    "pyqpanda3": package_version("pyqpanda3"),
                },
                "api_path": "qpanda3_runtime.RuntimeService / circuit_chunking_submit + query_task",
                "compatibility_workaround": "high-level sample() returned None on QP3 Runtime 1.0.2; lower-level circuit_chunking_submit/query_task used",
                "command": "python -m starter_kit.hardware.originq_runtime_real --confirm-real-hardware",
            },
        )
    finally:
        service.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Origin Quantum Runtime real-chip Bell evidence runner")
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
        print(
            f"provider=originq_runtime\ndevice={config['device_name']}\n"
            f"device_id={config['device_id']}\nshots={args.shots}\nwill_submit=false"
        )
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
