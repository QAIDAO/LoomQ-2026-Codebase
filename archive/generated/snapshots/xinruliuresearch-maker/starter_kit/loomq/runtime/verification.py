"""Fail-closed admission checks for runtime results."""

from datetime import datetime
from typing import Any, Dict, Mapping

from ..errors import SimulationError


REQUIRED_FIELDS = ("backend", "job_id", "shots", "counts", "bit_order", "timestamp")
SENSITIVE_KEY_FRAGMENTS = ("api_key", "apikey", "authorization", "cookie", "password", "secret", "token")


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            if any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS):
                return True
            if _contains_sensitive_key(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def admit_result(payload: Dict[str, Any], requested_shots: int, classical_bits: int) -> Dict[str, Any]:
    """Validate the strict official schema before a result leaves the adapter."""
    if not isinstance(payload, dict):
        raise SimulationError("runtime result must be a dictionary")
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise SimulationError("runtime result is missing: %s" % ", ".join(missing))
    if not isinstance(payload["backend"], str) or not payload["backend"].strip():
        raise SimulationError("runtime backend must be a non-empty string")
    if not isinstance(payload["job_id"], str) or not payload["job_id"].startswith("local-sim-"):
        raise SimulationError("reference runtime job_id must use the honest local-sim prefix")
    if payload["shots"] != requested_shots or isinstance(payload["shots"], bool):
        raise SimulationError("runtime shots must equal the requested shots")
    counts = payload["counts"]
    if not isinstance(counts, dict) or not counts:
        raise SimulationError("runtime counts must be a non-empty dictionary")
    for key, value in counts.items():
        if not isinstance(key, str) or len(key) != classical_bits or set(key) - {"0", "1"}:
            raise SimulationError("runtime counts keys must be fixed-width binary strings")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise SimulationError("runtime counts values must be non-negative integers")
    if sum(counts.values()) != requested_shots:
        raise SimulationError("runtime counts must sum exactly to shots")
    if payload["bit_order"] != "little":
        raise SimulationError("runtime bit_order must be little")
    timestamp = payload["timestamp"]
    if not isinstance(timestamp, str):
        raise SimulationError("runtime timestamp must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SimulationError("runtime timestamp is not valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise SimulationError("runtime timestamp must include a timezone")
    if payload.get("meta", {}).get("is_mock"):
        raise SimulationError("mock runtime results are prohibited")
    if _contains_sensitive_key(payload):
        raise SimulationError("runtime result contains a sensitive field name")
    return payload
