"""Shared validation, result extraction, and schema helpers for remote runs."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import os
from typing import Any, Dict, Iterable, Mapping, Optional


class HardwareInterfaceError(RuntimeError):
    """Raised when a remote provider cannot be configured or queried."""


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise HardwareInterfaceError(
            f"missing required environment variable: {name}"
        )
    return value


def positive_shots(shots: int) -> int:
    if isinstance(shots, bool) or not isinstance(shots, int) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    return shots


def utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _is_binary_key(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value >= 0
    text = str(value).strip().lower()
    if text.startswith("0b"):
        text = text[2:]
    if text.startswith("0x"):
        try:
            int(text, 16)
            return True
        except ValueError:
            return False
    return bool(text) and set(text) <= {"0", "1"}


def _as_binary_key(value: Any, width: int) -> str:
    if isinstance(value, bool):
        raise ValueError("boolean is not a measurement key")

    if isinstance(value, int):
        number = value
    else:
        text = str(value).strip().lower()
        if text.startswith("0b"):
            number = int(text[2:], 2)
        elif text.startswith("0x"):
            number = int(text[2:], 16)
        elif set(text) <= {"0", "1"}:
            if len(text) > width:
                raise ValueError(
                    f"measurement key {text!r} is wider than {width} bits"
                )
            return text.zfill(width)
        else:
            number = int(text, 10)

    if number < 0 or number >= 2**width:
        raise ValueError(f"measurement key {value!r} does not fit {width} bits")
    return format(number, f"0{width}b")


def _numeric_mapping(value: Any) -> Optional[Dict[Any, float]]:
    if not isinstance(value, Mapping) or not value:
        return None
    converted: Dict[Any, float] = {}
    for key, raw in value.items():
        if not _is_binary_key(key):
            return None
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            try:
                raw = float(raw)
            except (TypeError, ValueError):
                return None
        number = float(raw)
        if not math.isfinite(number) or number < 0:
            return None
        converted[key] = number
    return converted


def extract_counts(payload: Any) -> Dict[Any, float]:
    """Find a measurement distribution inside a provider response.

    Provider SDKs use different wrappers (`counts`, `taskResult`, `obj`,
    `measurement_counts`, ...).  This function deliberately accepts only a
    mapping whose keys look like computational-basis states, so task metadata
    is not mistaken for a distribution.
    """

    direct = _numeric_mapping(payload)
    if direct is not None:
        return direct

    if isinstance(payload, Mapping):
        preferred = (
            "counts",
            "measurement_counts",
            "measurementCounts",
            "taskResult",
            "task_result",
            "result",
            "data",
            "obj",
            "output",
            "results",
        )
        for key in preferred:
            if key in payload:
                try:
                    return extract_counts(payload[key])
                except HardwareInterfaceError:
                    continue
        for value in payload.values():
            try:
                return extract_counts(value)
            except HardwareInterfaceError:
                continue

    if isinstance(payload, (list, tuple)):
        for value in payload:
            try:
                return extract_counts(value)
            except HardwareInterfaceError:
                continue

    raise HardwareInterfaceError("provider response does not contain measurement counts")


def extract_job_id(payload: Any) -> Optional[str]:
    """Extract a provider task identifier without exposing credentials."""

    if isinstance(payload, Mapping):
        for key in (
            "job_id",
            "jobId",
            "task_id",
            "taskId",
            "tid",
            "task_arn",
            "taskArn",
            "arn",
            "id",
        ):
            value = payload.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
        for value in payload.values():
            found = extract_job_id(value)
            if found:
                return found
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            found = extract_job_id(value)
            if found:
                return found
    return None


def _largest_remainder(values: Mapping[str, float], shots: int) -> Dict[str, int]:
    total = sum(values.values())
    if total <= 0:
        raise HardwareInterfaceError("provider returned an empty measurement distribution")

    raw = {key: value / total * shots for key, value in values.items()}
    counts = {key: int(math.floor(value)) for key, value in raw.items()}
    remainder = shots - sum(counts.values())
    order = sorted(
        raw,
        key=lambda key: (raw[key] - counts[key], key),
        reverse=True,
    )
    for key in order[:remainder]:
        counts[key] += 1
    return {key: value for key, value in counts.items() if value > 0}


def normalize_counts(
    raw_counts: Mapping[Any, Any],
    *,
    width: int,
    shots: int,
) -> Dict[str, int]:
    """Normalize counts or probabilities to exact little-endian shot counts."""

    positive_shots(shots)
    if not isinstance(raw_counts, Mapping) or not raw_counts:
        raise HardwareInterfaceError("provider returned no measurement counts")

    values: Dict[str, float] = {}
    for raw_key, raw_value in raw_counts.items():
        key = _as_binary_key(raw_key, width)
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise HardwareInterfaceError("provider returned a non-numeric count") from exc
        if not math.isfinite(value) or value < 0:
            raise HardwareInterfaceError("provider returned an invalid count")
        values[key] = values.get(key, 0.0) + value

    total = sum(values.values())
    if total <= 0:
        raise HardwareInterfaceError("provider returned an empty measurement distribution")

    integral = all(abs(value - round(value)) < 1e-9 for value in values.values())
    if integral and abs(total - shots) < 1e-9:
        return {
            key: int(round(value))
            for key, value in values.items()
            if value > 0
        }
    return _largest_remainder(values, shots)


def standard_result(
    *,
    backend: str,
    job_id: str,
    shots: int,
    counts: Mapping[str, int],
    meta: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    total = sum(int(value) for value in counts.values())
    if total != shots:
        raise HardwareInterfaceError(
            f"normalized counts total {total} does not equal shots {shots}"
        )
    result: Dict[str, Any] = {
        "backend": backend,
        "job_id": str(job_id),
        "shots": shots,
        "counts": {str(key): int(value) for key, value in counts.items()},
        "bit_order": "little",
        "timestamp": utc_timestamp(),
    }
    if meta:
        result["meta"] = dict(meta)
    return result


def measured_width(circuit: Any) -> int:
    return max(
        int(getattr(circuit, "num_clbits", 0)),
        int(getattr(circuit, "num_qubits", 0)),
        1,
    )
