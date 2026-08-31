#!/usr/bin/env python3
"""Run Bell on Origin Quantum cloud (QPU if online, else full-amplitude cloud sim).

Env:
  ORIGIN_API_TOKEN   required api token from qcloud.originqc.com.cn
  ORIGIN_SHOTS       default 1000
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _probs_to_counts(probs: dict, shots: int) -> dict:
    # values may be probabilities or already counts
    vals = {str(k): float(v) for k, v in dict(probs).items()}
    total = sum(vals.values())
    if total <= 1.5:
        raw = {k: int(round(v * shots)) for k, v in vals.items()}
    else:
        raw = {k: int(round(v)) for k, v in vals.items()}
    # fix rounding
    diff = shots - sum(raw.values())
    if raw and diff:
        kmax = max(raw, key=raw.get)
        raw[kmax] += diff
    return raw


def main() -> int:
    token = os.environ.get("ORIGIN_API_TOKEN", "").strip()
    shots = int(os.environ.get("ORIGIN_SHOTS", "1000"))
    if not token:
        print("缺少 ORIGIN_API_TOKEN", file=sys.stderr)
        return 2

    import pyqpanda as pq

    out = Path(__file__).resolve().parent / "evidence" / "files"
    out.mkdir(parents=True, exist_ok=True)
    qasm_path = Path(__file__).resolve().parent / "circuits" / "bell.qasm"
    qasm = qasm_path.read_text(encoding="utf-8")

    qm = pq.QCloud()
    if hasattr(qm, "set_configure"):
        qm.set_configure(72, 72)
    qm.init_qvm(token, True)
    try:
        q = qm.qAlloc_many(2)
        c = qm.cAlloc_many(2)
        prog = pq.QProg()
        prog << pq.H(q[0]) << pq.CNOT(q[0], q[1])
        prog << pq.Measure(q[0], c[0]) << pq.Measure(q[1], c[1])

        backend = "originq_wukong"
        job_id = "unknown"
        counts = {}
        meta = {}
        try:
            chip = pq.real_chip_type.origin_72
            raw = qm.real_chip_measure(prog, shots, chip)
            meta["mode"] = "real_chip"
            print("real chip raw:", raw)
        except Exception as exc:
            print("真机不可用，改用云全振幅模拟:", exc)
            raw = qm.full_amplitude_measure(prog, shots)
            backend = "originq_cloud_full_amplitude"
            meta["mode"] = "full_amplitude"
            print("cloud sim raw:", raw)

        if isinstance(raw, dict):
            # probability dict or count dict
            sample = next(iter(raw.values()))
            if isinstance(sample, float) and sample <= 1.0:
                counts = _probs_to_counts(raw, shots)
            else:
                counts = {str(k): int(v) for k, v in raw.items()}
            meta["raw"] = {str(k): v for k, v in raw.items()}

        payload = {
            "backend": backend,
            "job_id": job_id,
            "shots": sum(counts.values()) if counts else shots,
            "counts": counts,
            "bit_order": "little",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "meta": meta,
        }
        (out / "originq-circuit.qasm").write_text(qasm, encoding="utf-8")
        (out / "originq-result.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("wrote", out / "originq-result.json")
        return 0
    finally:
        try:
            qm.finalize()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
