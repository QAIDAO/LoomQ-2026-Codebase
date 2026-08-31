"""Shared, secret-free helpers for genuine hardware evidence runners."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.metadata
import json
import math
from pathlib import Path
from typing import Any, Mapping


STARTER_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = STARTER_ROOT / "evidence" / "files"
COMPETITION_START = datetime(2026, 8, 1, tzinfo=timezone.utc)
COMPETITION_END = datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc)

BELL_QASM2 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
"""

BELL_QASM3 = """OPENQASM 3.0;
qubit[2] q;
bit[2] c;
h q[0];
cnot q[0], q[1];
c[0] = measure q[0];
c[1] = measure q[1];
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def evidence_paths(provider: str) -> dict[str, Path]:
    prefix = provider.lower()
    return {
        "qasm": EVIDENCE_ROOT / f"{prefix}-hardware-bell.qasm",
        "raw": EVIDENCE_ROOT / f"{prefix}-hardware-result.raw.json",
        "normalized": EVIDENCE_ROOT / f"{prefix}-hardware-result.normalized.json",
        "metadata": EVIDENCE_ROOT / f"{prefix}-hardware-metadata.json",
    }


def repository_path(path: Path) -> str:
    return path.resolve().relative_to(STARTER_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if hasattr(value, "dict") and callable(value.dict):
        return json_safe(value.dict())
    return str(value)


def normalize_distribution(raw: Mapping[Any, Any], shots: int, width: int = 2) -> tuple[dict[str, int], str]:
    if not raw:
        raise ValueError("provider returned an empty distribution")
    canonical: dict[str, float] = {}
    for key, value in raw.items():
        text = str(key).replace(" ", "")
        if text.startswith("0b"):
            text = text[2:]
        if set(text) <= {"0", "1"}:
            state = text.zfill(width)
        else:
            state = format(int(text), f"0{width}b")
        canonical[state] = canonical.get(state, 0.0) + float(value)
    values = list(canonical.values())
    if all(value.is_integer() for value in values) and int(sum(values)) == shots:
        return {state: int(value) for state, value in canonical.items()}, "counts"
    total = sum(values)
    if not math.isclose(total, 1.0, rel_tol=0.02, abs_tol=0.02):
        raise ValueError("provider distribution is neither shot counts nor normalized probabilities")
    scaled = {state: value / total * shots for state, value in canonical.items()}
    counts = {state: math.floor(value) for state, value in scaled.items()}
    remaining = shots - sum(counts.values())
    order = sorted(scaled, key=lambda state: (scaled[state] - counts[state], state), reverse=True)
    for state in order[:remaining]:
        counts[state] += 1
    return counts, "probabilities_converted_by_largest_remainder"


def normalized_result(
    *, provider: str, backend: str, job_id: str, shots: int, counts: dict[str, int],
    submitted_at: str, completed_at: str, device: str, source_kind: str,
) -> dict[str, Any]:
    return {
        "backend": backend,
        "job_id": job_id,
        "shots": shots,
        "counts": dict(sorted(counts.items())),
        "bit_order": "little",
        "timestamp": completed_at,
        "meta": {
            "provider": provider,
            "device": device,
            "is_hardware": True,
            "is_mock": False,
            "submitted_at": submitted_at,
            "source_result_kind": source_kind,
        },
    }


def save_completed_evidence(
    *, provider: str, qasm: str, raw: object, result: dict[str, Any], metadata: dict[str, Any]
) -> dict[str, str]:
    paths = evidence_paths(provider)
    paths["qasm"].parent.mkdir(parents=True, exist_ok=True)
    paths["qasm"].write_text(qasm, encoding="utf-8")
    write_json(paths["raw"], json_safe(raw))
    write_json(paths["normalized"], result)
    metadata = {
        **metadata,
        "qasm_path": repository_path(paths["qasm"]),
        "raw_result_path": repository_path(paths["raw"]),
        "normalized_result_path": repository_path(paths["normalized"]),
        "test_fixture": False,
    }
    write_json(paths["metadata"], metadata)
    return {name: repository_path(path) for name, path in paths.items()}
