"""Unified execution records and hardware-evidence export for L1 backends."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


SENSITIVE_FRAGMENTS = ("token", "secret", "password", "private_key", "authorization", "cookie")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    """Convert SDK values to JSON-safe data without retaining credentials."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if any(part in str(key).lower() for part in SENSITIVE_FRAGMENTS)
            else _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "dict") and callable(value.dict):
        return _json_safe(value.dict())
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return _json_safe(value.model_dump())
    return str(value)


@dataclass
class ExecutionResult:
    backend: str
    job_id: str
    shots: int
    counts: Dict[str, int]
    timestamp: str
    bit_order: str = "little"
    device: Optional[str] = None
    counts_source: str = "measurement_counts"
    raw_result: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("execution result requires a traceable job ID")
        if self.shots <= 0:
            raise ValueError("execution result shots must be positive")
        if not self.counts:
            raise ValueError("execution result counts must not be empty")
        for key, value in self.counts.items():
            if not key or set(key) - {"0", "1"}:
                raise ValueError(f"execution result contains an invalid count key: {key}")
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"execution result contains an invalid count value: {value}")
        if sum(self.counts.values()) != self.shots:
            raise ValueError("execution result counts total must equal shots")
        if self.bit_order != "little":
            raise ValueError("execution result bit_order must be little")
        if not self.timestamp:
            raise ValueError("execution result timestamp must not be empty")

    def to_contract_dict(self, *, include_raw: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "backend": self.backend,
            "job_id": self.job_id,
            "shots": self.shots,
            "counts": dict(self.counts),
            "bit_order": self.bit_order,
            "timestamp": self.timestamp,
        }
        meta = dict(self.metadata)
        if self.device:
            meta["device"] = self.device
        meta["counts_source"] = self.counts_source
        if meta:
            payload["meta"] = _json_safe(meta)
        if include_raw:
            payload["raw_result"] = _json_safe(self.raw_result)
        return payload


def save_hardware_evidence(
    execution: ExecutionResult,
    native_program: str,
    output_directory: str,
    *,
    program_suffix: str,
) -> Dict[str, str]:
    """Write a native program, normalized result, and sanitized raw response."""
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    stem = execution.backend.replace("_real", "")
    program_path = directory / f"{stem}-circuit.{program_suffix.lstrip('.')}"
    result_path = directory / f"{stem}-result.json"
    raw_path = directory / f"{stem}-raw-result.json"

    program_path.write_text(native_program, encoding="utf-8")
    result_path.write_text(
        json.dumps(execution.to_contract_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    raw_path.write_text(
        json.dumps(_json_safe(execution.raw_result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "program": str(program_path),
        "result": str(result_path),
        "raw_result": str(raw_path),
    }


def save_local_artifacts(
    execution: ExecutionResult,
    native_program: str,
    output_directory: str,
    *,
    program_suffix: str,
) -> Dict[str, str]:
    """Write a local backend's native program and normalized result."""
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    stem = execution.backend
    program_path = directory / f"{stem}-local-circuit.{program_suffix.lstrip('.')}"
    result_path = directory / f"{stem}-local-result.json"

    program_path.write_text(native_program, encoding="utf-8")
    result_path.write_text(
        json.dumps(execution.to_contract_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"program": str(program_path), "result": str(result_path)}
