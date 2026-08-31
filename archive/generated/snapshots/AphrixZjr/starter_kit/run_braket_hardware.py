#!/usr/bin/env python3
"""Explicit CLI for guarded AWS Braket QPU evidence runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from l1_braket import emit_braket_executable, run_braket
from l1_braket_hardware import (
    ENVIRONMENT_FIELDS,
    REQUIRED_ENVIRONMENT_FIELDS,
    SUBMISSION_CONFIRMATION,
    BraketHardwareConfig,
    BraketHardwareError,
    BraketHardwareRun,
    check_braket_hardware,
    run_braket_hardware,
    sanitize_for_json,
    write_json,
)
from loomq_l1 import normalize_counts, parse_qasm


HERE = Path(__file__).resolve().parent
PRIVATE_RECEIPT_DIR = HERE / ".hardware-private" / "braket"
CIRCUITS = {
    "bell": HERE / "circuits" / "bell.qasm",
    "ghz3": HERE / "circuits" / "ghz3.qasm",
    "bit_order": HERE / "circuits" / "bit_order.qasm",
}
CONFIRMATION = SUBMISSION_CONFIRMATION
MIN_HARDWARE_SUPPORT_PROBABILITY = 0.5
MIN_LOCAL_SUPPORT_PROBABILITY = 0.97
MAX_PRIVATE_RECEIPT_BYTES = 16 * 1024
PRIVATE_RECEIPT_SCHEMA_VERSION = 2
_CLIENT_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_PREPARED_RECEIPT_NAME_RE = re.compile(
    r"^braket-(bell|ghz3|bit_order)-([0-9a-f]{20})-prepared\.json$"
)
_SUBMITTED_RECEIPT_NAME_RE = re.compile(
    r"^braket-(bell|ghz3|bit_order)-([A-Za-z0-9._-]{1,128})-submitted\.json$"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_braket_hardware.py",
        description=(
            "Plan, check, or explicitly submit AWS Braket QPU jobs. "
            "No command submits without --confirm-submit %s." % CONFIRMATION
        ),
    )
    parser.add_argument(
        "mode",
        choices=(
            "plan",
            "check",
            "smoke",
            "formal",
            "submit-one",
            "retry-prepared",
            "resume",
        ),
        help=(
            "plan is offline; check is read-only; smoke runs Bell and the "
            "bit-order probe; formal runs Bell and GHZ-3; submit-one creates "
            "one explicit task; retry-prepared reuses one private idempotency "
            "receipt; resume polls one existing task without submitting"
        ),
    )
    parser.add_argument(
        "--confirm-submit",
        metavar="SUBMIT",
        help=(
            "exact literal required for smoke, formal, submit-one, and "
            "retry-prepared"
        ),
    )
    parser.add_argument(
        "--task-arn",
        help="existing AWS Braket quantum task ARN (resume mode only)",
    )
    parser.add_argument(
        "--client-token",
        help="clientToken from the original local submission receipt (resume only)",
    )
    parser.add_argument(
        "--circuit",
        choices=tuple(sorted(CIRCUITS)),
        help="explicit circuit for submit-one, retry-prepared, or resume",
    )
    parser.add_argument(
        "--shots",
        type=int,
        help=(
            "shots per circuit: smoke defaults to 100 and permits at most "
            "256; formal is fixed at 8192 and rejects this option; submit-one, "
            "and retry-prepared require explicit shots; resume requires the "
            "original task's shots"
        ),
    )
    parser.add_argument(
        "--prepared-receipt",
        help=(
            "basename of a PREPARED receipt inside the fixed private state "
            "directory (retry-prepared only)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=HERE / "evidence" / "files" / "braket",
        help=(
            "directory for sanitized public evidence artifacts; private "
            "recovery receipts always use the fixed ignored state directory"
        ),
    )
    return parser


def _validate_args(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> Tuple[int, List[str]]:
    if args.mode in {"plan", "check"}:
        if args.confirm_submit is not None:
            parser.error("%s mode does not accept --confirm-submit" % args.mode)
        if args.shots is not None:
            parser.error("%s mode does not accept --shots" % args.mode)
        if any(
            value is not None
            for value in (
                args.task_arn,
                args.client_token,
                args.circuit,
                args.prepared_receipt,
            )
        ):
            parser.error("%s mode does not accept execution arguments" % args.mode)
        return 0, []
    if args.mode == "resume":
        if args.confirm_submit is not None:
            parser.error("resume mode does not accept --confirm-submit")
        if not args.task_arn or not args.client_token or not args.circuit:
            parser.error(
                "resume mode requires --task-arn, --client-token, --circuit, and --shots"
            )
        if args.shots is None or args.shots <= 0:
            parser.error("resume mode requires a positive --shots value")
        if args.prepared_receipt is not None:
            parser.error("resume mode does not accept --prepared-receipt")
        return args.shots, [args.circuit]
    if args.mode in {"submit-one", "retry-prepared"}:
        if args.confirm_submit != CONFIRMATION:
            parser.error(
                "%s mode requires the exact flag --confirm-submit %s"
                % (args.mode, CONFIRMATION)
            )
        if args.task_arn is not None or args.client_token is not None:
            parser.error(
                "%s mode does not accept --task-arn or --client-token"
                % args.mode
            )
        if not args.circuit:
            parser.error("%s mode requires --circuit" % args.mode)
        if args.shots is None or args.shots <= 0:
            parser.error("%s mode requires a positive explicit --shots" % args.mode)
        maximum = 256 if args.circuit == "bit_order" else 8192
        if args.shots > maximum:
            parser.error(
                "%s %s is limited to at most %d shots"
                % (args.mode, args.circuit, maximum)
            )
        if args.mode == "submit-one" and args.prepared_receipt is not None:
            parser.error("submit-one mode does not accept --prepared-receipt")
        if args.mode == "retry-prepared" and not args.prepared_receipt:
            parser.error("retry-prepared mode requires --prepared-receipt")
        return args.shots, [args.circuit]
    if any(
        value is not None
        for value in (
            args.task_arn,
            args.client_token,
            args.circuit,
            args.prepared_receipt,
        )
    ):
        parser.error("single-task arguments are not accepted in batch modes")
    if args.confirm_submit != CONFIRMATION:
        parser.error(
            "%s mode requires the exact flag --confirm-submit %s"
            % (args.mode, CONFIRMATION)
        )
    if args.mode == "smoke":
        shots = 100 if args.shots is None else args.shots
        if shots <= 0:
            parser.error("--shots must be positive")
        if shots > 256:
            parser.error("smoke mode is limited to at most 256 shots per circuit")
        return shots, ["bell", "bit_order"]
    if args.shots is not None:
        parser.error("formal mode uses the fixed 8192 shots per circuit")
    return 8192, ["bell", "ghz3"]


def _safe_job_id(job_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", str(job_id)).strip(".-")
    return safe[:128] or "task"


def _expected_support(name: str) -> Tuple[str, ...]:
    if name == "bell":
        return ("00", "11")
    if name == "ghz3":
        return ("000", "111")
    if name == "bit_order":
        return ("011",)
    raise ValueError("unknown circuit: %s" % name)


def _dominance_summary(
    name: str, counts: Dict[str, int], shots: int
) -> Dict[str, object]:
    expected = _expected_support(name)
    ranked = sorted(
        (key for key, value in counts.items() if value > 0),
        key=lambda key: (-counts[key], key),
    )
    dominant = ranked[: min(len(expected), len(ranked))]
    expected_mass = sum(counts.get(key, 0) for key in expected) / shots
    dominant_states_match = (
        len(dominant) == len(expected) and set(dominant) == set(expected)
    )
    return {
        "expected_support": list(expected),
        "observed_dominant_states": dominant,
        "dominant_states_match": dominant_states_match,
        "expected_support_probability": expected_mass,
        "expected_support_threshold": MIN_HARDWARE_SUPPORT_PROBABILITY,
        "hardware_validation_passed": (
            dominant_states_match
            and expected_mass >= MIN_HARDWARE_SUPPORT_PROBABILITY
        ),
    }


def _run_local_preflight(name: str, circuit, shots: int) -> Dict[str, object]:
    raw, backend, _job_id, _meta = run_braket(circuit, shots)
    counts = normalize_counts(raw, shots, circuit.classical_count)
    dominance = _dominance_summary(name, counts, shots)
    if (
        not dominance["dominant_states_match"]
        or dominance["expected_support_probability"] < MIN_LOCAL_SUPPORT_PROBABILITY
    ):
        raise RuntimeError("AWS Braket LocalSimulator preflight failed for %s" % name)
    return {"backend": backend, "counts": counts, **dominance}


def _write_text_exclusive(path: Path, text: str) -> None:
    created = False
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            created = True
            handle.write(text)
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise


def _write_bundle(
    output_dir: Path,
    name: str,
    qasm2: str,
    run: BraketHardwareRun,
) -> Dict[str, Path]:
    stem = "braket-%s-%s" % (name, _safe_job_id(run.summary["job_id"]))
    qasm2_path = output_dir / (stem + ".qasm")
    qasm3_path = output_dir / (stem + ".braket.qasm")
    raw_path = output_dir / (stem + "-raw.json")
    summary_path = output_dir / (stem + "-summary.json")
    output_dir.mkdir(parents=True, exist_ok=True)
    created: List[Path] = []
    try:
        _write_text_exclusive(qasm2_path, qasm2)
        created.append(qasm2_path)
        _write_text_exclusive(qasm3_path, run.qasm3)
        created.append(qasm3_path)
        raw_record = sanitize_for_json(dict(run.raw_record))
        raw_record.update(
            {
                "circuit": name,
                "qasm_file": qasm2_path.name,
                "braket_qasm_file": qasm3_path.name,
            }
        )
        summary = sanitize_for_json(dict(run.summary))
        summary.update(
            {
                "circuit": name,
                "raw_result_file": raw_path.name,
                "qasm_file": qasm2_path.name,
                "braket_qasm_file": qasm3_path.name,
            }
        )
        summary.update(
            _dominance_summary(name, summary["counts"], summary["shots"])
        )
        write_json(raw_path, raw_record, exclusive=True)
        created.append(raw_path)
        write_json(summary_path, summary, exclusive=True)
        created.append(summary_path)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return {
        "qasm": qasm2_path,
        "braket_qasm": qasm3_path,
        "raw": raw_path,
        "summary": summary_path,
    }


def _receipt_key(client_token: str) -> str:
    return hashlib.sha256(client_token.encode("utf-8")).hexdigest()[:20]


def _canonical_create_request(
    config: BraketHardwareConfig,
    shots: int,
    qasm3: str,
    client_token: str,
) -> Dict[str, object]:
    """Mirror every argument passed to Boto3 CreateQuantumTask."""

    action = json.dumps(
        {
            "braketSchemaHeader": {
                "name": "braket.ir.openqasm.program",
                "version": "1",
            },
            "source": qasm3,
            "inputs": {},
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "_localAwsProfile": config.profile,
        "_localAwsRegion": config.region,
        "action": action,
        "clientToken": client_token,
        "deviceArn": config.device_arn,
        "deviceParameters": "{}",
        "outputS3Bucket": config.s3_bucket,
        "outputS3KeyPrefix": "%s/tasks/%s"
        % (config.s3_prefix, client_token),
        "shots": shots,
    }


def _request_sha256(
    config: BraketHardwareConfig,
    shots: int,
    qasm3: str,
    client_token: str,
) -> str:
    canonical = json.dumps(
        _canonical_create_request(config, shots, qasm3, client_token),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _unique_json_object(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    value: Dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def _path_is_reparse(path: Path) -> bool:
    """Detect symlinks and Windows junction/reparse points without following."""

    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError:
        raise BraketHardwareError(
            "AWS Braket private receipt path cannot be inspected"
        ) from None
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _ensure_private_receipt_dir(
    receipt_dir: Path,
    *,
    create: bool,
    expected_root: Optional[Path] = None,
) -> Path:
    """Safely create/validate a direct private state directory."""

    root = Path(receipt_dir)
    if expected_root is not None:
        lexical_root = Path(os.path.abspath(os.fspath(root)))
        lexical_expected = Path(os.path.abspath(os.fspath(expected_root)))
        if lexical_root != lexical_expected:
            raise BraketHardwareError(
                "AWS Braket private receipt directory is not the fixed directory"
            )
    parent = root.parent
    if _path_is_reparse(parent) or _path_is_reparse(root):
        raise BraketHardwareError(
            "AWS Braket private receipt directory cannot use a reparse point"
        )
    if not parent.exists():
        if not create:
            raise BraketHardwareError(
                "AWS Braket private receipt directory is unavailable"
            )
        grandparent = parent.parent
        if (
            not grandparent.is_dir()
            or _path_is_reparse(grandparent)
            or parent.parent == parent
        ):
            raise BraketHardwareError(
                "AWS Braket private receipt parent directory is unsafe"
            )
        try:
            parent.mkdir()
        except FileExistsError:
            pass
        except OSError:
            raise BraketHardwareError(
                "AWS Braket private receipt parent directory cannot be created"
            ) from None
    if not parent.is_dir() or _path_is_reparse(parent):
        raise BraketHardwareError(
            "AWS Braket private receipt parent directory is unsafe"
        )
    try:
        resolved_parent = parent.resolve(strict=True)
    except (OSError, RuntimeError):
        raise BraketHardwareError(
            "AWS Braket private receipt parent directory is unsafe"
        ) from None
    if not root.exists():
        if not create:
            raise BraketHardwareError(
                "AWS Braket private receipt directory is unavailable"
            )
        try:
            root.mkdir()
        except FileExistsError:
            pass
        except OSError:
            raise BraketHardwareError(
                "AWS Braket private receipt directory cannot be created"
            ) from None
    if not root.is_dir() or _path_is_reparse(root):
        raise BraketHardwareError(
            "AWS Braket private receipt directory is unsafe"
        )
    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise BraketHardwareError(
            "AWS Braket private receipt directory is unsafe"
        ) from None
    if resolved_root.parent != resolved_parent or _path_is_reparse(root):
        raise BraketHardwareError(
            "AWS Braket private receipt directory escapes its parent"
        )
    return root


def _read_private_json(
    receipt_dir: Path, filename: str
) -> Dict[str, object]:
    """Read one small, direct, non-symlink file from the private directory."""

    if (
        not isinstance(filename, str)
        or not re.fullmatch(r"[A-Za-z0-9._-]{1,240}", filename)
        or Path(filename).name != filename
    ):
        raise BraketHardwareError("AWS Braket private receipt name is invalid")
    root = _ensure_private_receipt_dir(receipt_dir, create=False)
    try:
        resolved_root = root.resolve(strict=True)
        candidate = root / filename
        if _path_is_reparse(candidate):
            raise BraketHardwareError(
                "AWS Braket private receipt cannot be a reparse point"
            )
        resolved = candidate.resolve(strict=True)
    except BraketHardwareError:
        raise
    except (OSError, RuntimeError):
        raise BraketHardwareError("AWS Braket private receipt is unavailable") from None
    if resolved.parent != resolved_root or not resolved.is_file():
        raise BraketHardwareError("AWS Braket private receipt path escapes its directory")
    try:
        size = resolved.stat().st_size
        if size <= 0 or size > MAX_PRIVATE_RECEIPT_BYTES:
            raise BraketHardwareError("AWS Braket private receipt size is invalid")
        with resolved.open("rb") as handle:
            encoded = handle.read(MAX_PRIVATE_RECEIPT_BYTES + 1)
        if len(encoded) > MAX_PRIVATE_RECEIPT_BYTES:
            raise BraketHardwareError("AWS Braket private receipt is too large")
        decoded = encoded.decode("utf-8")
        payload = json.loads(decoded, object_pairs_hook=_unique_json_object)
    except BraketHardwareError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise BraketHardwareError("AWS Braket private receipt is invalid") from None
    if not isinstance(payload, dict):
        raise BraketHardwareError("AWS Braket private receipt must be a JSON object")
    return payload


def _load_prepared_receipt(
    receipt_dir: Path,
    filename: str,
    name: str,
    shots: int,
    qasm3: str,
    config: BraketHardwareConfig,
) -> Dict[str, object]:
    match = _PREPARED_RECEIPT_NAME_RE.fullmatch(filename or "")
    if match is None or match.group(1) != name:
        raise BraketHardwareError("AWS Braket PREPARED receipt filename is invalid")
    payload = _read_private_json(receipt_dir, filename)
    expected_fields = {
        "schema_version",
        "provider",
        "state",
        "circuit",
        "shots",
        "clientToken",
        "qasm3_sha256",
        "request_sha256",
    }
    if set(payload) != expected_fields:
        raise BraketHardwareError("AWS Braket PREPARED receipt schema is invalid")
    client_token = payload.get("clientToken")
    if not isinstance(client_token, str) or not _CLIENT_TOKEN_RE.fullmatch(
        client_token
    ):
        raise BraketHardwareError("AWS Braket PREPARED receipt token is invalid")
    qasm3_sha256 = hashlib.sha256(qasm3.encode("utf-8")).hexdigest()
    request_sha256 = _request_sha256(config, shots, qasm3, client_token)
    expected_values = {
        "schema_version": PRIVATE_RECEIPT_SCHEMA_VERSION,
        "provider": "aws-braket",
        "state": "PREPARED",
        "circuit": name,
        "shots": shots,
        "qasm3_sha256": qasm3_sha256,
        "request_sha256": request_sha256,
    }
    if any(payload.get(key) != value for key, value in expected_values.items()):
        raise BraketHardwareError("AWS Braket PREPARED receipt does not match the request")
    if match.group(2) != _receipt_key(client_token):
        raise BraketHardwareError("AWS Braket PREPARED receipt filename token mismatch")
    return payload


def _write_prepared_receipt(
    output_dir: Path,
    name: str,
    shots: int,
    qasm3: str,
    client_token: str,
    request_sha256: str,
) -> Path:
    """Persist the idempotency token before the paid API call."""

    output_dir = _ensure_private_receipt_dir(output_dir, create=True)
    path = output_dir / (
        "braket-%s-%s-prepared.json" % (name, _receipt_key(client_token))
    )
    write_json(
        path,
        {
            "schema_version": PRIVATE_RECEIPT_SCHEMA_VERSION,
            "provider": "aws-braket",
            "state": "PREPARED",
            "circuit": name,
            "shots": shots,
            "clientToken": client_token,
            "qasm3_sha256": hashlib.sha256(qasm3.encode("utf-8")).hexdigest(),
            "request_sha256": request_sha256,
        },
        exclusive=True,
    )
    return path


def _submitted_receipt_payload(
    name: str,
    shots: int,
    qasm3: str,
    client_token: str,
    task_id: str,
    request_sha256: str,
) -> Dict[str, object]:
    return {
        "schema_version": PRIVATE_RECEIPT_SCHEMA_VERSION,
        "provider": "aws-braket",
        "state": "SUBMITTED",
        "circuit": name,
        "shots": shots,
        "clientToken": client_token,
        "job_id": task_id,
        "qasm3_sha256": hashlib.sha256(qasm3.encode("utf-8")).hexdigest(),
        "request_sha256": request_sha256,
    }


def _scan_matching_submitted_receipts(
    output_dir: Path,
    name: str,
    expected: Mapping[str, object],
) -> None:
    """Reject a token/request fingerprint already bound to another task."""

    root = _ensure_private_receipt_dir(output_dir, create=False)
    try:
        entries = list(root.iterdir())
    except OSError:
        raise BraketHardwareError(
            "AWS Braket private SUBMITTED receipts cannot be scanned"
        ) from None
    expected_token = expected["clientToken"]
    expected_request = expected["request_sha256"]
    expected_task_name = _safe_job_id(str(expected["job_id"]))
    for entry in entries:
        match = _SUBMITTED_RECEIPT_NAME_RE.fullmatch(entry.name)
        if match is None:
            continue
        payload = _read_private_json(root, entry.name)
        token_matches = payload.get("clientToken") == expected_token
        request_matches = payload.get("request_sha256") == expected_request
        if not token_matches and not request_matches:
            continue
        if (
            payload != dict(expected)
            or match.group(1) != name
            or match.group(2) != expected_task_name
        ):
            raise BraketHardwareError(
                "AWS Braket SUBMITTED receipt fingerprint is bound to a different task"
            )


def _write_submitted_receipt(
    output_dir: Path,
    name: str,
    shots: int,
    qasm3: str,
    client_token: str,
    task_id: str,
    request_sha256: str,
    *,
    allow_existing: bool = False,
) -> Path:
    """Persist the safe task identifier immediately after CreateQuantumTask."""

    output_dir = _ensure_private_receipt_dir(output_dir, create=True)
    path = output_dir / (
        "braket-%s-%s-submitted.json" % (name, _safe_job_id(task_id))
    )
    payload = _submitted_receipt_payload(
        name,
        shots,
        qasm3,
        client_token,
        task_id,
        request_sha256,
    )
    if allow_existing:
        _scan_matching_submitted_receipts(output_dir, name, payload)
    created = False
    try:
        write_json(path, payload, exclusive=True)
        created = True
    except FileExistsError:
        if not allow_existing:
            raise
        existing = _read_private_json(output_dir, path.name)
        if existing != payload:
            raise BraketHardwareError(
                "AWS Braket existing SUBMITTED receipt does not match the retry"
            ) from None
    if allow_existing:
        try:
            _scan_matching_submitted_receipts(output_dir, name, payload)
        except Exception:
            if created:
                path.unlink(missing_ok=True)
            raise
    return path


def _write_failure_evidence(
    output_dir: Path,
    name: str,
    qasm2: str,
    qasm3: str,
    error: BraketHardwareError,
    local_preflight: Mapping[str, object],
    fallback_client_token: Optional[str] = None,
) -> Optional[Path]:
    """Exclusively archive every failure known to follow a paid submission."""

    raw_record = error.raw_record
    if not isinstance(raw_record, Mapping):
        return None
    task_id = raw_record.get("job_id")
    if isinstance(task_id, str) and task_id:
        evidence_id = _safe_job_id(task_id)
    elif (
        raw_record.get("submission_attempted") is True
        and isinstance(fallback_client_token, str)
        and fallback_client_token
    ):
        evidence_id = "submission-" + _receipt_key(fallback_client_token)
        task_id = None
    else:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / (
        "braket-%s-%s-failure.json" % (name, evidence_id)
    )
    payload = {
        "schema_version": 1,
        "provider": "aws-braket",
        "outcome": "FAILURE",
        "circuit": name,
        "job_id": task_id,
        "error_type": type(error).__name__,
        "error": str(error),
        "qasm2_sha256": hashlib.sha256(qasm2.encode("utf-8")).hexdigest(),
        "qasm3_sha256": hashlib.sha256(qasm3.encode("utf-8")).hexdigest(),
        "local_preflight": dict(local_preflight),
        "raw_record": dict(raw_record),
    }
    write_json(path, sanitize_for_json(payload), exclusive=True)
    return path


def _print_plan() -> None:
    print("AWS Braket QPU fallback plan (offline; no AWS call made)")
    print("1. smoke bell: 100 shots")
    print("2. smoke bit_order: 100 shots")
    print("3. formal bell: 8192 shots")
    print("4. formal ghz3: 8192 shots")
    print("total: 4 QPU tasks, 16584 shots")
    print("configuration environment fields (values are never printed):")
    required = set(REQUIRED_ENVIRONMENT_FIELDS)
    for name in ENVIRONMENT_FIELDS:
        print("- %s (%s)" % (name, "required" if name in required else "optional"))
    print("submission confirmation: --confirm-submit %s" % CONFIRMATION)


def _execute(
    names: Sequence[str],
    shots: int,
    output_dir: Path,
    config: BraketHardwareConfig,
    *,
    resume_task_arn: Optional[str] = None,
    resume_client_token: Optional[str] = None,
    retry_prepared_name: Optional[str] = None,
    receipt_dir: Optional[Path] = None,
) -> int:
    private_receipt_dir = (
        PRIVATE_RECEIPT_DIR if receipt_dir is None else receipt_dir
    )
    if resume_task_arn is None:
        _ensure_private_receipt_dir(
            private_receipt_dir,
            create=retry_prepared_name is None,
            expected_root=(PRIVATE_RECEIPT_DIR if receipt_dir is None else None),
        )
    loaded = []
    for name in names:
        qasm2 = CIRCUITS[name].read_text(encoding="utf-8")
        loaded.append((name, qasm2, parse_qasm(qasm2)))

    if retry_prepared_name is not None and resume_task_arn is not None:
        raise ValueError("retry-prepared and resume are mutually exclusive")
    retry_client_token: Optional[str] = None
    if retry_prepared_name is not None:
        if len(loaded) != 1:
            raise ValueError("retry-prepared accepts exactly one circuit")
        retry_name, _retry_qasm2, retry_circuit = loaded[0]
        retry_qasm3 = emit_braket_executable(retry_circuit)
        prepared = _load_prepared_receipt(
            private_receipt_dir,
            retry_prepared_name,
            retry_name,
            shots,
            retry_qasm3,
            config,
        )
        retry_client_token = str(prepared["clientToken"])

    # Every selected circuit must pass locally before the first paid submission.
    preflights = {}
    for name, _qasm2, circuit in loaded:
        preflights[name] = _run_local_preflight(name, circuit, shots)
        print("local preflight passed: %s" % name)

    for name, qasm2, circuit in loaded:
        qasm3 = emit_braket_executable(circuit)
        client_token = (
            resume_client_token or retry_client_token or uuid.uuid4().hex
        )
        request_sha256 = _request_sha256(config, shots, qasm3, client_token)
        if resume_task_arn is None and retry_client_token is None:
            _write_prepared_receipt(
                private_receipt_dir,
                name,
                shots,
                qasm3,
                client_token,
                request_sha256,
            )

        def submitted(task_id: str, circuit_name: str = name) -> None:
            if resume_task_arn is None:
                _write_submitted_receipt(
                    private_receipt_dir,
                    circuit_name,
                    shots,
                    qasm3,
                    client_token,
                    task_id,
                    request_sha256,
                    allow_existing=retry_client_token is not None,
                )
            print(
                "AWS Braket task identified for %s: %s"
                % (circuit_name, _safe_job_id(task_id))
            )

        run: Optional[BraketHardwareRun] = None
        try:
            run = run_braket_hardware(
                circuit,
                shots,
                config,
                confirmation=(
                    None if resume_task_arn is not None else CONFIRMATION
                ),
                on_submitted=submitted,
                client_token=client_token,
                resume_task_arn=resume_task_arn,
            )
            summary = dict(run.summary)
            summary["local_preflight"] = sanitize_for_json(preflights[name])
            run = BraketHardwareRun(run.qasm3, run.raw_record, summary)
            hardware = _dominance_summary(name, summary["counts"], shots)
            if not hardware["hardware_validation_passed"]:
                raise BraketHardwareError(
                    "AWS Braket hardware validation failed for %s" % name,
                    run.raw_record,
                )
            _write_bundle(output_dir, name, qasm2, run)
        except BraketHardwareError as exc:
            _write_failure_evidence(
                output_dir,
                name,
                qasm2,
                qasm3,
                exc,
                preflights[name],
                client_token,
            )
            raise
        except Exception:
            if run is None:
                raise
            error = BraketHardwareError(
                "AWS Braket evidence archival failed", run.raw_record
            )
            _write_failure_evidence(
                output_dir,
                name,
                qasm2,
                qasm3,
                error,
                preflights[name],
                client_token,
            )
            raise error from None
        print(
            "hardware evidence passed: %s (%s)"
            % (name, _safe_job_id(run.summary["job_id"]))
        )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    shots, names = _validate_args(parser, args)
    if args.mode == "plan":
        _print_plan()
        return 0
    try:
        config = BraketHardwareConfig.from_env()
        if args.mode == "check":
            report = check_braket_hardware(config)
            print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
            return 0 if (
                report["read_only_configuration_valid"]
                and report["qpu_online"]
            ) else 1
        return _execute(
            names,
            shots,
            args.output_dir,
            config,
            resume_task_arn=args.task_arn if args.mode == "resume" else None,
            resume_client_token=(
                args.client_token if args.mode == "resume" else None
            ),
            retry_prepared_name=(
                args.prepared_receipt
                if args.mode == "retry-prepared"
                else None
            ),
        )
    except (BraketHardwareError, ValueError, OSError, RuntimeError) as exc:
        # Core exceptions are already redacted.  Keep generic CLI failures terse
        # so SDK request metadata cannot escape through an exception repr.
        if isinstance(exc, BraketHardwareError):
            print(str(exc), file=sys.stderr)
        elif isinstance(exc, ValueError):
            print(str(exc), file=sys.stderr)
        else:
            print("AWS Braket hardware command failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
