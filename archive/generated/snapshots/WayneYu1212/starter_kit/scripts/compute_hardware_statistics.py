#!/usr/bin/env python3
"""Compute statistical uncertainty (Wilson 95% CI) for the LoomQ hardware evidence.

Reads the normalized hardware results (provider job records) and computes, for each
job, the Wilson score interval for the headline support rates. This is OFFLINE
analysis of already-recorded evidence — it does not touch raw files and does not
submit anything.

Output: starter_kit/evidence/files/hardware-statistics.json

Usage:
    python starter_kit/scripts/compute_hardware_statistics.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

STARTER_ROOT = Path(__file__).resolve().parent.parent
FILES = STARTER_ROOT / "evidence" / "files"
Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float, float]:
    """Wilson score interval for a binomial proportion k/n."""
    if n <= 0:
        raise ValueError("n must be positive")
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def raw_probabilities(raw: dict, width: int) -> dict[str, float]:
    """Read the two recorded Runtime probability-response shapes."""
    if "probabilities" in raw:
        return raw["probabilities"]
    response = raw["sdk_response"]
    payload = json.loads(response["taskResult"][0])
    return {
        format(int(key, 0), f"0{width}b"): value
        for key, value in zip(payload["key"], payload["value"])
    }


def analyze(job: dict) -> dict:
    if job.get("source_result_kind") == "probabilities":
        return {
            "job_id": job["job_id"],
            "device": job.get("device", job.get("device_id", "")),
            "requested_shots": int(job["shots"]),
            "circuit_kind": job.get("circuit_kind", job.get("kind", "")),
            "source_result_kind": "provider_probabilities",
            "probabilities": job["probabilities"],
            "statistical_inference": "not_computed",
            "note": "Provider probability output is preserved as a point estimate. Raw shot counts were not exported, so Wilson intervals are not computed from rounded display counts.",
        }
    counts = job["counts"]
    n = int(job["shots"])
    states = sorted(counts)
    # headline target states per circuit kind
    kind = job.get("circuit_kind", job.get("kind", ""))
    if kind in ("bell", "bell_xbasis", "bell_ybasis"):
        target = ["00", "11"]
    elif kind == "ghz3":
        target = ["000", "111"]
    elif kind == "multi":
        target = None  # uniform reference; report per-state intervals
    else:
        target = None
    out = {
        "job_id": job["job_id"],
        "device": job.get("device", job.get("device_id", "")),
        "shots": n,
        "circuit_kind": kind,
        "per_state": {},
    }
    for s in states:
        k = int(counts[s])
        p, lo, hi = wilson(k, n)
        out["per_state"][s] = {
            "count": k,
            "p_hat": round(p, 4),
            "wilson95": [round(lo, 4), round(hi, 4)],
        }
    if target:
        k = sum(int(counts[s]) for s in target if s in counts)
        p, lo, hi = wilson(k, n)
        out["target_support"] = {
            "states": target,
            "count": k,
            "p_hat": round(p, 4),
            "wilson95": [round(lo, 4), round(hi, 4)],
            "note": "Wilson score 95% interval; separable/mixed baseline for Bell Z-basis "
                    "target support is 0.5 only for a maximally-correlated classical mixture; "
                    "the interval quantifies sampling uncertainty, not hardware noise.",
        }
    return out


def main() -> int:
    jobs = []

    # canonical OriginQ Bell (D0C7F4) - counts live in normalized result
    norm = json.loads((FILES / "originq-hardware-result.normalized.json").read_text(encoding="utf-8"))
    jobs.append({
        "job_id": norm["job_id"], "shots": norm["shots"], "counts": norm["counts"],
        "device": "Origin Wukong 180-2 (legacy QCloud)", "circuit_kind": "bell",
    })

    # runtime jobs
    for prefix, kind in (
        ("originq_runtime_bell", "bell"),
        ("originq_runtime_ghz3", "ghz3"),
        ("originq_runtime_multi", "multi"),
        ("originq_runtime_bell_xbasis", "bell_xbasis"),
        ("originq_runtime_bell_ybasis", "bell_ybasis"),
    ):
        d = json.loads((FILES / f"{prefix}-hardware-result.normalized.json").read_text(encoding="utf-8"))
        raw = json.loads((FILES / f"{prefix}-hardware-result.raw.json").read_text(encoding="utf-8"))
        jobs.append({
            "job_id": d["job_id"], "shots": d["requested_shots"],
            "device": "Origin Wukong 180-2 (QPanda3 Runtime, WK_C180_2)", "circuit_kind": kind,
            "source_result_kind": "probabilities",
            "probabilities": raw_probabilities(raw, d["logical_qubits"]),
        })

    # SpinQ (probability mode; shots not exposed - report probabilities only)
    spinq = json.loads((FILES / "spinq-hardware-result.normalized.json").read_text(encoding="utf-8"))
    probabilities = spinq.get("probabilities")

    result = {
        "generated_by": "starter_kit/scripts/compute_hardware_statistics.py",
        "method": {
            "interval": "Wilson score interval, z=1.959963984540054 (95%)",
            "formula": "center=(p+z^2/2n)/(1+z^2/n); half=z*sqrt(p(1-p)/n+z^2/4n^2)/(1+z^2/n)",
            "scope": "sampling uncertainty only; does not model readout/depolarizing noise",
        },
        "jobs": [analyze(j) for j in jobs],
    }
    if probabilities:
        result["spinq_note"] = {
            "job_id": spinq.get("job_id"),
            "note": "SpinQ NMR export provides ensemble projection probabilities without a discrete "
                    "shot count; no binomial interval is computed (would require fabricating a shot count).",
            "probabilities": probabilities,
        }

    out_path = FILES / "hardware-statistics.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path.relative_to(STARTER_ROOT.parent)}")
    for j in result["jobs"]:
        ts = j.get("target_support")
        line = f"{j['job_id']} ({j['circuit_kind']}): "
        if ts:
            line += f"target {ts['states']} p={ts['p_hat']} wilson95={ts['wilson95']}"
        elif j.get("statistical_inference") == "not_computed":
            line += "provider probabilities; no independently-derived interval"
        else:
            line += "per-state intervals only"
        print(" ", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
