"""Normalize provider execution results into the LoomQ L1 result schema.

Decimal count keys use a canonical ASCII representation: ``"0"`` is the only
zero representation, and non-zero values must not have leading zeroes.
"""

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from .errors import NormalizationError
from .model import RawExecution


MAX_WIDTH = 4096
MAX_KEY_LENGTH = 4096


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _validate_width(width: Any) -> None:
    if type(width) is not int or not 0 < width <= MAX_WIDTH:
        raise NormalizationError("width must be a positive bounded built-in integer")


def _validate_count(count: Any) -> None:
    if type(count) is not int or count < 0:
        raise NormalizationError("count values must be non-negative built-in integers")


def _parse_key(key: Any, width: int, key_format: str) -> int:
    limit = (1 << width) - 1

    if key_format == "integer":
        if type(key) is not int or key < 0:
            raise NormalizationError("integer keys must be non-negative built-in integers")
        value = key
    elif key_format == "decimal":
        if type(key) is not str or not key or len(key) > MAX_KEY_LENGTH:
            raise NormalizationError("decimal keys must be bounded non-empty ASCII strings")
        if (len(key) > 1 and key[0] == "0") or any(character < "0" or character > "9" for character in key):
            raise NormalizationError("decimal keys must be canonical non-negative ASCII decimals")
        if len(key) > len(str(limit)):
            raise NormalizationError("decimal key does not fit width")
        value = int(key, 10)
    else:
        if type(key) is not str or len(key) > MAX_KEY_LENGTH:
            raise NormalizationError("binary keys must be bounded ASCII strings")
        bits = []
        for character in key:
            if character == " ":
                continue
            if character not in ("0", "1"):
                raise NormalizationError("binary keys may contain only ASCII bits and spaces")
            bits.append(character)
        if not bits:
            raise NormalizationError("binary keys must contain at least one bit")
        if len(bits) > width:
            raise NormalizationError("binary key does not fit width")
        value = int("".join(bits), 2)

    if value > limit:
        raise NormalizationError("count key does not fit width")
    return value


def _normalize_counts(raw_counts: Any, width: int, key_format: Any, reverse_bits: Any) -> Dict[str, int]:
    _validate_width(width)
    if type(key_format) is not str or key_format not in ("binary", "decimal", "integer"):
        raise NormalizationError("unsupported count key format")
    if type(reverse_bits) is not bool:
        raise NormalizationError("reverse_bits must be a built-in bool")
    if not isinstance(raw_counts, Mapping):
        raise NormalizationError("raw_counts must be a non-empty mapping")
    if not raw_counts:
        raise NormalizationError("raw_counts must be a non-empty mapping")

    normalized: Dict[str, int] = {}
    for raw_key, count in raw_counts.items():
        _validate_count(count)
        value = _parse_key(raw_key, width, key_format)
        key = format(value, "0{}b".format(width))
        if reverse_bits:
            key = key[::-1]
        normalized[key] = normalized.get(key, 0) + count

    if not normalized:
        raise NormalizationError("normalized counts must not be empty")
    return normalized


def normalize_counts(raw_counts: Any, width: int, key_format: str, reverse_bits: bool) -> Dict[str, int]:
    """Convert provider count keys into width-padded canonical bit strings."""
    try:
        return _normalize_counts(raw_counts, width, key_format, reverse_bits)
    except NormalizationError:
        raise
    except Exception as error:
        raise NormalizationError("invalid raw counts") from error


def _validate_raw_execution(raw: Any) -> RawExecution:
    if not isinstance(raw, RawExecution):
        raise NormalizationError("raw must be a RawExecution")
    if type(raw.backend) is not str or not raw.backend:
        raise NormalizationError("raw backend must be a non-empty built-in string")
    if type(raw.job_id) is not str or not raw.job_id:
        raise NormalizationError("raw job_id must be a non-empty built-in string")
    if type(raw.metadata) is not dict:
        raise NormalizationError("raw metadata must be a dict")
    return raw


def _reject_mock_metadata(value: Any, seen: set[int]) -> None:
    value_id = id(value)
    if value_id in seen:
        return
    seen.add(value_id)

    if isinstance(value, Mapping):
        for key, child in value.items():
            if type(key) is str and key == "is_mock" and child is True:
                raise NormalizationError("mock execution results are not allowed")
            _reject_mock_metadata(child, seen)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for child in value:
            _reject_mock_metadata(child, seen)


def _copy_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    _reject_mock_metadata(metadata, set())
    return deepcopy(metadata)


def _timestamp_from(now: Any) -> str:
    if not callable(now):
        raise NormalizationError("now must be callable")
    timestamp = now()
    if type(timestamp) is not datetime:
        raise NormalizationError("now must return a built-in datetime")
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise NormalizationError("timestamp must be timezone-aware")
    return timestamp.isoformat()


def build_result(
    raw: RawExecution,
    width: int,
    shots: int,
    now: Callable[[], datetime] = utc_now,
) -> Dict[str, Any]:
    """Build a fresh official LoomQ result dictionary from a raw execution."""
    try:
        _validate_width(width)
        if type(shots) is not int or shots <= 0:
            raise NormalizationError("shots must be a positive built-in integer")
        raw = _validate_raw_execution(raw)
        counts = normalize_counts(raw.counts, width, raw.key_format, raw.reverse_bits)
        if sum(counts.values()) != shots:
            raise NormalizationError("normalized counts total must equal shots")
        timestamp = _timestamp_from(now)
        metadata = _copy_metadata(raw.metadata)
        return {
            "backend": raw.backend,
            "job_id": raw.job_id,
            "shots": shots,
            "counts": counts,
            "bit_order": "little",
            "timestamp": timestamp,
            "meta": metadata,
        }
    except NormalizationError:
        raise
    except Exception as error:
        raise NormalizationError("invalid raw execution") from error
