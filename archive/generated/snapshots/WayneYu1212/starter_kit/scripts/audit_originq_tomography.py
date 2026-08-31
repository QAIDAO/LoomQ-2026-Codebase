#!/usr/bin/env python3
"""Independently audit a completed OriginQ two-qubit tomography result.

This program reads the preserved provider response only.  It never contacts a
backend and never submits a quantum task.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
FILES = ROOT / "starter_kit" / "evidence" / "files"
PREFIX = "originq_tomography_bell_phi_plus"
RAW_PATH = FILES / f"{PREFIX}-corrected-provider.raw.json"
OUT_PATH = FILES / f"{PREFIX}-corrected-density-audit.json"


def complex_json(value: complex) -> dict[str, float]:
    return {"real": float(value.real), "imag": float(value.imag)}


def main() -> int:
    raw_bytes = RAW_PATH.read_bytes()
    raw = json.loads(raw_bytes.decode("utf-8"))
    provider = json.loads(raw["origin_data"])
    obj = provider.get("obj") or {}
    matrix_records = json.loads((obj.get("qstTaskResult") or [""])[0])
    if len(matrix_records) != 16:
        raise ValueError("provider qstTaskResult is not a 4x4 density matrix")
    rho = np.array([complex(float(cell["r"]), float(cell["i"])) for cell in matrix_records], dtype=complex).reshape(4, 4)
    provider_fidelity = float(obj["qstFidelity"])

    trace = np.trace(rho)
    hermiticity_residual = float(np.max(np.abs(rho - rho.conj().T)))
    eigenvalues = np.linalg.eigvalsh(rho)
    phi_plus = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
    independent_fidelity = complex(phi_plus.conj() @ rho @ phi_plus)
    rho_pt_b = rho.reshape(2, 2, 2, 2).transpose(0, 3, 2, 1).reshape(4, 4)
    ppt_eigenvalues = np.linalg.eigvalsh(rho_pt_b)
    negativity = float(np.sum(np.maximum(0.0, -ppt_eigenvalues)))

    report = {
        "job_id": obj.get("taskId"),
        "backend": obj.get("chipId"),
        "raw_provider_response_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "provider_state_fidelity": provider_fidelity,
        "density_matrix_shape": list(rho.shape),
        "trace": complex_json(complex(trace)),
        "hermiticity_max_abs_residual": hermiticity_residual,
        "eigenvalues": [float(value) for value in eigenvalues],
        "psd_tolerance": 1e-9,
        "is_psd_within_tolerance": bool(float(np.min(eigenvalues)) >= -1e-9),
        "independent_phi_plus_fidelity": complex_json(independent_fidelity),
        "fidelity_absolute_difference": float(abs(independent_fidelity.real - provider_fidelity)),
        "partial_transpose_subsystem": "B",
        "ppt_eigenvalues": [float(value) for value in ppt_eigenvalues],
        "negativity": negativity,
        "ppt_2x2_note": "For a two-qubit state, PPT is necessary and sufficient for separability.",
        "claim_boundary": (
            "At the level of the provider-reconstructed density-matrix point estimate, "
            "the two-qubit state is entangled under the PPT criterion. "
            "No statistical confidence interval is claimed."
            if negativity > 0 else
            "The provider-reconstructed density-matrix point estimate has no negative partial-transpose eigenvalue. "
            "No statistical confidence interval is claimed."
        ),
    }
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"job_id={report['job_id']}")
    print(f"provider_fidelity={provider_fidelity:.12g}")
    print(f"independent_fidelity={independent_fidelity.real:.12g}")
    print(f"negativity={negativity:.12g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
