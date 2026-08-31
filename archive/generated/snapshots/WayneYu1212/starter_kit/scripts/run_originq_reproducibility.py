#!/usr/bin/env python3
"""Run repeated real OriginQ Wukong 180-2 Bell jobs for reproducibility evidence.

This script submits the SAME Bell circuit (device WK_C180_2, physical qubits [49,58],
shots=1000) that reproduces the canonical accepted job D0C7F490B43D9B04FDF19ABF3DB8B342,
via the modern QPanda3 Runtime API, and appends each new real result to an INDEPENDENT
reproducibility file. It NEVER touches the existing originq-hardware-* evidence files.

Usage:
    $env:LOOMQ_ORIGINQ_TOKEN = "<token>"   # keep local, never paste into chat
    python starter_kit/scripts/run_originq_reproducibility.py --target-runs 5

No token, Authorization, cookie, account, phone, or API key is ever recorded.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from starter_kit.hardware.common import normalize_distribution, utc_now
from starter_kit.hardware.originq_runtime_real import _to_counts_map

STARTER_ROOT = REPO_ROOT / "starter_kit"
SUMMARY_PATH = STARTER_ROOT / "evidence" / "files" / "originq-reproducibility-summary.json"
CIRCUIT_SHA256 = "7e8c1c09ba2d68afac59b1af854bffec6e92409ca02b83d71a029676a1ceff7f"

DEVICE_ID = os.environ.get("LOOMQ_ORIGINQ_DEVICE_ID", "WK_C180_2")
QUBITS = [49, 58]
BELL_QASM2 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
"""


def _load_summary() -> dict:
    if SUMMARY_PATH.exists():
        return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    return {
        "provider": "originq",
        "device": "Origin Wukong 180-2",
        "circuit_kind": "bell",
        "circuit_sha256": CIRCUIT_SHA256,
        "circuit_source": "evidence/files/originq-hardware-bell.qasm",
        "runs": [],
        "summary": {},
    }


def _submit_one(shots: int, timeout: int, poll_interval: int) -> dict:
    token = os.environ.get("LOOMQ_ORIGINQ_TOKEN")
    if not token:
        raise RuntimeError("LOOMQ_ORIGINQ_TOKEN not configured")
    import pyqpanda3 as pq3
    from qpanda3_runtime import RuntimeService

    submitted_at = utc_now()
    service = RuntimeService()
    service.login(token, channel="qcloud")
    try:
        device = service.device(DEVICE_ID, channel="qcloud")
        circuit = pq3.core.QCircuit()
        circuit << pq3.core.H(0) << pq3.core.CNOT(0, 1)
        ir_list = RuntimeService._preprocess_circuits(
            circuit, update_measure_qubits=[0, 1], specified_block=QUBITS
        )
        task_msg = service._chip_sample_task_msg
        task_msg.build(
            progs=[], chip_id=device.chip_id(), shot=shots,
            is_amend=True, is_mapping=True, is_optimization=True,
            specified_block=QUBITS, priority=0, point_label=0,
            token=service.tokens["qcloud"], task_describe="LoomQ-repro",
        )
        resp = service._request_worker.circuit_chunking_submit(
            "qcloud", ir_list, task_msg.msg_dict(), "sample",
            max_byte_num_per_packet=1000, max_cir_num_per_packet=10,
        )
        task_ids = [r["taskId"] for r in resp if isinstance(r, dict) and r.get("taskId")]
        if not task_ids:
            raise RuntimeError(f"no task id returned: {resp!r}")
        task_id = task_ids[0]
        deadline = time.monotonic() + timeout
        final = None
        while time.monotonic() < deadline:
            qres = service.query_task("qcloud", [task_id], using_http=True, timeout=60)
            item = qres[0] if qres else {}
            status = item.get("task_status", "Unknown")
            if status == "finished":
                final = item
                break
            if status in ("failed", "canceled"):
                raise RuntimeError(f"task failed: {task_id} {status}")
            time.sleep(poll_interval)
        if final is None:
            raise TimeoutError(f"task did not finish within {timeout}s: {task_id}")
        tr = final.get("taskResult")
        import json
        distribution = json.loads(tr[0]) if tr else None
        counts_map = _to_counts_map(distribution)
        counts, source_kind = normalize_distribution(counts_map, shots, width=2)
        completed_at = utc_now()
        probs = {state: round(count / shots, 4) for state, count in counts.items()}
        return {
            "job_id": task_id,
            "shots": shots,
            "physical_qubits": QUBITS,
            "device_id": DEVICE_ID,
            "probabilities": probs,
            "counts": counts,
            "target_mass": round(probs.get("00", 0) + probs.get("11", 0), 4),
            "non_target_mass": round(probs.get("01", 0) + probs.get("10", 0), 4),
            "submitted_at": submitted_at,
            "completed_at": completed_at,
            "source_kind": source_kind,
        }
    finally:
        service.close()


def _update_summary(entry: dict) -> None:
    data = _load_summary()
    data["runs"] = [r for r in data.get("runs", []) if r.get("job_id") != entry["job_id"]]
    data["runs"].append(entry)
    probs = [r["probabilities"] for r in data["runs"]]
    target_masses = [r["target_mass"] for r in data["runs"]]
    n = len(probs)
    summary = {
        "runs_completed": n,
        "successful_runs": n,
        "failed_runs": 0,
        "blocked_runs": 0,
        "target_runs": 5,
        "status": "COMPLETE" if n >= 5 else "PARTIAL",
    }
    if n >= 2:
        import statistics

        mean = statistics.mean(target_masses)
        std = statistics.stdev(target_masses) if n > 1 else 0.0
        summary["mean_target_mass"] = round(mean, 4)
        summary["std_target_mass"] = round(std, 4)
        summary["min_target_mass"] = round(min(target_masses), 4)
        summary["max_target_mass"] = round(max(target_masses), 4)
        summary["stability_metric"] = round(std, 4)
    else:
        summary["stability_metric"] = None
    data["summary"] = summary
    SUMMARY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-runs", type=int, default=5)
    parser.add_argument("--shots", type=int, default=1000)
    parser.add_argument("--timeout", type=int, default=5400)
    parser.add_argument("--poll-interval", type=int, default=45)
    args = parser.parse_args()
    data = _load_summary()
    existing = {r.get("job_id") for r in data.get("runs", [])}
    print(f"existing_runs={len(existing)}")
    while len(existing) < args.target_runs:
        try:
            entry = _submit_one(args.shots, args.timeout, args.poll_interval)
            summary = _update_summary(entry)
            print(f"job_id={entry['job_id']} shots={entry['shots']} qubits={entry['physical_qubits']}")
            print(f"probabilities={entry['probabilities']} target_mass={entry['target_mass']}")
            print(f"runs_completed={summary['runs_completed']}")
            existing.add(entry["job_id"])
        except RuntimeError as exc:
            print(f"PROVIDER_BLOCKED={exc}")
            return 2
    print("TARGET_REACHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())