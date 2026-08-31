"""Standard-library normalization and atomic QPU evidence recording."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any, Dict, Mapping, Optional, Sequence
from uuid import uuid4

from .errors import EvidenceError, ResultValidationError


SCHEMA_VERSION = "loomq.hardware.evidence/v1"
SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "email",
    "password",
    "private",
    "secret",
    "signature",
    "token",
    "username",
)


@dataclass(frozen=True)
class EvidenceBundle:
    """All artifacts required for one admitted real-QPU execution."""

    provider: str
    input_qasm: str
    submission: Mapping[str, Any]
    raw_result: Any
    normalized_result: Mapping[str, Any]
    metadata: Mapping[str, Any]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ResultValidationError("timestamp must be a timezone-aware ISO-8601 string.")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        raise ResultValidationError("timestamp must be a timezone-aware ISO-8601 string.") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResultValidationError("timestamp must include a timezone offset.")
    return parsed


def normalize_counts(raw_counts: Mapping[Any, Any], shots: int) -> Dict[str, int]:
    if isinstance(shots, bool) or not isinstance(shots, int) or shots < 1:
        raise ResultValidationError("shots must be a positive integer.")
    if not isinstance(raw_counts, Mapping) or not raw_counts:
        raise ResultValidationError("hardware counts must be a non-empty mapping.")

    counts: Dict[str, int] = {}
    width: Optional[int] = None
    for raw_key, raw_value in raw_counts.items():
        if not isinstance(raw_key, str) or not raw_key or any(ch not in "01" for ch in raw_key):
            raise ResultValidationError("hardware count keys must be non-empty binary strings.")
        if width is None:
            width = len(raw_key)
        elif len(raw_key) != width:
            raise ResultValidationError("hardware count keys must have a uniform width.")
        if isinstance(raw_value, bool) or not isinstance(raw_value, int) or raw_value < 0:
            raise ResultValidationError("hardware count values must be non-negative integers.")
        counts[raw_key] = counts.get(raw_key, 0) + raw_value

    if sum(counts.values()) != shots:
        raise ResultValidationError("hardware counts must sum exactly to shots.")
    return dict(sorted(counts.items()))


def make_hardware_result(
    backend: str,
    job_id: str,
    shots: int,
    counts: Mapping[Any, Any],
    provider: str,
    timestamp: Optional[str] = None,
    meta: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    result = {
        "backend": backend,
        "job_id": job_id,
        "shots": shots,
        "counts": normalize_counts(counts, shots),
        "bit_order": "vendor_native",
        "timestamp": timestamp or utc_timestamp(),
        "meta": {
            "execution_mode": "qpu",
            "qpu_verified": True,
            "native_sdk_used": True,
            "provider": provider,
            **dict(meta or {}),
        },
    }
    validate_hardware_result(result)
    return result


def validate_hardware_result(result: Mapping[str, Any]) -> None:
    if not isinstance(result, Mapping):
        raise ResultValidationError("normalized hardware result must be a mapping.")
    for field in ("backend", "job_id", "shots", "counts", "bit_order", "timestamp", "meta"):
        if field not in result:
            raise ResultValidationError("normalized hardware result is missing %s." % field)
    if not isinstance(result["backend"], str) or not result["backend"].strip():
        raise ResultValidationError("backend must be non-empty.")
    if not isinstance(result["job_id"], str) or not result["job_id"].strip():
        raise ResultValidationError("a vendor-issued job_id is required.")
    normalize_counts(result["counts"], result["shots"])
    if result["bit_order"] not in ("vendor_native", "little"):
        raise ResultValidationError("bit_order must be vendor_native or little.")
    _parse_timestamp(result["timestamp"])
    meta = result["meta"]
    if not isinstance(meta, Mapping):
        raise ResultValidationError("meta must be a mapping.")
    if meta.get("execution_mode") != "qpu" or meta.get("qpu_verified") is not True:
        raise ResultValidationError("only a verified QPU response is admissible as hardware evidence.")
    if meta.get("native_sdk_used") is not True:
        raise ResultValidationError("hardware evidence must come from a native vendor SDK.")


def redact_payload(value: Any, secret_values: Sequence[str] = ()) -> Any:
    """Return JSON-safe data with credential-looking fields and values removed."""

    secrets = tuple(item for item in secret_values if isinstance(item, str) and item)
    if isinstance(value, Mapping):
        clean: Dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            lowered = text_key.lower().replace("-", "_")
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                clean[text_key] = "[REDACTED]"
            else:
                clean[text_key] = redact_payload(item, secrets)
        return clean
    if isinstance(value, (list, tuple)):
        return [redact_payload(item, secrets) for item in value]
    if isinstance(value, str):
        clean_text = value
        for secret in secrets:
            clean_text = clean_text.replace(secret, "[REDACTED]")
        return clean_text
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        raise EvidenceError("evidence contains data that cannot be encoded as strict JSON.") from None
    return (text + "\n").encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(".%s.%s.tmp" % (path.name, uuid4().hex))
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _is_within(child: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath((str(child), str(parent))) == str(parent)
    except ValueError:
        return False


def record_evidence(
    root: str,
    bundle: EvidenceBundle,
    secret_values: Sequence[str] = (),
) -> Path:
    """Atomically commit a complete evidence directory below ``root``.

    No directory is created until the result has passed QPU admission.  A
    same-filesystem directory rename makes the final five-file bundle visible
    as one commit.
    """

    validate_hardware_result(bundle.normalized_result)
    if bundle.provider not in ("spinq", "originq"):
        raise EvidenceError("provider must be spinq or originq.")
    metadata = dict(bundle.metadata)
    if metadata.get("execution_kind") != "qpu" or metadata.get("qpu_verified") is not True:
        raise EvidenceError("metadata must independently attest a verified QPU execution.")
    if metadata.get("job_id") != bundle.normalized_result.get("job_id"):
        raise EvidenceError("metadata and normalized result job IDs must match.")
    _parse_timestamp(metadata.get("timestamp"))

    raw_root = Path(root).expanduser()
    if raw_root.exists() and raw_root.is_symlink():
        raise EvidenceError("evidence root must not be a symbolic link.")
    try:
        raw_root.mkdir(parents=True, exist_ok=True)
        resolved_root = raw_root.resolve(strict=True)
    except OSError:
        raise EvidenceError("evidence root could not be created safely.") from None
    if not resolved_root.is_dir():
        raise EvidenceError("evidence root must be a directory.")

    nonce = uuid4().hex
    staging = resolved_root / (".staging-" + nonce)
    final = resolved_root / ("%s-%s" % (bundle.provider, nonce))
    if not _is_within(staging, resolved_root) or not _is_within(final, resolved_root):
        raise EvidenceError("evidence path escaped the configured root.")

    clean_submission = redact_payload(bundle.submission, secret_values)
    clean_raw = redact_payload(bundle.raw_result, secret_values)
    clean_normalized = redact_payload(bundle.normalized_result, secret_values)
    clean_metadata = redact_payload(metadata, secret_values)
    artifacts = {
        "input.qasm": bundle.input_qasm.encode("utf-8"),
        "submission.json": _json_bytes(clean_submission),
        "raw_result.json": _json_bytes(clean_raw),
        "normalized_result.json": _json_bytes(clean_normalized),
    }
    clean_metadata["schema_version"] = SCHEMA_VERSION
    clean_metadata["artifact_sha256"] = {
        name: _sha256(content) for name, content in sorted(artifacts.items())
    }
    artifacts["metadata.json"] = _json_bytes(clean_metadata)

    try:
        staging.mkdir()
        for filename, content in artifacts.items():
            _atomic_write(staging / filename, content)
        os.replace(str(staging), str(final))
    except OSError:
        if staging.exists() and _is_within(staging, resolved_root):
            shutil.rmtree(staging, ignore_errors=True)
        raise EvidenceError("hardware evidence could not be committed atomically.") from None
    return final
