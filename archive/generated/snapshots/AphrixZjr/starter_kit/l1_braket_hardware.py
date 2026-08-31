"""Guarded AWS Braket QPU execution for LoomQ L1.

The module deliberately uses the low-level Boto3 Braket and S3 clients.  The
high-level Braket SDK remains responsible only for the offline LocalSimulator
preflight in :mod:`run_braket_hardware`.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Sequence, Tuple

from l1_braket import emit_braket_executable
from loomq_l1 import Circuit


PROFILE_ENV = "LOOMQ_BRAKET_AWS_PROFILE"
REGION_ENV = "LOOMQ_BRAKET_AWS_REGION"
DEVICE_ARN_ENV = "LOOMQ_BRAKET_DEVICE_ARN"
S3_BUCKET_ENV = "LOOMQ_BRAKET_S3_BUCKET"
S3_PREFIX_ENV = "LOOMQ_BRAKET_S3_PREFIX"
POLL_INTERVAL_ENV = "LOOMQ_BRAKET_POLL_INTERVAL_SECONDS"
JOB_TIMEOUT_ENV = "LOOMQ_BRAKET_JOB_TIMEOUT_SECONDS"
SUBMISSION_CONFIRMATION = "AWS_BRAKET_QPU"
DEFAULT_S3_PREFIX = "loomq/l1"
DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_JOB_TIMEOUT_SECONDS = 432000.0
MAX_POLL_INTERVAL_SECONDS = 300.0
MAX_JOB_TIMEOUT_SECONDS = 604800.0
MAX_RESULT_BYTES = 10 * 1024 * 1024
MAX_CONSECUTIVE_POLL_ERRORS = 3

REQUIRED_ENVIRONMENT_FIELDS = (
    PROFILE_ENV,
    REGION_ENV,
    DEVICE_ARN_ENV,
    S3_BUCKET_ENV,
)
OPTIONAL_ENVIRONMENT_FIELDS = (
    S3_PREFIX_ENV,
    POLL_INTERVAL_ENV,
    JOB_TIMEOUT_ENV,
)
ENVIRONMENT_FIELDS = REQUIRED_ENVIRONMENT_FIELDS + OPTIONAL_ENVIRONMENT_FIELDS

_PENDING_STATES = {"CREATED", "QUEUED", "RUNNING", "CANCELLING"}
_FAILED_STATES = {"FAILED", "CANCELLED"}
_PROFILE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_REGION_RE = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z]+-\d+$")
_DEVICE_ARN_RE = re.compile(
    r"^arn:(aws(?:-cn|-us-gov)?):braket:([a-z0-9-]+)::"
    r"device/qpu/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$"
)
_TASK_ARN_RE = re.compile(
    r"^arn:(?:aws(?:-cn|-us-gov)?):braket:[a-z0-9-]+:\d{12}:"
    r"quantum-task/([A-Za-z0-9._-]{1,128})$"
)
_SENSITIVE_KEY_RE = re.compile(
    r"(?:secret|token|password|authorization|cookie|access.?key|account|"
    r"profile|bucket|responsemetadata|httpheaders|requestid)",
    re.IGNORECASE,
)
_ACCESS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_ARN_ACCOUNT_RE = re.compile(
    r"(arn:(?:aws(?:-cn|-us-gov)?):[A-Za-z0-9-]+:[A-Za-z0-9-]*:)"
    r"\d{12}(?=:)",
    re.IGNORECASE,
)
_LABELED_ACCOUNT_RE = re.compile(
    r"(\baccount(?:\s*id)?\s*[:=]\s*)\d{12}\b",
    re.IGNORECASE,
)
_CLIENT_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class BraketHardwareError(RuntimeError):
    """A safe-to-display Braket hardware error."""

    def __init__(
        self, message: str, raw_record: Optional[Mapping[str, Any]] = None
    ) -> None:
        super().__init__(message)
        self.raw_record = dict(raw_record) if raw_record is not None else None


class BraketHardwareTimeout(BraketHardwareError):
    """The local wait ended while the remote task remained active."""


class BraketHardwareJobFailed(BraketHardwareError):
    """The remote task entered a terminal failure state."""


def _required_text(name: str, environment: Mapping[str, str]) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ValueError("missing required environment variable: %s" % name)
    lowered = value.lower()
    if any(marker in lowered for marker in ("change-me", "changeme", "example", "your-")):
        raise ValueError("environment variable %s still contains a placeholder" % name)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("environment variable %s contains control characters" % name)
    return value


def _positive_float(name: str, raw: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError("%s must be a positive number" % name) from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError("%s must be a positive number" % name)
    return value


def _validate_bucket(value: str) -> str:
    if not 3 <= len(value) <= 63:
        raise ValueError("%s must be a valid S3 bucket name" % S3_BUCKET_ENV)
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", value):
        raise ValueError("%s must be a valid S3 bucket name" % S3_BUCKET_ENV)
    if ".." in value or ".-" in value or "-." in value:
        raise ValueError("%s must be a valid S3 bucket name" % S3_BUCKET_ENV)
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", value):
        raise ValueError("%s must not be an IP address" % S3_BUCKET_ENV)
    return value


def _validate_prefix(value: str) -> str:
    value = value.strip().strip("/")
    if not value:
        raise ValueError("%s must be non-empty" % S3_PREFIX_ENV)
    lowered = value.lower()
    if any(marker in lowered for marker in ("change-me", "changeme", "example", "your-")):
        raise ValueError("%s still contains a placeholder" % S3_PREFIX_ENV)
    if len(value) > 256 or "\\" in value:
        raise ValueError("%s is invalid" % S3_PREFIX_ENV)
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("%s is invalid" % S3_PREFIX_ENV)
    if any(
        ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        raise ValueError("%s contains control characters" % S3_PREFIX_ENV)
    return value


@dataclass(frozen=True)
class BraketHardwareConfig:
    """Validated, non-global AWS configuration for one hardware session."""

    profile: str = field(repr=False)
    region: str
    device_arn: str
    s3_bucket: str = field(repr=False)
    s3_prefix: str = DEFAULT_S3_PREFIX
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS
    job_timeout_seconds: float = DEFAULT_JOB_TIMEOUT_SECONDS

    @classmethod
    def from_env(
        cls, environment: Optional[Mapping[str, str]] = None
    ) -> "BraketHardwareConfig":
        env = os.environ if environment is None else environment
        profile = _required_text(PROFILE_ENV, env)
        region = _required_text(REGION_ENV, env)
        device_arn = _required_text(DEVICE_ARN_ENV, env)
        bucket = _required_text(S3_BUCKET_ENV, env)
        prefix = env.get(S3_PREFIX_ENV, DEFAULT_S3_PREFIX)
        poll = env.get(POLL_INTERVAL_ENV, str(DEFAULT_POLL_INTERVAL_SECONDS))
        timeout = env.get(JOB_TIMEOUT_ENV, str(DEFAULT_JOB_TIMEOUT_SECONDS))

        if not _PROFILE_RE.fullmatch(profile):
            raise ValueError("%s must name one explicit AWS profile" % PROFILE_ENV)
        if not _REGION_RE.fullmatch(region):
            raise ValueError("%s is not a valid AWS region" % REGION_ENV)
        arn_match = _DEVICE_ARN_RE.fullmatch(device_arn)
        if not arn_match:
            raise ValueError("%s must be an AWS Braket QPU ARN" % DEVICE_ARN_ENV)
        if arn_match.group(2) != region:
            raise ValueError("Braket device ARN region does not match %s" % REGION_ENV)
        poll_seconds = _positive_float(POLL_INTERVAL_ENV, poll)
        timeout_seconds = _positive_float(JOB_TIMEOUT_ENV, timeout)
        if poll_seconds > MAX_POLL_INTERVAL_SECONDS:
            raise ValueError("%s exceeds the safety limit" % POLL_INTERVAL_ENV)
        if timeout_seconds > MAX_JOB_TIMEOUT_SECONDS:
            raise ValueError("%s exceeds the safety limit" % JOB_TIMEOUT_ENV)
        if poll_seconds > timeout_seconds:
            raise ValueError("poll interval must not exceed the job timeout")
        return cls(
            profile=profile,
            region=region,
            device_arn=device_arn,
            s3_bucket=_validate_bucket(bucket),
            s3_prefix=_validate_prefix(prefix),
            poll_interval_seconds=poll_seconds,
            job_timeout_seconds=timeout_seconds,
        )


def _load_boto3():
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        raise BraketHardwareError(
            "AWS Braket hardware support requires the pinned boto3 dependency"
        ) from None
    return boto3, Config


class BraketHardwareClient(Protocol):
    def get_device(self) -> Mapping[str, Any]: ...

    def check_s3(self) -> Mapping[str, Any]: ...

    def submit(
        self, qasm3: str, shots: int, client_token: str, output_prefix: str
    ) -> str: ...

    def poll(self, task_arn: str) -> Mapping[str, Any]: ...

    def download_result(
        self, task: Mapping[str, Any], expected_prefix: str
    ) -> bytes: ...

    def close(self) -> None: ...


class Boto3BraketHardwareClient:
    """Small low-level wrapper with no implicit default credential chain."""

    def __init__(self, config: BraketHardwareConfig) -> None:
        self._config = config
        self._braket = None
        self._s3 = None
        try:
            if any(
                name.upper().startswith("AWS_ENDPOINT_URL") and str(value).strip()
                for name, value in os.environ.items()
            ):
                raise BraketHardwareError(
                    "custom AWS service endpoints are not allowed for hardware evidence"
                )
            boto3, Config = _load_boto3()
            session = boto3.Session(
                profile_name=config.profile,
                region_name=config.region,
            )
            client_config = Config(
                user_agent_extra="BraketSchemas/1.28.0",
                retries={"mode": "standard", "max_attempts": 4},
                ignore_configured_endpoint_urls=True,
            )
            self._braket = session.client(
                "braket", region_name=config.region, config=client_config
            )
            self._s3 = session.client(
                "s3", region_name=config.region, config=client_config
            )
        except BraketHardwareError:
            try:
                self.close()
            except Exception:
                pass
            raise
        except Exception:
            try:
                self.close()
            except Exception:
                pass
            raise BraketHardwareError(
                "AWS named profile or client initialization failed"
            ) from None

    def get_device(self) -> Mapping[str, Any]:
        try:
            return self._braket.get_device(deviceArn=self._config.device_arn)
        except Exception:
            raise BraketHardwareError("AWS Braket GetDevice failed") from None

    def check_s3(self) -> Mapping[str, Any]:
        try:
            location = self._s3.get_bucket_location(
                Bucket=self._config.s3_bucket,
            )
            listing = self._s3.list_objects_v2(
                Bucket=self._config.s3_bucket,
                Prefix=self._config.s3_prefix.rstrip("/") + "/",
                MaxKeys=1,
            )
            return {
                "bucket_location": location.get("LocationConstraint"),
                "prefix_key_count": listing.get("KeyCount"),
            }
        except Exception:
            raise BraketHardwareError("AWS S3 read-only prefix check failed") from None

    def submit(
        self, qasm3: str, shots: int, client_token: str, output_prefix: str
    ) -> str:
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
        try:
            response = self._braket.create_quantum_task(
                action=action,
                clientToken=client_token,
                deviceArn=self._config.device_arn,
                deviceParameters="{}",
                outputS3Bucket=self._config.s3_bucket,
                outputS3KeyPrefix=output_prefix,
                shots=shots,
            )
        except Exception:
            raise BraketHardwareError("AWS Braket CreateQuantumTask failed") from None
        task_arn = response.get("quantumTaskArn") if isinstance(response, Mapping) else None
        if not isinstance(task_arn, str):
            raise BraketHardwareError("AWS Braket returned no quantum task ARN")
        return task_arn

    def poll(self, task_arn: str) -> Mapping[str, Any]:
        try:
            return self._braket.get_quantum_task(quantumTaskArn=task_arn)
        except Exception:
            raise BraketHardwareError("AWS Braket GetQuantumTask failed") from None

    def download_result(
        self, task: Mapping[str, Any], expected_prefix: str
    ) -> bytes:
        bucket = task.get("outputS3Bucket")
        directory = task.get("outputS3Directory")
        if bucket != self._config.s3_bucket or not isinstance(directory, str):
            raise BraketHardwareError("AWS Braket returned an unexpected S3 result location")
        clean_directory = directory.strip("/")
        clean_prefix = expected_prefix.strip("/")
        if not clean_directory or not (
            clean_directory == clean_prefix
            or clean_directory.startswith(clean_prefix + "/")
        ):
            raise BraketHardwareError("AWS Braket returned an unexpected S3 result prefix")
        key = clean_directory + "/results.json"
        try:
            response = self._s3.get_object(Bucket=bucket, Key=key)
            length = response.get("ContentLength")
            if isinstance(length, int) and length > MAX_RESULT_BYTES:
                raise BraketHardwareError("AWS Braket result exceeds the size limit")
            body = response.get("Body")
            if body is None or not hasattr(body, "read"):
                raise BraketHardwareError("AWS S3 returned an invalid result body")
            try:
                payload = body.read(MAX_RESULT_BYTES + 1)
            finally:
                close = getattr(body, "close", None)
                if callable(close):
                    close()
        except BraketHardwareError:
            raise
        except Exception:
            raise BraketHardwareError("AWS Braket S3 result download failed") from None
        if not isinstance(payload, bytes) or len(payload) > MAX_RESULT_BYTES:
            raise BraketHardwareError("AWS Braket returned an invalid result payload")
        return payload

    def close(self) -> None:
        for client in (self._braket, self._s3):
            if client is None:
                continue
            close = getattr(client, "close", None)
            if callable(close):
                close()


def _redact_text(value: str, secrets: Sequence[str] = ()) -> str:
    text = str(value)
    for secret in sorted(
        (item for item in secrets if item), key=len, reverse=True
    ):
        text = text.replace(str(secret), "[REDACTED]")
    text = _ACCESS_KEY_RE.sub("[REDACTED_AWS_ACCESS_KEY]", text)
    text = _ARN_ACCOUNT_RE.sub(r"\1[REDACTED_ACCOUNT]", text)
    return _LABELED_ACCOUNT_RE.sub(r"\1[REDACTED_ACCOUNT]", text)


def sanitize_for_json(value: Any, secrets: Sequence[str] = ()) -> Any:
    """Recursively produce JSON-safe data while removing AWS identifiers."""

    if isinstance(value, Mapping):
        sanitized: Dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = _redact_text(str(raw_key), secrets)
            sanitized[key] = (
                "[REDACTED]"
                if _SENSITIVE_KEY_RE.search(key)
                else sanitize_for_json(raw_value, secrets)
            )
        return sanitized
    if isinstance(value, (list, tuple)):
        return [sanitize_for_json(item, secrets) for item in value]
    if isinstance(value, str):
        return _redact_text(value, secrets)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value), secrets)


@dataclass(frozen=True)
class DeviceCapabilities:
    name: str
    provider_name: str
    status: str
    device_type: str
    qubit_count: int
    supported_operations: Tuple[str, ...]
    min_shots: Optional[int]
    max_shots: Optional[int]
    requires_all_qubits_measurement: bool


def _required_operations(qasm3: str) -> Tuple[str, ...]:
    operations = set()
    for line in qasm3.splitlines():
        stripped = line.strip()
        if (
            not stripped
            or stripped.startswith("OPENQASM ")
            or stripped.startswith("qubit[")
            or stripped.startswith("bit[")
            or "measure" in stripped
        ):
            continue
        token = stripped.split(" ", 1)[0]
        operation = token.split("(", 1)[0]
        if operation:
            operations.add(operation)
    return tuple(sorted(operations))


def _parse_capabilities(
    response: Mapping[str, Any],
    config: BraketHardwareConfig,
    *,
    circuit: Optional[Circuit] = None,
    qasm3: Optional[str] = None,
    shots: Optional[int] = None,
    require_online: bool = False,
) -> DeviceCapabilities:
    if not isinstance(response, Mapping):
        raise BraketHardwareError("AWS Braket returned invalid device metadata")
    if response.get("deviceArn") != config.device_arn:
        raise BraketHardwareError("AWS Braket returned metadata for an unexpected device")
    device_type = str(response.get("deviceType", "")).upper()
    status = str(response.get("deviceStatus", "")).upper()
    if device_type != "QPU":
        raise BraketHardwareError("configured AWS Braket device is not a QPU")
    if require_online and status != "ONLINE":
        raise BraketHardwareError("configured AWS Braket QPU is not ONLINE")
    raw_capabilities = response.get("deviceCapabilities")
    try:
        capabilities = (
            json.loads(raw_capabilities)
            if isinstance(raw_capabilities, str)
            else raw_capabilities
        )
    except (TypeError, ValueError):
        raise BraketHardwareError("AWS Braket returned invalid device capabilities") from None
    if not isinstance(capabilities, Mapping):
        raise BraketHardwareError("AWS Braket returned invalid device capabilities")
    paradigm = capabilities.get("paradigm")
    action_map = capabilities.get("action")
    if not isinstance(paradigm, Mapping) or not isinstance(action_map, Mapping):
        raise BraketHardwareError("AWS Braket device capabilities are incomplete")
    qubit_count = paradigm.get("qubitCount")
    if not isinstance(qubit_count, int) or isinstance(qubit_count, bool):
        raise BraketHardwareError("AWS Braket device has no valid qubit count")
    action = action_map.get("braket.ir.openqasm.program")
    if not isinstance(action, Mapping):
        raise BraketHardwareError("AWS Braket QPU does not support OpenQASM programs")
    operations = action.get("supportedOperations")
    if not isinstance(operations, list) or not all(
        isinstance(item, str) for item in operations
    ):
        raise BraketHardwareError("AWS Braket QPU has invalid operation capabilities")
    normalized_operations = tuple(sorted({item.lower() for item in operations}))

    min_shots: Optional[int] = None
    max_shots: Optional[int] = None
    result_types = action.get("supportedResultTypes", [])
    if isinstance(result_types, list):
        sample = next(
            (
                item
                for item in result_types
                if isinstance(item, Mapping)
                and str(item.get("name", "")).lower() == "sample"
            ),
            None,
        )
        if sample is not None:
            raw_min, raw_max = sample.get("minShots"), sample.get("maxShots")
            min_shots = raw_min if isinstance(raw_min, int) else None
            max_shots = raw_max if isinstance(raw_max, int) else None
    requires_all = bool(action.get("requiresAllQubitsMeasurement", False))

    if circuit is not None:
        if circuit.qubit_count > qubit_count:
            raise BraketHardwareError("circuit exceeds the AWS Braket QPU qubit count")
        if requires_all:
            measured = {_global_qubit_index(circuit, item.qubit) for item in circuit.measurements}
            if measured != set(range(circuit.qubit_count)):
                raise BraketHardwareError("AWS Braket QPU requires all qubits to be measured")
    if qasm3 is not None:
        missing = set(_required_operations(qasm3)) - set(normalized_operations)
        if missing:
            raise BraketHardwareError(
                "AWS Braket QPU lacks required operations: %s"
                % ", ".join(sorted(missing))
            )
    if shots is not None:
        if min_shots is not None and shots < min_shots:
            raise BraketHardwareError("shots are below the AWS Braket QPU minimum")
        if max_shots is not None and shots > max_shots:
            raise BraketHardwareError("shots exceed the AWS Braket QPU maximum")
    return DeviceCapabilities(
        name=_redact_text(str(response.get("deviceName", "unknown"))),
        provider_name=_redact_text(str(response.get("providerName", "unknown"))),
        status=status or "UNKNOWN",
        device_type=device_type,
        qubit_count=qubit_count,
        supported_operations=normalized_operations,
        min_shots=min_shots,
        max_shots=max_shots,
        requires_all_qubits_measurement=requires_all,
    )


def check_braket_hardware(
    config: BraketHardwareConfig,
    client: Optional[BraketHardwareClient] = None,
) -> Dict[str, Any]:
    """Perform only GetDevice and an S3 list-prefix authorization check."""

    active = Boto3BraketHardwareClient(config) if client is None else client
    try:
        capabilities = _parse_capabilities(active.get_device(), config)
        s3_check = active.check_s3()
        if not isinstance(s3_check, Mapping):
            raise BraketHardwareError("AWS S3 returned an invalid bucket check")
        bucket_location = s3_check.get("bucket_location")
        if bucket_location in (None, ""):
            bucket_region = "us-east-1"
        elif bucket_location == "EU":
            bucket_region = "eu-west-1"
        elif isinstance(bucket_location, str):
            bucket_region = bucket_location
        else:
            raise BraketHardwareError("AWS S3 returned an invalid bucket region")
        if bucket_region != config.region:
            raise BraketHardwareError(
                "AWS S3 bucket region does not match the configured region"
            )
        return {
            "provider": "aws-braket",
            "credential_source": "named-profile",
            "region": config.region,
            "device_name": capabilities.name,
            "provider_name": capabilities.provider_name,
            "device_type": capabilities.device_type,
            "device_status": capabilities.status,
            "qubit_count": capabilities.qubit_count,
            "openqasm_supported": True,
            "s3_prefix_readable": True,
            "s3_bucket_region_matches": True,
            "qpu_online": capabilities.status == "ONLINE",
            "read_only_configuration_valid": True,
            "paid_submission_permission_verified": False,
        }
    finally:
        try:
            active.close()
        except Exception:
            pass


def _global_qubit_index(circuit: Circuit, bit: Any) -> int:
    offset = 0
    for name, size in circuit.qregs:
        if name == bit.register:
            return offset + bit.index
        offset += size
    raise BraketHardwareError("circuit contains an unknown qubit reference")


def _global_classical_index(circuit: Circuit, bit: Any) -> int:
    offset = 0
    for name, size in circuit.cregs:
        if name == bit.register:
            return offset + bit.index
        offset += size
    raise BraketHardwareError("circuit contains an unknown classical reference")


def _measurement_map(circuit: Circuit) -> Dict[int, int]:
    mapping: Dict[int, int] = {}
    classical_destinations = set()
    for measurement in circuit.measurements:
        qubit = _global_qubit_index(circuit, measurement.qubit)
        classical = _global_classical_index(circuit, measurement.classical)
        if qubit in mapping or classical in classical_destinations:
            raise BraketHardwareError(
                "Braket hardware evidence requires unique qubit measurements and classical destinations"
            )
        mapping[qubit] = classical
        classical_destinations.add(classical)
    if not mapping:
        raise BraketHardwareError("Braket hardware circuit has no measurements")
    return mapping


def _largest_remainder_counts(
    probabilities: Mapping[str, Any], shots: int
) -> Dict[str, int]:
    parsed: Dict[str, float] = {}
    for raw_key, raw_value in probabilities.items():
        key = str(raw_key).replace(" ", "")
        if not key or set(key) - {"0", "1"}:
            raise BraketHardwareError("AWS Braket returned an invalid probability key")
        if isinstance(raw_value, bool):
            raise BraketHardwareError("AWS Braket returned an invalid probability")
        try:
            probability = float(raw_value)
        except (TypeError, ValueError):
            raise BraketHardwareError("AWS Braket returned an invalid probability") from None
        if not math.isfinite(probability) or probability < 0:
            raise BraketHardwareError("AWS Braket returned an invalid probability")
        parsed[key] = parsed.get(key, 0.0) + probability
    total = sum(parsed.values())
    if not parsed or total <= 0 or abs(total - 1.0) > 1e-4:
        raise BraketHardwareError("AWS Braket probabilities do not sum to one")
    exact = {key: value * shots / total for key, value in parsed.items()}
    counts = {key: int(math.floor(value)) for key, value in exact.items()}
    remaining = shots - sum(counts.values())
    ranked = sorted(
        exact,
        key=lambda key: (-(exact[key] - counts[key]), key),
    )
    for key in ranked[:remaining]:
        counts[key] += 1
    return counts


def _map_raw_counts(
    raw_counts: Mapping[str, int],
    measured_qubits: Sequence[Any],
    circuit: Circuit,
) -> Dict[str, int]:
    if not measured_qubits or not all(
        isinstance(item, int) and not isinstance(item, bool) and item >= 0
        for item in measured_qubits
    ):
        raise BraketHardwareError("AWS Braket returned invalid measured qubits")
    if len(set(measured_qubits)) != len(measured_qubits):
        raise BraketHardwareError("AWS Braket returned duplicate measured qubits")
    measurement_map = _measurement_map(circuit)
    if set(measured_qubits) != set(measurement_map):
        raise BraketHardwareError("AWS Braket measured qubits do not match the circuit")
    normalized: Dict[str, int] = {}
    for raw_key, count in raw_counts.items():
        key = str(raw_key).replace(" ", "")
        if len(key) != len(measured_qubits) or set(key) - {"0", "1"}:
            raise BraketHardwareError("AWS Braket returned an invalid measurement key")
        classical = ["0"] * circuit.classical_count
        for bit, qubit in zip(key, measured_qubits):
            classical[measurement_map[qubit]] = bit
        little_key = "".join(reversed(classical))
        normalized[little_key] = normalized.get(little_key, 0) + count
    return normalized


def parse_braket_result(
    payload: Any,
    circuit: Circuit,
    shots: int,
    *,
    expected_task_arn: Optional[str] = None,
    expected_device_arn: Optional[str] = None,
) -> Tuple[Dict[str, int], Dict[str, Any]]:
    """Validate a raw GateModelTaskResult and normalize it to LoomQ order."""

    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError:
            raise BraketHardwareError("AWS Braket result is not UTF-8 JSON") from None
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            raise BraketHardwareError("AWS Braket result is invalid JSON") from None
    if not isinstance(payload, Mapping):
        raise BraketHardwareError("AWS Braket result must be a JSON object")
    header = payload.get("braketSchemaHeader")
    if not isinstance(header, Mapping) or header.get("name") != "braket.task_result.gate_model_task_result":
        raise BraketHardwareError("AWS Braket returned an unexpected result schema")
    measured_qubits = payload.get("measuredQubits")
    if not isinstance(measured_qubits, list):
        raise BraketHardwareError("AWS Braket result has no measured qubit order")
    task_metadata = payload.get("taskMetadata", {})
    if not isinstance(task_metadata, Mapping):
        raise BraketHardwareError("AWS Braket result has invalid task metadata")
    metadata_shots = task_metadata.get("shots")
    if metadata_shots is not None and metadata_shots != shots:
        raise BraketHardwareError("AWS Braket result shots do not match the request")
    if expected_task_arn is not None:
        if task_metadata.get("id") != expected_task_arn:
            raise BraketHardwareError(
                "AWS Braket result task identifier does not match the request"
            )
        if metadata_shots != shots:
            raise BraketHardwareError(
                "AWS Braket result must identify the requested shot count"
            )
    if expected_device_arn is not None and task_metadata.get("deviceId") != expected_device_arn:
        raise BraketHardwareError(
            "AWS Braket result device does not match the configured QPU"
        )
    successful = payload.get("numSuccessfulShots")
    failed = payload.get("numFailedShots")
    if successful is not None and successful != shots:
        raise BraketHardwareError("AWS Braket did not return every requested shot")
    if failed not in (None, 0):
        raise BraketHardwareError("AWS Braket reported failed shots")

    measurements = payload.get("measurements")
    if isinstance(measurements, list) and measurements:
        counts_source = "measurements"
        raw_counter: Counter[str] = Counter()
        for row in measurements:
            if not isinstance(row, list) or len(row) != len(measured_qubits):
                raise BraketHardwareError("AWS Braket returned an invalid measurement row")
            if any(type(bit) is not int or bit not in (0, 1) for bit in row):
                raise BraketHardwareError("AWS Braket returned an invalid measurement bit")
            raw_counter["".join(str(bit) for bit in row)] += 1
        if sum(raw_counter.values()) != shots:
            raise BraketHardwareError("AWS Braket measurement total does not match shots")
        raw_counts: Dict[str, int] = dict(raw_counter)
    else:
        counts_source = "derived_from_probabilities"
        probabilities = payload.get("measurementProbabilities")
        if not isinstance(probabilities, Mapping):
            raise BraketHardwareError("AWS Braket result contains no measurements")
        raw_counts = _largest_remainder_counts(probabilities, shots)
    counts = _map_raw_counts(raw_counts, measured_qubits, circuit)
    if sum(counts.values()) != shots:
        raise BraketHardwareError("AWS Braket normalized counts do not match shots")
    decoded = dict(payload)
    decoded["loomq_counts_source"] = counts_source
    return counts, decoded


def _task_id(
    task_arn: str, config: Optional[BraketHardwareConfig] = None
) -> str:
    match = _TASK_ARN_RE.fullmatch(task_arn)
    if not match:
        raise BraketHardwareError("AWS Braket returned an invalid quantum task ARN")
    if config is not None:
        task_parts = task_arn.split(":", 5)
        device_parts = config.device_arn.split(":", 5)
        if (
            task_parts[1] != device_parts[1]
            or task_parts[3] != config.region
        ):
            raise BraketHardwareError(
                "AWS Braket quantum task ARN does not match the configured region"
            )
    return match.group(1)


def _validated_client_token(value: Optional[str]) -> str:
    token = uuid.uuid4().hex if value is None else value
    if not isinstance(token, str) or not _CLIENT_TOKEN_RE.fullmatch(token):
        raise BraketHardwareError("AWS Braket clientToken is invalid")
    return token


def _validate_task_snapshot(
    snapshot: Mapping[str, Any],
    task_arn: str,
    config: BraketHardwareConfig,
    shots: int,
) -> None:
    if not isinstance(snapshot, Mapping):
        raise BraketHardwareError("AWS Braket returned invalid task metadata")
    if snapshot.get("quantumTaskArn") != task_arn:
        raise BraketHardwareError(
            "AWS Braket task metadata identifier does not match the request"
        )
    if snapshot.get("deviceArn") != config.device_arn:
        raise BraketHardwareError(
            "AWS Braket task metadata device does not match the configured QPU"
        )
    if snapshot.get("shots") != shots:
        raise BraketHardwareError(
            "AWS Braket task metadata shots do not match the request"
        )


def _downloaded_result_evidence(
    payload: Any, secrets: Sequence[str]
) -> Dict[str, Any]:
    """Retain a safe snapshot before semantic result validation can fail."""

    if isinstance(payload, bytes):
        encoded = payload
        snapshot: Dict[str, Any] = {
            "byte_length": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
        try:
            decoded = encoded.decode("utf-8")
        except UnicodeDecodeError:
            snapshot["utf8"] = False
            return snapshot
        snapshot["utf8"] = True
        try:
            parsed = json.loads(decoded)
        except (TypeError, ValueError):
            snapshot["json"] = False
            return snapshot
        snapshot["json"] = sanitize_for_json(parsed, secrets)
        return snapshot
    if isinstance(payload, str):
        encoded = payload.encode("utf-8")
        snapshot = {
            "byte_length": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "utf8": True,
        }
        try:
            parsed = json.loads(payload)
        except (TypeError, ValueError):
            snapshot["json"] = False
            return snapshot
        snapshot["json"] = sanitize_for_json(parsed, secrets)
        return snapshot
    serialized = json.dumps(
        sanitize_for_json(payload, secrets),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "byte_length": len(serialized),
        "sha256": hashlib.sha256(serialized).hexdigest(),
        "utf8": True,
        "json": sanitize_for_json(payload, secrets),
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class BraketHardwareRun:
    qasm3: str
    raw_record: Dict[str, Any]
    summary: Dict[str, Any]


def run_braket_hardware(
    circuit: Circuit,
    shots: int,
    config: BraketHardwareConfig,
    *,
    confirmation: Optional[str] = None,
    client: Optional[BraketHardwareClient] = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = _utc_now,
    on_submitted: Optional[Callable[[str], None]] = None,
    client_token: Optional[str] = None,
    resume_task_arn: Optional[str] = None,
) -> BraketHardwareRun:
    """Submit once or resume an existing task, then poll with bounded retries."""

    if resume_task_arn is None and confirmation != SUBMISSION_CONFIRMATION:
        raise BraketHardwareError(
            "AWS Braket QPU submission requires explicit confirmation"
        )
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    qasm3 = emit_braket_executable(circuit)
    token = _validated_client_token(client_token)
    task_arn = resume_task_arn
    task_id = _task_id(task_arn, config) if task_arn is not None else None
    # The idempotency token is also embedded in outputS3Directory.  Treat it
    # as private everywhere a task snapshot or downloaded payload is archived.
    secrets = (token, config.profile, config.s3_bucket, config.s3_prefix)
    started = monotonic()
    started_at = now()
    raw_record: Dict[str, Any] = {
        "schema_version": 1,
        "provider": "aws-braket",
        "region": config.region,
        "shots": shots,
        "qubits": circuit.qubit_count,
        "classical_bits": circuit.classical_count,
        "execution_started_at": _iso_utc(started_at),
        "execution_mode": "resume" if task_arn is not None else "submit",
        "client_token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        "qasm3_sha256": hashlib.sha256(qasm3.encode("utf-8")).hexdigest(),
    }
    if task_id is not None:
        raw_record["job_id"] = task_id
    last_snapshot: Optional[Mapping[str, Any]] = None
    active: Optional[BraketHardwareClient] = None
    output_prefix = "%s/tasks/%s" % (config.s3_prefix, token)
    consecutive_poll_errors = 0
    try:
        active = Boto3BraketHardwareClient(config) if client is None else client
        device = _parse_capabilities(
            active.get_device(),
            config,
            circuit=circuit,
            qasm3=qasm3,
            shots=shots,
            require_online=task_arn is None,
        )
        if task_arn is None:
            raw_record["submission_attempted"] = True
            task_arn = active.submit(qasm3, shots, token, output_prefix)
            task_id = _task_id(task_arn, config)
            raw_record["submitted_at"] = _iso_utc(now())
        raw_record.update(
            {
                "job_id": task_id,
                "device_name": device.name,
                "provider_name": device.provider_name,
            }
        )
        if on_submitted is not None:
            on_submitted(task_id)
        while True:
            try:
                last_snapshot = active.poll(task_arn)
                consecutive_poll_errors = 0
            except Exception:
                consecutive_poll_errors += 1
                raw_record["consecutive_poll_errors"] = consecutive_poll_errors
                elapsed = monotonic() - started
                if consecutive_poll_errors > MAX_CONSECUTIVE_POLL_ERRORS:
                    raise BraketHardwareError(
                        "AWS Braket polling failed after bounded retries"
                    ) from None
                if elapsed >= config.job_timeout_seconds:
                    raw_record.update(
                        {
                            "observed_at": _iso_utc(now()),
                            "terminal_state": "TIMEOUT",
                        }
                    )
                    raise BraketHardwareTimeout(
                        "AWS Braket task %s is still active after %.1f seconds; it was not cancelled"
                        % (task_id, config.job_timeout_seconds),
                        raw_record,
                    )
                sleep(
                    min(
                        config.poll_interval_seconds,
                        config.job_timeout_seconds - elapsed,
                    )
                )
                continue
            _validate_task_snapshot(last_snapshot, task_arn, config, shots)
            raw_state = last_snapshot.get("status") if isinstance(last_snapshot, Mapping) else None
            state = str(raw_state).upper() if isinstance(raw_state, str) else ""
            if state == "COMPLETED":
                payload = active.download_result(last_snapshot, output_prefix)
                raw_record["downloaded_result"] = _downloaded_result_evidence(
                    payload, secrets
                )
                counts, decoded_result = parse_braket_result(
                    payload,
                    circuit,
                    shots,
                    expected_task_arn=task_arn,
                    expected_device_arn=config.device_arn,
                )
                completed_at = now()
                raw_record.update(
                    {
                        "completed_at": _iso_utc(completed_at),
                        "terminal_state": state,
                        "task_metadata": sanitize_for_json(last_snapshot, secrets),
                    }
                )
                summary: Dict[str, Any] = {
                    "backend": "aws-braket-qpu-%s" % device.name,
                    "job_id": task_id,
                    "shots": shots,
                    "counts": counts,
                    "counts_source": decoded_result["loomq_counts_source"],
                    "bit_order": "little",
                    "timestamp": _iso_utc(completed_at),
                    "meta": {
                        "provider": "AWS Braket",
                        "device_name": device.name,
                        "provider_name": device.provider_name,
                        "device_type": device.device_type,
                        "region": config.region,
                        "qasm3_sha256": raw_record["qasm3_sha256"],
                    },
                }
                return BraketHardwareRun(qasm3, raw_record, summary)
            if state in _FAILED_STATES:
                raw_record.update(
                    {
                        "completed_at": _iso_utc(now()),
                        "terminal_state": state,
                        "task_metadata": sanitize_for_json(last_snapshot, secrets),
                    }
                )
                raise BraketHardwareJobFailed(
                    "AWS Braket task %s failed in state %s" % (task_id, state),
                    raw_record,
                )
            if state not in _PENDING_STATES:
                raw_record.update(
                    {
                        "observed_at": _iso_utc(now()),
                        "terminal_state": "UNKNOWN",
                        "task_metadata": sanitize_for_json(last_snapshot, secrets),
                    }
                )
                raise BraketHardwareJobFailed(
                    "AWS Braket task %s returned an unknown state" % task_id,
                    raw_record,
                )
            elapsed = monotonic() - started
            if elapsed >= config.job_timeout_seconds:
                raw_record.update(
                    {
                        "observed_at": _iso_utc(now()),
                        "terminal_state": "TIMEOUT",
                        "last_remote_state": state,
                        "task_metadata": sanitize_for_json(last_snapshot, secrets),
                    }
                )
                raise BraketHardwareTimeout(
                    "AWS Braket task %s is still active after %.1f seconds; it was not cancelled"
                    % (task_id, config.job_timeout_seconds),
                    raw_record,
                )
            sleep(
                min(
                    config.poll_interval_seconds,
                    config.job_timeout_seconds - elapsed,
                )
            )
    except (KeyboardInterrupt, SystemExit):
        if task_id is None:
            raise
        raw_record.update(
            {
                "observed_at": _iso_utc(now()),
                "terminal_state": "INTERRUPTED",
            }
        )
        raise BraketHardwareError(
            "AWS Braket wait was interrupted; the remote task was not cancelled",
            raw_record,
        ) from None
    except Exception as exc:
        if isinstance(exc, BraketHardwareError):
            if exc.raw_record is None and (
                task_id is not None or raw_record.get("submission_attempted") is True
            ):
                raw_record.update(
                    {
                        "observed_at": _iso_utc(now()),
                        "terminal_state": (
                            "CLIENT_ERROR"
                            if task_id is not None
                            else "SUBMISSION_UNCERTAIN"
                        ),
                    }
                )
                if last_snapshot is not None:
                    raw_record["task_metadata"] = sanitize_for_json(
                        last_snapshot, secrets
                    )
                raise exc.__class__(
                    _redact_text(str(exc), secrets), raw_record
                ) from None
            raise
        if task_id is None and raw_record.get("submission_attempted") is True:
            raw_record.update(
                {
                    "observed_at": _iso_utc(now()),
                    "terminal_state": "SUBMISSION_UNCERTAIN",
                }
            )
        raise BraketHardwareError(
            "AWS Braket hardware execution failed",
            raw_record
            if task_id is not None or raw_record.get("submission_attempted") is True
            else None,
        ) from None
    finally:
        if active is not None:
            try:
                active.close()
            except Exception:
                pass


def write_json(
    path: Path, payload: Mapping[str, Any], *, exclusive: bool = False
) -> None:
    """Write deterministic JSON; evidence callers use exclusive mode."""

    path.parent.mkdir(parents=True, exist_ok=True)
    created_exclusively = False
    try:
        with path.open(
            "x" if exclusive else "w", encoding="utf-8", newline="\n"
        ) as handle:
            created_exclusively = exclusive
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
    except Exception:
        if created_exclusively:
            path.unlink(missing_ok=True)
        raise
