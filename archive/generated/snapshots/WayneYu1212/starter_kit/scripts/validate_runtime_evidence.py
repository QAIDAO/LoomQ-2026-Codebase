#!/usr/bin/env python3
"""Validate supplemental QPanda3 Runtime evidence without imposing canonical schema.

These packages are participant-side modern Runtime evidence only. They do not
replace the accepted SpinQ/OriginQ canonical hardware packages, and this
validator deliberately requires provider probabilities rather than fabricated
per-shot counts or unavailable provider timestamps.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


FILES = Path(__file__).resolve().parents[1] / "evidence" / "files"
PREFIXES = (
    "originq_runtime_bell",
    "originq_runtime_ghz3",
    "originq_runtime_multi",
    "originq_runtime_bell_xbasis",
    "originq_runtime_bell_ybasis",
)
SECRET_KEY = re.compile(r"token|api[_-]?key|secret|access[_-]?key|cookie|authorization", re.I)
TIMESTAMP_KEYS = {"created_at", "submitted_at", "started_at", "completed_at", "timestamp"}


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: expected an object")
    return value


def provider_probabilities(raw: dict, width: int) -> dict[str, float]:
    if "probabilities" in raw:
        return {str(key): float(value) for key, value in raw["probabilities"].items()}
    response = raw.get("raw_sdk_response", raw.get("sdk_response"))
    if not isinstance(response, dict) or not isinstance(response.get("taskResult"), list):
        raise ValueError("raw response does not expose provider probabilities")
    payload = json.loads(response["taskResult"][0])
    return {
        format(int(key, 0), f"0{width}b"): float(value)
        for key, value in zip(payload["key"], payload["value"])
    }


def secret_paths(value: object, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if SECRET_KEY.search(str(key)):
                found.append(path)
            found.extend(secret_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(secret_paths(item, f"{prefix}[{index}]"))
    return found


def validate_package(prefix: str) -> dict[str, str]:
    manifest_path = FILES / f"{prefix}-manifest.json"
    metadata_path = FILES / f"{prefix}-hardware-metadata.json"
    normalized_path = FILES / f"{prefix}-hardware-result.normalized.json"
    raw_path = FILES / f"{prefix}-hardware-result.raw.json"
    qasm_path = FILES / f"{prefix}-hardware-bell.qasm"
    manifest, metadata, normalized, raw = map(load, (manifest_path, metadata_path, normalized_path, raw_path))

    job_id = manifest.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError(f"{prefix}: missing manifest job_id")
    raw_job_id = raw.get("job_id", raw.get("task_id"))
    if metadata.get("job_id") != job_id or normalized.get("job_id") != job_id or raw_job_id != job_id:
        raise ValueError(f"{prefix}: job_id mismatch across package")
    if metadata.get("device_id") != "WK_C180_2" or manifest.get("device_id") != "WK_C180_2":
        raise ValueError(f"{prefix}: unexpected device")
    if not qasm_path.read_text(encoding="utf-8").strip():
        raise ValueError(f"{prefix}: empty QASM")

    for item_name, item in (("metadata", metadata), ("normalized", normalized), ("raw", raw)):
        if secret_paths(item):
            raise ValueError(f"{prefix}: secret-like key in {item_name}")
    if any(key in metadata for key in TIMESTAMP_KEYS) or any(key in normalized for key in TIMESTAMP_KEYS):
        raise ValueError(f"{prefix}: timestamp must not be claimed without captured provider value")
    if metadata.get("timestamp_status") != "not exposed by the captured Runtime API response":
        raise ValueError(f"{prefix}: timestamp availability is not declared")
    if metadata.get("result_kind") != "provider_probabilities" or normalized.get("result_kind") != "provider_probabilities":
        raise ValueError(f"{prefix}: result kind must be provider probabilities")
    if not isinstance(metadata.get("requested_shots"), int) or metadata["requested_shots"] <= 0:
        raise ValueError(f"{prefix}: missing requested shots")
    if normalized.get("requested_shots") != metadata["requested_shots"]:
        raise ValueError(f"{prefix}: requested shots mismatch")
    if "counts" in normalized or "shots" in normalized:
        raise ValueError(f"{prefix}: per-shot counts must not be fabricated")
    width = normalized.get("logical_qubits")
    if not isinstance(width, int) or width <= 0:
        raise ValueError(f"{prefix}: missing logical qubit width")
    expected = provider_probabilities(raw, width)
    actual = normalized.get("probabilities")
    if actual != expected:
        raise ValueError(f"{prefix}: normalized probabilities differ from provider response")
    if not 0.98 <= sum(expected.values()) <= 1.02:
        raise ValueError(f"{prefix}: probabilities do not sum near one")

    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{prefix}: missing manifest files")
    if any(entry.get("name") == manifest_path.name for entry in entries):
        raise ValueError(f"{prefix}: manifest must not hash itself")
    for entry in entries:
        target = FILES / str(entry.get("name", ""))
        if not target.is_file():
            raise ValueError(f"{prefix}: manifest file missing")
        if target.stat().st_size != entry.get("size_bytes"):
            raise ValueError(f"{prefix}: manifest size mismatch for {target.name}")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != entry.get("sha256"):
            raise ValueError(f"{prefix}: manifest hash mismatch for {target.name}")
    return {"package": prefix, "job_id": job_id}


def main() -> int:
    packages = [validate_package(prefix) for prefix in PREFIXES]
    unique_jobs = {package["job_id"] for package in packages}
    if len(unique_jobs) != len(packages):
        raise ValueError("cross-job separation failed: duplicate job_id")
    print(json.dumps({
        "status": "PASS",
        "package_count": len(packages),
        "unique_job_count": len(unique_jobs),
        "provider_timestamps": "unavailable",
        "per_shot_counts": "unavailable",
        "packages": packages,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
