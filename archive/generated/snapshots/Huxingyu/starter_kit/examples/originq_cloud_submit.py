#!/usr/bin/env python3
"""Submit an OpenQASM 2.0 circuit to the Origin Quantum cloud real QPU.

Uses the official pyqpanda3 QCloudService client. The submitted QASM, job ID,
raw origin data, timing info and normalized counts are saved as evidence.

Environment:
    ORIGINQ_API_KEY    Origin Quantum cloud API key (do not commit it)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from pyqpanda3.intermediate_compiler import (
    convert_qasm_string_to_qprog,
    convert_qprog_to_originir,
    convert_qprog_to_qasm,
)
from pyqpanda3.qcloud import QCloudService, QCloudOptions, DataBase, JobStatus


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def exact_counts(probs: Dict[str, float], shots: int) -> Dict[str, int]:
    """Round probabilities to integer counts that sum exactly to shots."""
    scaled = {key: value * shots for key, value in probs.items()}
    counts = {key: int(value) for key, value in scaled.items()}
    remaining = shots - sum(counts.values())
    for key in sorted(scaled, key=lambda item: scaled[item] - int(scaled[item]), reverse=True)[:remaining]:
        counts[key] += 1
    return counts


def choose_backend(service: QCloudService, preferred: List[str]) -> str:
    backends = service.backends()
    for name in preferred:
        if backends.get(name, False):
            return name
    available = [name for name, enabled in backends.items() if enabled]
    if not available:
        raise RuntimeError("no available Origin Quantum backend")
    return available[0]


def chip_summary(backend) -> Dict[str, Any]:
    info = backend.chip_info()
    try:
        edges = info.get_chip_topology()
    except Exception:
        edges = []
    try:
        double = [[q1, q2] for q1, q2 in (item.get_qubits() for item in info.double_qubits_info())]
    except Exception:
        double = []
    try:
        blocks = backend.best_qubit_blocks(2, 1, 1)
        best_blocks = list(blocks)
    except Exception:
        best_blocks = []
    return {
        "chip_id": info.chip_id(),
        "qubits_num": info.qubits_num(),
        "available_qubits": info.available_qubits(),
        "basic_gates": info.get_basic_gates(),
        "topology": edges,
        "double_qubit_edges": double,
        "best_2q_blocks": best_blocks,
    }


def submit(
    qasm: str,
    backend_name: str = "WK_C180",
    shots: int = 1024,
    poll_interval: int = 5,
    specified_block: List[int] | None = None,
) -> Dict[str, Any]:
    api_key = os.environ.get("ORIGINQ_API_KEY")
    if not api_key:
        raise RuntimeError("ORIGINQ_API_KEY must be set")

    service = QCloudService(api_key)
    available = service.backends()
    if backend_name not in available or not available[backend_name]:
        raise RuntimeError(f"backend {backend_name} is not available; got {sorted(available)}")
    backend = service.backend(backend_name)

    try:
        prog = convert_qasm_string_to_qprog(qasm)
    except Exception as exc:
        raise RuntimeError(
            "Origin Quantum rejected the supplied QASM; no fallback circuit was submitted"
        ) from exc

    submitted_at = utcnow()
    options = QCloudOptions()
    if specified_block:
        options.set_specified_block(specified_block)
    job = backend.run(prog, shots, options)
    job_id = job.job_id()

    statuses: List[str] = []
    deadline = time.time() + 1800
    while time.time() < deadline:
        status = job.status()
        statuses.append(status.name)
        if status in (JobStatus.FINISHED, JobStatus.FAILED):
            break
        time.sleep(poll_interval)
    if status not in (JobStatus.FINISHED, JobStatus.FAILED):
        raise TimeoutError(f"job {job_id} did not finish within 30 minutes")
    if status == JobStatus.FAILED:
        raise RuntimeError(f"job {job_id} failed")

    result = job.result()
    probs = result.get_probs(DataBase.Binary)
    counts = result.get_counts(DataBase.Binary) or exact_counts(probs, shots)
    raw = result.origin_data()
    try:
        raw_obj = json.loads(raw)
    except Exception:
        raw_obj = raw

    originir = convert_qprog_to_originir(prog)
    submitted_qasm = convert_qprog_to_qasm(prog)
    extras: Dict[str, Any] = {}
    for name in ("qprog", "instructions", "mapping_qprog", "mapping_qubit", "measure_qubits", "src_qubits", "target_cbits", "prob_count_raw"):
        try:
            extras[name] = getattr(result, name)()
        except Exception:
            pass

    return {
        "backend": "originq_wukong",
        "backend_detail": backend.name(),
        "job_id": job_id,
        "submitted_at": submitted_at,
        "finished_at": utcnow(),
        "timestamp": submitted_at.replace("+00:00", "Z"),
        "shots": shots,
        "status": status.name,
        "counts": counts,
        "probs": probs,
        "bit_order": "little",
        "meta": {
            "is_mock": False,
            "platform": "Origin Quantum Cloud",
            "backend_detail": backend.name(),
        },
        "timing_info": result.timing_info(),
        "originir": originir,
        "qasm": submitted_qasm,
        "chip": chip_summary(backend),
        "raw_origin_data": raw_obj,
        "extra_fields": extras,
        "status_poll": statuses,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("qasm", help="OpenQASM 2.0 circuit file")
    parser.add_argument("--backend", default="WK_C180", help="Origin cloud backend name")
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--json-out", help="output JSON evidence file")
    parser.add_argument("--specified-block", nargs="+", type=int, default=None,
                        help="physical qubit block, e.g. --specified-block 157 166 176")
    args = parser.parse_args()

    qasm = open(args.qasm, encoding="utf-8").read()
    outcome = submit(qasm, backend_name=args.backend, shots=args.shots, specified_block=args.specified_block)
    print(json.dumps(
        {
            "backend": outcome["backend"],
            "backend_detail": outcome["backend_detail"],
            "job_id": outcome["job_id"],
            "submitted_at": outcome["submitted_at"],
            "finished_at": outcome["finished_at"],
            "shots": outcome["shots"],
            "counts": outcome["counts"],
            "probs": outcome["probs"],
            "timing_info": outcome["timing_info"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(outcome, handle, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
