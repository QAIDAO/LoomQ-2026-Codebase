#!/usr/bin/env python3
"""Read-only validation for the OriginQ Bell tomography evidence package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SUCCESS = "F7287E16E8478E4DB5051105468DB638"
FAILURE = "EE7D22A38D5A9F246A2031BC7A31C3AD"


def _load(root: Path, name: str) -> dict[str, Any]:
    return json.loads((root / name).read_text(encoding="utf-8"))


def validate_package(root: Path) -> dict[str, Any]:
    attempt_one = _load(root, "originq_tomography_bell_phi_plus-submission.json")
    attempt_one_raw = _load(root, "originq_tomography_bell_phi_plus-provider.raw.json")
    attempt_two = _load(root, "originq_tomography_bell_phi_plus-corrected-submission.json")
    attempt_two_raw_path = root / "originq_tomography_bell_phi_plus-corrected-provider.raw.json"
    attempt_two_raw = json.loads(attempt_two_raw_path.read_text(encoding="utf-8"))
    audit = _load(root, "originq_tomography_bell_phi_plus-corrected-density-audit.json")
    metadata = _load(root, "originq_tomography_bell_phi_plus-corrected-metadata.json")
    if attempt_one.get("job_id") != FAILURE or attempt_two.get("job_id") != SUCCESS:
        raise ValueError("attempt job IDs do not match the declared failure/success provenance")
    if attempt_one_raw.get("job_status") != "JobStatus.FAILED":
        raise ValueError("attempt 1 must remain recorded as FAILED")
    if "measured qubit is zero" not in attempt_one_raw.get("origin_data", ""):
        raise ValueError("attempt 1 does not preserve the missing-measurement provider error")
    if attempt_two_raw.get("job_status") != "JobStatus.FINISHED":
        raise ValueError("attempt 2 must be FINISHED")
    origin = json.loads(attempt_two_raw["origin_data"])
    obj = origin.get("obj") or {}
    if obj.get("taskId") != SUCCESS or obj.get("chipId") != "WK_C180_2":
        raise ValueError("provider response has unexpected success job or backend")
    if obj.get("qstFidelity") is None or not obj.get("qstTaskResult"):
        raise ValueError("provider tomography response omits fidelity or density matrix")
    if metadata.get("shots") != 1000 or metadata.get("requested_physical_qubits") != [49, 58]:
        raise ValueError("metadata does not preserve requested shots/physical block")
    raw_hash = hashlib.sha256(attempt_two_raw_path.read_bytes()).hexdigest()
    if raw_hash != audit.get("raw_provider_response_sha256"):
        raise ValueError("raw provider response hash does not match density audit")
    if audit.get("job_id") != SUCCESS or audit.get("backend") != "WK_C180_2":
        raise ValueError("density audit does not bind to the successful provider job")
    if audit.get("density_matrix_shape") != [4, 4]:
        raise ValueError("density matrix is not 4x4")
    trace = audit.get("trace", {})
    if abs(float(trace.get("real", float("nan"))) - 1.0) > 1e-9 or abs(float(trace.get("imag", float("nan")))) > 1e-9:
        raise ValueError("density matrix trace is not finite and unit")
    if not audit.get("is_psd_within_tolerance"):
        raise ValueError("density matrix PSD tolerance check failed")
    difference = float(audit.get("fidelity_absolute_difference", float("inf")))
    if difference > 1e-6:
        raise ValueError("independent/provider fidelity difference exceeds tolerance")
    ppt = audit.get("ppt_eigenvalues") or []
    if len(ppt) != 4 or min(float(value) for value in ppt) >= 0:
        raise ValueError("PPT audit lacks a negative partial-transpose eigenvalue")
    return {
        "status": "PASS", "failure_job_id": FAILURE, "success_job_id": SUCCESS,
        "raw_provider_response_sha256": raw_hash,
        "fidelity_absolute_difference": difference,
        "ppt_minimum_eigenvalue": min(float(value) for value in ppt),
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "evidence" / "files" / "originq-tomography"
    print(json.dumps(validate_package(root), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
