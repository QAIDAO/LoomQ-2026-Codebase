"""Dependency-free input validation shared by real-hardware runners."""

from pathlib import Path
from typing import Dict
from urllib.parse import urlparse

from .errors import ConfigurationError


MAX_QASM_BYTES = 1024 * 1024
MAX_SHOTS = 100_000


def read_qasm_file(path: str) -> str:
    qasm_path = Path(path).expanduser()
    try:
        resolved = qasm_path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ConfigurationError("QASM input file does not exist or cannot be resolved.") from None
    if not resolved.is_file():
        raise ConfigurationError("QASM input path must identify a regular file.")
    try:
        if resolved.stat().st_size > MAX_QASM_BYTES:
            raise ConfigurationError("QASM input exceeds the 1 MiB hardware-runner limit.")
        source = resolved.read_text(encoding="utf-8")
    except UnicodeError:
        raise ConfigurationError("QASM input must be valid UTF-8 text.") from None
    except OSError:
        raise ConfigurationError("QASM input file could not be read.") from None
    return validate_qasm2(source)


def validate_qasm2(source: str) -> str:
    if not isinstance(source, str):
        raise ConfigurationError("QASM input must be text.")
    encoded = source.encode("utf-8")
    if not source.strip():
        raise ConfigurationError("QASM input must not be empty.")
    if len(encoded) > MAX_QASM_BYTES:
        raise ConfigurationError("QASM input exceeds the 1 MiB hardware-runner limit.")
    if "\x00" in source:
        raise ConfigurationError("QASM input must not contain NUL bytes.")
    if not source.lstrip().startswith("OPENQASM 2.0;"):
        raise ConfigurationError("Hardware runners accept complete OpenQASM 2.0 input only.")
    if "qreg" not in source:
        raise ConfigurationError("QASM input must declare at least one quantum register.")
    return source


def validate_shots(shots: int) -> int:
    if isinstance(shots, bool) or not isinstance(shots, int):
        raise ConfigurationError("shots must be an integer.")
    if shots < 1 or shots > MAX_SHOTS:
        raise ConfigurationError("shots must be between 1 and 100000.")
    return shots


def validate_identifier(value: str, label: str, max_length: int = 128) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError("%s must be a non-empty string." % label)
    value = value.strip()
    if len(value) > max_length or any(ord(ch) < 32 for ch in value):
        raise ConfigurationError("%s contains invalid characters or is too long." % label)
    if any(ch in value for ch in ("/", "\\", "..")):
        raise ConfigurationError("%s must not contain path components." % label)
    return value


def validate_http_url(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError("%s is required." % label)
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ConfigurationError("%s must be an absolute HTTP(S) URL." % label)
    if parsed.username or parsed.password:
        raise ConfigurationError("%s must not embed credentials." % label)
    return value.strip().rstrip("/")


def dry_run_plan(provider: str, target: str, shots: int, qasm: str) -> Dict[str, object]:
    """Return a non-submitting plan.  Deliberately contains no ``job_id`` key."""

    import hashlib

    validate_shots(shots)
    validate_qasm2(qasm)
    return {
        "mode": "dry_run",
        "network_called": False,
        "vendor_imported": False,
        "evidence_written": False,
        "provider": provider,
        "target": target,
        "shots": shots,
        "input_sha256": hashlib.sha256(qasm.encode("utf-8")).hexdigest(),
    }
