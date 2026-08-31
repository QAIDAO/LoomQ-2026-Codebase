"""Prepare traceable QPU evidence without submitting a QPU task.

Live QPU submission is intentionally unsupported until a provider account can
provide its exact, current API contract.  This module therefore only performs
local parse/emit dry-runs and imports a small, validated provider result.
"""

import argparse
from collections.abc import Mapping
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
from typing import Any

from starter_kit.loomq_l1.emitters import emit
from starter_kit.loomq_l1.errors import CredentialError, NormalizationError
from starter_kit.loomq_l1.model import RawExecution
from starter_kit.loomq_l1.normalize import build_result
from starter_kit.loomq_l1.parser import parse_qasm


SUPPORTED_PROVIDERS = ("spinq", "originq", "braket")
CREDENTIAL_VARIABLES = frozenset(
    (
        "SPINQ_API_TOKEN",
        "ORIGINQ_API_TOKEN",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_ROLE_ARN",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "AWS_BRAKET_DEVICE_ARN",
    )
)
_JOB_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_REQUIRED_RESULT_FIELDS = frozenset(("provider", "job_id", "timestamp", "shots", "counts"))
_REVERSE_BITS = {"spinq": True, "originq": False, "braket": True}


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=SUPPORTED_PROVIDERS)
    parser.add_argument("--qasm", required=True)
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--import-result")
    parser.add_argument("--output-dir")
    arguments = parser.parse_args(argv)
    if arguments.shots <= 0:
        parser.error("--shots must be positive")
    if arguments.dry_run and arguments.import_result:
        parser.error("--dry-run and --import-result cannot be combined")
    if arguments.import_result and not arguments.output_dir:
        parser.error("--output-dir is required with --import-result")
    return arguments


def _read_qasm(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _has_value(environ: Mapping[str, str], name: str) -> bool:
    return type(environ.get(name)) is str and bool(environ.get(name))


def _credentials_available(provider: str, environ: Mapping[str, str]) -> bool:
    if provider == "spinq":
        return _has_value(environ, "SPINQ_API_TOKEN")
    if provider == "originq":
        return _has_value(environ, "ORIGINQ_API_TOKEN")

    has_aws_chain = (
        (_has_value(environ, "AWS_ACCESS_KEY_ID") and _has_value(environ, "AWS_SECRET_ACCESS_KEY"))
        or _has_value(environ, "AWS_PROFILE")
        or (_has_value(environ, "AWS_ROLE_ARN") and _has_value(environ, "AWS_WEB_IDENTITY_TOKEN_FILE"))
        or _has_value(environ, "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
        or _has_value(environ, "AWS_CONTAINER_CREDENTIALS_FULL_URI")
    )
    return has_aws_chain and _has_value(environ, "AWS_BRAKET_DEVICE_ARN")


def _live_submission() -> None:
    """Kept separate so a future audited implementation has an explicit seam."""
    raise CredentialError("live QPU submission is intentionally unsupported")


def _refuse_live_submission(provider: str, environ: Mapping[str, str]) -> None:
    if not _credentials_available(provider, environ):
        raise CredentialError("required credentials are unavailable")
    raise CredentialError("live QPU submission is intentionally unsupported")


def _utc_timestamp(value: Any) -> datetime:
    if type(value) is not str or not value or len(value) > 128:
        raise ValueError("provider timestamp must be a non-empty UTC timestamp")
    source = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        timestamp = datetime.fromisoformat(source)
    except ValueError:
        raise ValueError("provider timestamp must be a valid UTC timestamp") from None
    if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
        raise ValueError("provider timestamp must be a valid UTC timestamp")
    return timestamp


def _validated_import(value: Any, selected_provider: str) -> tuple[dict[str, Any], datetime]:
    if type(value) is not dict or not _REQUIRED_RESULT_FIELDS.issubset(value):
        raise ValueError("provider result is missing required fields")

    provider = value["provider"]
    if type(provider) is not str or provider not in SUPPORTED_PROVIDERS:
        raise ValueError("provider result has an unsupported provider")
    if provider != selected_provider:
        raise ValueError("provider result does not match --provider")

    job_id = value["job_id"]
    if type(job_id) is not str or _JOB_ID.fullmatch(job_id) is None:
        raise ValueError("provider result job_id is invalid")

    timestamp = _utc_timestamp(value["timestamp"])
    shots = value["shots"]
    if type(shots) is not int or shots <= 0:
        raise ValueError("provider result shots must be a positive integer")

    counts = value["counts"]
    if type(counts) is not dict or not counts:
        raise ValueError("provider result counts must be a non-empty object")
    for key, count in counts.items():
        if type(key) is not str or not key or any(bit not in "01" for bit in key):
            raise ValueError("provider result counts must use non-empty bitstrings")
        if type(count) is not int or count < 0:
            raise ValueError("provider result counts must use non-negative integers")
    if sum(counts.values()) != shots:
        raise ValueError("provider result counts must total shots")

    return {
        "provider": provider,
        "job_id": job_id,
        "timestamp": value["timestamp"],
        "shots": shots,
        "counts": dict(counts),
    }, timestamp


def _normalized_result(result: dict[str, Any], timestamp: datetime, width: int) -> dict[str, Any]:
    try:
        return build_result(
            RawExecution(
                backend=result["provider"],
                job_id=result["job_id"],
                counts=result["counts"],
                key_format="binary",
                reverse_bits=_REVERSE_BITS[result["provider"]],
                metadata={"provider": result["provider"]},
            ),
            width=width,
            shots=result["shots"],
            now=lambda: timestamp,
        )
    except NormalizationError as error:
        raise ValueError("provider result counts do not match the circuit") from error


def _write_new(path: Path, content: str) -> None:
    opened = False
    try:
        destination = path.open("x", encoding="utf-8", newline="\n")
        opened = True
        with destination:
            destination.write(content)
    except Exception:
        if opened:
            path.unlink(missing_ok=True)
        raise


def _write_evidence(
    output_directory: str, provider: str, job_id: str, qasm: str, native_ir: str,
    raw_result: dict[str, Any], normalized_result: dict[str, Any],
) -> None:
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir():
        raise ValueError("--output-dir must name a directory")
    base = f"{provider}-{job_id}"
    artifacts = (
        (directory / f"{base}-submission.qasm", qasm),
        (directory / f"{base}.native.ir", native_ir),
        (directory / f"{base}.raw-result.json", json.dumps(raw_result, ensure_ascii=False, indent=2) + "\n"),
        (directory / f"{base}.normalized-result.json", json.dumps(normalized_result, ensure_ascii=False, indent=2) + "\n"),
    )
    if any(path.exists() for path, _content in artifacts):
        raise FileExistsError("refusing to overwrite existing evidence artifacts")

    created: list[Path] = []
    try:
        for path, content in artifacts:
            _write_new(path, content)
            created.append(path)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    """Run the local-only evidence CLI and return a shell-compatible status."""
    arguments = _arguments(argv)
    qasm = _read_qasm(arguments.qasm)
    circuit = parse_qasm(qasm)
    native_ir = emit(circuit, arguments.provider)

    if arguments.dry_run:
        print(native_ir, end="")
        return 0
    if arguments.import_result:
        imported = json.loads(Path(arguments.import_result).read_text(encoding="utf-8"))
        raw_result, timestamp = _validated_import(imported, arguments.provider)
        normalized = _normalized_result(raw_result, timestamp, circuit.num_clbits)
        _write_evidence(
            arguments.output_dir,
            arguments.provider,
            raw_result["job_id"],
            qasm,
            native_ir,
            raw_result,
            normalized,
        )
        return 0

    _refuse_live_submission(arguments.provider, os.environ if environ is None else environ)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
