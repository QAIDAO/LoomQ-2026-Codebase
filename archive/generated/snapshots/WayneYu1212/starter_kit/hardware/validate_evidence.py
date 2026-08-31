#!/usr/bin/env python3
"""Validate hardware evidence structure without claiming remote traceability."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
from typing import Any

from starter_kit.hardware.common import COMPETITION_END, COMPETITION_START, STARTER_ROOT


ALLOWED_PROVIDERS = {"originq", "braket", "spinq"}
SECRET_KEYS = re.compile(r"token|api[_-]?key|secret|access[_-]?key|cookie|authorization", re.I)
FORBIDDEN_ID = re.compile(r"local|simulator|mock|fixture|example|placeholder", re.I)


def _validate_result_schema(result: object) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "result must be an object"
    required = ("backend", "job_id", "shots", "counts", "bit_order", "timestamp")
    missing = [field for field in required if field not in result]
    if missing:
        return False, "missing fields: " + ", ".join(missing)
    shots = result["shots"]
    counts = result["counts"]
    if isinstance(shots, bool) or not isinstance(shots, int) or shots <= 0:
        return False, "shots must be a positive integer"
    if not isinstance(counts, dict) or not counts:
        return False, "counts must be non-empty"
    if any(not isinstance(key, str) or not key or set(key) - {"0", "1"} for key in counts):
        return False, "counts keys must be binary strings"
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts.values()):
        return False, "counts values must be non-negative integers"
    if sum(counts.values()) != shots:
        return False, "counts total must equal shots"
    if result["bit_order"] != "little":
        return False, "bit_order must be little"
    return True, "schema valid"


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    if not COMPETITION_START <= parsed <= COMPETITION_END:
        raise ValueError(f"{field} is outside the competition window")
    return parsed


def _secret_paths(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if SECRET_KEYS.search(str(key)):
                found.append(path)
            found.extend(_secret_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_secret_paths(item, f"{prefix}[{index}]"))
    return found


def _resolve(reference: object) -> Path:
    if not isinstance(reference, str) or not reference:
        raise ValueError("evidence path must be non-empty text")
    candidate = (STARTER_ROOT / reference).resolve()
    if STARTER_ROOT.resolve() not in candidate.parents or not candidate.is_file():
        raise ValueError(f"evidence path is missing or outside starter_kit: {reference}")
    return candidate


def validate_metadata(path: Path, *, allow_test_fixture: bool = False) -> dict[str, Any]:
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if metadata.get("test_fixture") and not allow_test_fixture:
        raise ValueError("TEST/FIXTURE evidence cannot be finalized")
    provider = str(metadata.get("provider", "")).lower()
    if provider not in ALLOWED_PROVIDERS:
        raise ValueError("provider must be originq, braket, or spinq")
    job_id = metadata.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip() or FORBIDDEN_ID.search(job_id):
        raise ValueError("job/task ID is empty or resembles a local/mock placeholder")
    device = str(metadata.get("device", ""))
    if not device or re.search(r"simulator|local", device, re.I):
        raise ValueError("device must identify genuine hardware, not a simulator")
    shots = metadata.get("shots")
    probability_mode = metadata.get("result_kind") == "probabilities"
    if probability_mode:
        if shots is not None or not metadata.get("shots_note"):
            raise ValueError("probability evidence must use shots=null and explain shots_note")
    elif isinstance(shots, bool) or not isinstance(shots, int) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    _timestamp(metadata.get("submitted_at"), "submitted_at")
    _timestamp(metadata.get("completed_at"), "completed_at")
    qasm_path = _resolve(metadata.get("qasm_path"))
    raw_path = _resolve(metadata.get("raw_result_path"))
    normalized_path = _resolve(metadata.get("normalized_result_path"))
    for optional_path in (
        "task_screenshot_path",
        "raw_csv_path",
        "raw_binary_path",
        "raw_qasm_path",
        "logical_circuit_svg_path",
        "physical_circuit_svg_path",
    ):
        if metadata.get(optional_path):
            _resolve(metadata[optional_path])
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    if probability_mode:
        probabilities = normalized.get("probabilities")
        if not isinstance(probabilities, dict) or not probabilities:
            raise ValueError("probability evidence requires a non-empty probabilities object")
        if any(not isinstance(key, str) or not key or set(key) - {"0", "1"} for key in probabilities):
            raise ValueError("probability keys must be binary strings")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 for value in probabilities.values()):
            raise ValueError("probabilities must be non-negative numbers")
        if not math.isclose(sum(float(value) for value in probabilities.values()), 1.0, rel_tol=0.02, abs_tol=0.02):
            raise ValueError("probabilities must sum to approximately one")
        if normalized.get("job_id") != job_id or normalized.get("shots") is not None:
            raise ValueError("metadata and probability result disagree")
    else:
        valid, reason = _validate_result_schema(normalized)
        if not valid:
            raise ValueError(f"normalized result schema failed: {reason}")
        if normalized["job_id"] != job_id or normalized["shots"] != shots:
            raise ValueError("metadata and normalized result disagree")
    if re.search(r"simulator|local", str(normalized["backend"]), re.I):
        raise ValueError("normalized backend claims a simulator/local execution")
    if normalized.get("meta", {}).get("is_mock"):
        raise ValueError("meta.is_mock must be absent or false")
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    secret_fields = sorted(set(_secret_paths(metadata) + _secret_paths(raw) + _secret_paths(normalized)))
    if secret_fields:
        raise ValueError("secret-like fields found: " + ", ".join(secret_fields))
    if not qasm_path.read_text(encoding="utf-8").strip():
        raise ValueError("QASM evidence is empty")
    return {
        "provider": provider,
        "platform": metadata.get("platform", provider),
        "job_id": job_id,
        "device": device,
        "shots": shots,
        "shots_note": metadata.get("shots_note", ""),
        "submitted_at": metadata["submitted_at"],
        "completed_at": metadata["completed_at"],
        "qasm_path": metadata["qasm_path"],
        "raw_result_path": metadata["raw_result_path"],
        "normalized_result_path": metadata["normalized_result_path"],
        "metadata_path": path.resolve().relative_to(STARTER_ROOT.resolve()).as_posix(),
        "task_screenshot_path": metadata.get("task_screenshot_path", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local LoomQ hardware evidence structure")
    parser.add_argument("metadata", nargs="+")
    args = parser.parse_args()
    for item in args.metadata:
        result = validate_metadata(Path(item).resolve())
        print(f"PASS provider={result['provider']} job_id={result['job_id']}")
    print("LOCAL VALIDATION DOES NOT PROVE REMOTE JOB TRACEABILITY; ORGANIZERS MAY LOG IN AND VERIFY THE JOB ID.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
