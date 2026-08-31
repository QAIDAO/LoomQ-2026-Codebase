"""LoomQ 执行结果 Schema 的创建与校验。"""

from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional


class ResultValidationError(ValueError):
    """执行结果不满足 LoomQ 官方 Schema。"""


def validate_shots(shots: int) -> None:
    """校验执行次数，bool 不视为合法整数。"""
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ResultValidationError("shots must be a positive integer")


def _validate_counts(counts: Mapping[str, int], shots: int) -> Dict[str, int]:
    if not isinstance(counts, dict):
        raise ResultValidationError("counts must be a dict")
    if not counts:
        raise ResultValidationError("counts must not be empty")

    key_length: Optional[int] = None
    normalized: Dict[str, int] = {}
    for key, value in counts.items():
        if not isinstance(key, str) or not key or set(key) - {"0", "1"}:
            raise ResultValidationError("counts keys must be non-empty binary strings")
        if key_length is None:
            key_length = len(key)
        elif len(key) != key_length:
            raise ResultValidationError("all counts keys must have the same length")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ResultValidationError("counts values must be non-negative integers")
        normalized[key] = value

    if sum(normalized.values()) != shots:
        raise ResultValidationError("counts total must equal shots exactly")
    return normalized


def create_result(
    *,
    backend: str,
    job_id: str,
    shots: int,
    counts: Mapping[str, int],
    meta: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """创建经过完整校验的普通 dict 结果。"""
    validate_shots(shots)
    if not isinstance(backend, str) or not backend:
        raise ResultValidationError("backend must be a non-empty string")
    if not isinstance(job_id, str) or not job_id:
        raise ResultValidationError("job_id must be a non-empty string")

    normalized_counts = _validate_counts(counts, shots)
    normalized_meta = dict(meta) if meta is not None else {}
    if normalized_meta.get("is_mock"):
        raise ResultValidationError("meta.is_mock must not be true")

    # 统一使用 UTC，并将 +00:00 规范化为比赛要求的 Z 后缀。
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "backend": backend,
        "job_id": job_id,
        "shots": shots,
        "counts": normalized_counts,
        "bit_order": "little",
        "timestamp": timestamp,
        "meta": normalized_meta,
    }
