"""Safe, explicit SpinQ Cloud hardware execution support for LoomQ L1.

This module targets the API shipped by the pinned ``spinqit==0.2.4``:

* ``get_spinq_cloud(username, keyfile, host)``
* ``SpinQCloudConfig.configure_platform/configure_shots/``
  ``configure_measured_qubits/configure_task``
* ``SpinQCloudBackend.submit_task`` and
  ``SpinQCloudBackend.get_task_result(hanging=False)``

It intentionally is not registered as the normal ``target="spinq"`` runner.
Hardware submission is available only through ``run_spinq_hardware.py``.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import math
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Sequence, Tuple
from urllib.parse import urlsplit

from loomq_l1 import Circuit, emit_spinq, normalize_counts


ENV_USERNAME = "SPINQ_CLOUD_USERNAME"
ENV_KEY_FILE = "SPINQ_CLOUD_KEY_FILE"
ENV_HOST = "SPINQ_CLOUD_HOST"
ENV_PLATFORM = "SPINQ_CLOUD_PLATFORM"
DEFAULT_HOST = "http://cloud.spinq.cn:6060"
DEFAULT_PLATFORM = "triangulum_vp"
REQUIRED_ENVIRONMENT = (ENV_USERNAME, ENV_KEY_FILE)
OPTIONAL_ENVIRONMENT_DEFAULTS = {
    ENV_HOST: DEFAULT_HOST,
    ENV_PLATFORM: DEFAULT_PLATFORM,
}
SUBMISSION_CONFIRMATION = "SPINQ_HARDWARE"
RUNNABLE_SUBMISSION_STATUSES = frozenset({200, 202})
SENSITIVE_KEY = re.compile(
    r"(?:authorization|cookie|credential|key(?:file)?|password|private|secret|token|username)",
    re.IGNORECASE,
)


class SpinQHardwareError(RuntimeError):
    """Base class for safe-to-display SpinQ hardware errors."""


class SpinQHardwareConfigurationError(SpinQHardwareError):
    """Hardware configuration is absent or invalid."""


class SpinQHardwareSubmissionError(SpinQHardwareError):
    """The cloud did not accept a runnable task."""


class SpinQHardwareTaskError(SpinQHardwareError):
    """An accepted cloud task failed or timed out."""


class SpinQHardwareClientError(SpinQHardwareError):
    """The SDK could not complete a cloud operation."""


@dataclass(frozen=True)
class SpinQHardwareSettings:
    """Credentials and routing settings; secret fields are excluded from repr."""

    username: str
    key_file: str
    host: str
    platform: str

    def __repr__(self) -> str:
        return "SpinQHardwareSettings(username=<redacted>, key_file=<redacted>, host=<redacted>, platform=<configured>)"

    @classmethod
    def from_environment(
        cls, environ: Optional[Mapping[str, str]] = None
    ) -> "SpinQHardwareSettings":
        source = os.environ if environ is None else environ
        missing = [name for name in REQUIRED_ENVIRONMENT if not source.get(name, "").strip()]
        if missing:
            raise SpinQHardwareConfigurationError(
                "missing required environment variables: " + ", ".join(missing)
            )

        username = source[ENV_USERNAME].strip()
        key_file = source[ENV_KEY_FILE].strip()
        host = source.get(ENV_HOST, "").strip() or DEFAULT_HOST
        platform = source.get(ENV_PLATFORM, "").strip() or DEFAULT_PLATFORM

        if _has_control_characters(username):
            raise SpinQHardwareConfigurationError(
                "invalid value configured by " + ENV_USERNAME
            )
        if _has_control_characters(platform) or not re.fullmatch(
            r"[A-Za-z0-9._:-]+", platform
        ):
            raise SpinQHardwareConfigurationError(
                "invalid value configured by " + ENV_PLATFORM
            )

        try:
            parsed_host = urlsplit(host)
            valid_host = (
                parsed_host.scheme in {"http", "https"}
                and parsed_host.hostname is not None
                and parsed_host.username is None
                and parsed_host.password is None
                and not parsed_host.query
                and not parsed_host.fragment
            )
        except ValueError:
            valid_host = False
        if not valid_host:
            raise SpinQHardwareConfigurationError(
                "invalid service address configured by " + ENV_HOST
            )

        credential_path = Path(key_file).expanduser()
        if not credential_path.is_file() or not os.access(credential_path, os.R_OK):
            raise SpinQHardwareConfigurationError(
                "invalid credential file configured by " + ENV_KEY_FILE
            )
        return cls(username, str(credential_path), host, platform)


@dataclass(frozen=True)
class HardwareRequest:
    platform: str
    shots: int
    measured_qubits: Tuple[int, ...]
    task_name: str
    task_description: str


@dataclass(frozen=True)
class Submission:
    status: int
    job_id: Optional[str]


@dataclass(frozen=True)
class PollOutcome:
    state: str
    counts: Optional[Mapping[Any, Any]] = None
    raw_result: Optional[Mapping[str, Any]] = None

    @classmethod
    def pending(cls) -> "PollOutcome":
        return cls("pending")

    @classmethod
    def succeeded(
        cls, counts: Mapping[Any, Any], raw_result: Mapping[str, Any]
    ) -> "PollOutcome":
        return cls("succeeded", counts, raw_result)

    @classmethod
    def failed(cls) -> "PollOutcome":
        return cls("failed")


class SpinQCloudClient(Protocol):
    def compile_qasm(self, source: str) -> Any:
        ...

    def submit_task(self, ir: Any, request: HardwareRequest) -> Submission:
        ...

    def poll_task(self, job_id: str) -> PollOutcome:
        ...


def _has_control_characters(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _load_sdk():
    try:
        from spinqit import SpinQCloudConfig, get_compiler, get_spinq_cloud
        from spinqit.model.exceptions import TaskStatusError
    except ImportError:
        raise SpinQHardwareClientError(
            "SpinQ hardware execution requires the pinned spinqit dependency"
        ) from None
    return SpinQCloudConfig, get_compiler, get_spinq_cloud, TaskStatusError


class _DiscardText(io.TextIOBase):
    def write(self, text: str) -> int:
        return len(text)


class SpinQitCloudClient:
    """Small adapter around the verified SpinQit 0.2.4 cloud API."""

    def __init__(self, settings: SpinQHardwareSettings, sdk: Optional[Tuple[Any, ...]] = None):
        self._config_type, compiler_factory, cloud_factory, self._pending_error = (
            _load_sdk() if sdk is None else sdk
        )
        try:
            self._compiler = compiler_factory("qasm")
            if settings.host == DEFAULT_HOST:
                # SpinQit defines the service address as its third-argument
                # default.  Omitting it keeps the normal credential contract
                # to the documented username/private-key pair.
                self._backend = cloud_factory(settings.username, settings.key_file)
            else:
                self._backend = cloud_factory(
                    settings.username, settings.key_file, settings.host
                )
        except Exception:
            raise SpinQHardwareClientError(
                "SpinQ cloud client initialization failed; SDK details suppressed"
            ) from None

    def compile_qasm(self, source: str) -> Any:
        path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".qasm", delete=False, encoding="utf-8"
            ) as handle:
                handle.write(source)
                path = handle.name
            return self._compiler.compile(path, 0)
        except Exception:
            raise SpinQHardwareClientError(
                "SpinQ QASM compilation failed; SDK details suppressed"
            ) from None
        finally:
            if path is not None:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass

    def submit_task(self, ir: Any, request: HardwareRequest) -> Submission:
        config = self._config_type()
        config.configure_platform(request.platform)
        config.configure_shots(request.shots)
        config.configure_measured_qubits(list(request.measured_qubits))
        config.configure_task(request.task_name, request.task_description)
        try:
            status, _message, task_code = self._backend.submit_task(ir, config)
            numeric_status = int(status)
        except Exception:
            raise SpinQHardwareClientError(
                "SpinQ cloud task submission failed; SDK details suppressed"
            ) from None
        job_id = None if task_code is None else _validated_job_id(task_code)
        return Submission(numeric_status, job_id)

    def poll_task(self, job_id: str) -> PollOutcome:
        try:
            # SpinQit prints terminal failure details. Suppress SDK stdout so an
            # unexpected server echo can never enter evidence or CI logs.
            with contextlib.redirect_stdout(_DiscardText()):
                result = self._backend.get_task_result(job_id, hanging=False)
        except self._pending_error:
            return PollOutcome.pending()
        except Exception:
            raise SpinQHardwareClientError(
                "SpinQ cloud result query failed; SDK details suppressed"
            ) from None
        if result is None:
            return PollOutcome.failed()
        counts = getattr(result, "counts", None)
        if not isinstance(counts, Mapping):
            raise SpinQHardwareTaskError(
                "SpinQ hardware task returned invalid counts"
            )
        raw_result = {
            "task_code": job_id,
            "counts": dict(counts),
            "probabilities": getattr(result, "probabilities", None),
            "shots": getattr(result, "_shots", None),
        }
        return PollOutcome.succeeded(counts, raw_result)


def _validated_job_id(value: Any) -> str:
    job_id = str(value)
    if (
        not job_id
        or len(job_id) > 256
        or not re.fullmatch(r"[A-Za-z0-9._:-]+", job_id)
    ):
        raise SpinQHardwareClientError("SpinQ cloud returned an invalid job ID")
    return job_id


def _measured_qubits(circuit: Circuit) -> Tuple[int, ...]:
    offsets: Dict[str, int] = {}
    offset = 0
    for name, size in circuit.qregs:
        offsets[name] = offset
        offset += size
    return tuple(
        offsets[item.qubit.register] + item.qubit.index
        for item in circuit.measurements
    )


def _measurement_map(circuit: Circuit) -> Tuple[Dict[str, int], ...]:
    """Return the explicit source-QASM qubit-to-classical-bit mapping."""

    qoffsets: Dict[str, int] = {}
    coffsets: Dict[str, int] = {}
    offset = 0
    for name, size in circuit.qregs:
        qoffsets[name] = offset
        offset += size
    offset = 0
    for name, size in circuit.cregs:
        coffsets[name] = offset
        offset += size
    return tuple(
        {
            "qubit": qoffsets[item.qubit.register] + item.qubit.index,
            "classical": (
                coffsets[item.classical.register] + item.classical.index
            ),
        }
        for item in circuit.measurements
    )


def _qubit_key(value: Any, width: int) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 0:
            raise SpinQHardwareTaskError("SpinQ hardware returned an invalid qubit key")
        key = format(value, "b")
    elif isinstance(value, str):
        key = value.replace(" ", "")
        if key.startswith("0b"):
            key = key[2:]
    else:
        raise SpinQHardwareTaskError("SpinQ hardware returned an invalid qubit key")
    if not key or len(key) > width or set(key) - {"0", "1"}:
        raise SpinQHardwareTaskError("SpinQ hardware returned an invalid qubit key")
    return key.zfill(width)


def _largest_remainder_counts(
    probabilities: Mapping[Any, Any], shots: int, width: int
) -> Dict[str, int]:
    parsed: Dict[str, float] = {}
    for raw_key, raw_value in probabilities.items():
        key = _qubit_key(raw_key, width)
        if isinstance(raw_value, bool):
            raise SpinQHardwareTaskError("SpinQ hardware returned invalid probabilities")
        try:
            probability = float(raw_value)
        except (TypeError, ValueError):
            raise SpinQHardwareTaskError(
                "SpinQ hardware returned invalid probabilities"
            ) from None
        if not math.isfinite(probability) or probability < 0:
            raise SpinQHardwareTaskError("SpinQ hardware returned invalid probabilities")
        parsed[key] = parsed.get(key, 0.0) + probability

    total = sum(parsed.values())
    if not parsed or total <= 0 or not math.isclose(total, 1.0, abs_tol=1e-6):
        raise SpinQHardwareTaskError("SpinQ hardware probabilities do not sum to one")
    exact = [(key, probability * shots / total) for key, probability in parsed.items()]
    rounded = {key: int(math.floor(value)) for key, value in exact}
    missing = shots - sum(rounded.values())
    if missing < 0 or missing > len(exact):
        raise SpinQHardwareTaskError("SpinQ hardware probabilities cannot be normalized")
    order = sorted(
        exact,
        key=lambda item: (-(item[1] - math.floor(item[1])), item[0]),
    )
    for key, _value in order[:missing]:
        rounded[key] += 1
    return rounded


def _project_qubit_counts_to_classical(
    counts: Mapping[Any, Any], circuit: Circuit
) -> Dict[str, int]:
    qoffsets: Dict[str, int] = {}
    coffsets: Dict[str, int] = {}
    offset = 0
    for name, size in circuit.qregs:
        qoffsets[name] = offset
        offset += size
    offset = 0
    for name, size in circuit.cregs:
        coffsets[name] = offset
        offset += size

    projected: Dict[str, int] = {}
    for raw_key, raw_value in counts.items():
        key = _qubit_key(raw_key, circuit.qubit_count)
        if not isinstance(raw_value, int) or isinstance(raw_value, bool) or raw_value < 0:
            raise SpinQHardwareTaskError("SpinQ hardware returned invalid counts")
        classical = ["0"] * circuit.classical_count
        for measurement in circuit.measurements:
            qindex = qoffsets[measurement.qubit.register] + measurement.qubit.index
            cindex = (
                coffsets[measurement.classical.register] + measurement.classical.index
            )
            classical[cindex] = key[qindex]
        normalized_key = "".join(reversed(classical))
        projected[normalized_key] = projected.get(normalized_key, 0) + raw_value
    return projected


def _normalize_cloud_result(
    outcome: PollOutcome, circuit: Circuit, shots: int
) -> Tuple[Dict[str, int], str]:
    if outcome.counts is None or outcome.raw_result is None:
        raise SpinQHardwareTaskError("SpinQ hardware task returned an incomplete result")
    provider_shots = outcome.raw_result.get("shots")
    if (
        not isinstance(provider_shots, int)
        or isinstance(provider_shots, bool)
        or provider_shots <= 0
    ):
        raise SpinQHardwareTaskError(
            "SpinQ hardware result _shots is missing or invalid"
        )
    if provider_shots != shots:
        raise SpinQHardwareTaskError(
            "SpinQ hardware result _shots %d does not match requested shots %d"
            % (provider_shots, shots)
        )
    probabilities = outcome.raw_result.get("probabilities")
    if isinstance(probabilities, Mapping):
        qubit_counts: Mapping[Any, Any] = _largest_remainder_counts(
            probabilities, shots, circuit.qubit_count
        )
        source = "probabilities-largest-remainder"
    else:
        try:
            qubit_counts = normalize_counts(
                outcome.counts, shots, circuit.qubit_count
            )
        except (TypeError, ValueError):
            raise SpinQHardwareTaskError(
                "SpinQ hardware task returned invalid counts"
            ) from None
        source = "counts"
    projected = _project_qubit_counts_to_classical(qubit_counts, circuit)
    try:
        return normalize_counts(projected, shots, circuit.classical_count), source
    except (TypeError, ValueError):
        raise SpinQHardwareTaskError(
            "SpinQ hardware task returned invalid counts"
        ) from None


def emit_spinq_cloud(circuit: Circuit) -> str:
    """Reuse the SpinQ emitter while moving measurement into cloud config.

    SpinQit 0.2.4's cloud backend rejects explicit MEASURE instructions and
    performs the configured qubit measurement automatically at circuit end.
    """

    lines = [
        line
        for line in emit_spinq(circuit).splitlines()
        if not line.lstrip().lower().startswith("measure ")
    ]
    return "\n".join(lines) + "\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _standard_meta(
    circuit: Circuit,
    settings: SpinQHardwareSettings,
    normalization_source: str,
    source_qasm: str,
    submitted_qasm: str,
) -> Dict[str, Any]:
    return {
        "provider": "SpinQ Cloud",
        "device_code": settings.platform,
        "sdk_api": "spinqit-0.2.4",
        "result_kind": (
            "probabilities"
            if normalization_source == "probabilities-largest-remainder"
            else "counts"
        ),
        "counts_normalization": normalization_source,
        "measured_qubits": list(_measured_qubits(circuit)),
        "measurement_map": list(_measurement_map(circuit)),
        "source_qasm_sha256": _sha256_text(source_qasm),
        "submitted_qasm_sha256": _sha256_text(submitted_qasm),
        # Filled by the evidence writer once the job-derived filename exists.
        "raw_evidence_file": None,
    }


def _request_record(
    circuit: Circuit,
    settings: SpinQHardwareSettings,
    shots: int,
    source_qasm: str,
    submitted_qasm: str,
    *,
    provenance: str,
    task_name: Optional[str] = None,
    task_description: Optional[str] = None,
) -> Dict[str, Any]:
    request: Dict[str, Any] = {
        "schema_version": "loomq-spinq-hardware-request-v1",
        "provider": "SpinQ Cloud",
        "sdk_api": "spinqit-0.2.4",
        "provenance": provenance,
        "platform": settings.platform,
        "shots": shots,
        "measured_qubits": list(_measured_qubits(circuit)),
        "measurement_map": list(_measurement_map(circuit)),
        "source_qasm_sha256": _sha256_text(source_qasm),
        "submitted_qasm_sha256": _sha256_text(submitted_qasm),
    }
    if task_name is not None:
        request["task_name"] = task_name
    if task_description is not None:
        request["task_description"] = task_description
    return request


def _sanitize_json_value(value: Any, secret_values: Sequence[str]) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        sanitized = value
        for secret in secret_values:
            if secret:
                sanitized = sanitized.replace(secret, "<redacted>")
        return sanitized
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            result[key] = (
                "<redacted>"
                if SENSITIVE_KEY.search(key)
                else _sanitize_json_value(item, secret_values)
            )
        return result
    if isinstance(value, (list, tuple)):
        return [_sanitize_json_value(item, secret_values) for item in value]
    # Never serialize repr(value): SDK object reprs may contain request state.
    return "<unsupported:%s>" % type(value).__name__


def _poll_hardware_task(
    cloud: SpinQCloudClient,
    job_id: str,
    circuit: Circuit,
    shots: int,
    settings: SpinQHardwareSettings,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    event_handler: Optional[Callable[[str, Mapping[str, Any]], None]],
) -> Tuple[Dict[str, int], Any, int, str]:
    deadline = clock() + timeout_seconds
    poll_count = 0
    while True:
        poll_count += 1
        outcome = cloud.poll_task(job_id)
        if outcome.state == "failed":
            raise SpinQHardwareTaskError("SpinQ hardware task %s failed" % job_id)
        if outcome.state == "succeeded":
            counts, normalization_source = _normalize_cloud_result(
                outcome, circuit, shots
            )
            raw_result = _sanitize_json_value(
                outcome.raw_result,
                (settings.username, settings.key_file, settings.host),
            )
            return counts, raw_result, poll_count, normalization_source
        if outcome.state != "pending":
            raise SpinQHardwareTaskError(
                "SpinQ hardware task returned an unknown state"
            )
        if event_handler is not None:
            event_handler("pending", {"job_id": job_id, "poll": poll_count})
        remaining = deadline - clock()
        if remaining <= 0:
            raise SpinQHardwareTaskError(
                "SpinQ hardware task %s timed out" % job_id
            )
        sleep(min(poll_interval_seconds, remaining))


def execute_spinq_hardware(
    circuit: Circuit,
    shots: int,
    settings: SpinQHardwareSettings,
    *,
    confirmation: str,
    source_qasm: Optional[str] = None,
    client: Optional[SpinQCloudClient] = None,
    timeout_seconds: float = 1800.0,
    poll_interval_seconds: float = 5.0,
    task_name: str = "LoomQ L1 hardware validation",
    task_description: str = "LoomQ L1 Bell/GHZ validation",
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    event_handler: Optional[Callable[[str, Mapping[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Submit one confirmed hardware task and return a redacted evidence payload."""

    if confirmation != SUBMISSION_CONFIRMATION:
        raise SpinQHardwareSubmissionError(
            "SpinQ hardware submission requires explicit confirmation"
        )
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")

    archived_source = emit_spinq(circuit) if source_qasm is None else source_qasm
    submitted_source = emit_spinq_cloud(circuit)
    cloud = SpinQitCloudClient(settings) if client is None else client
    ir = cloud.compile_qasm(submitted_source)
    request = HardwareRequest(
        platform=settings.platform,
        shots=shots,
        measured_qubits=_measured_qubits(circuit),
        task_name=task_name,
        task_description=task_description,
    )
    submitted_at = _utc_now()
    submission = cloud.submit_task(ir, request)
    if submission.status not in RUNNABLE_SUBMISSION_STATUSES:
        suffix = (
            " (job ID %s)" % submission.job_id if submission.job_id is not None else ""
        )
        raise SpinQHardwareSubmissionError(
            "SpinQ cloud did not accept a runnable task: status %d%s"
            % (submission.status, suffix)
        )
    if submission.job_id is None:
        raise SpinQHardwareSubmissionError(
            "SpinQ cloud accepted a task without returning a job ID"
        )
    job_id = _validated_job_id(submission.job_id)
    if event_handler is not None:
        event_handler(
            "submitted", {"job_id": job_id, "status": submission.status}
        )

    counts, raw_result, poll_count, normalization_source = _poll_hardware_task(
        cloud,
        job_id,
        circuit,
        shots,
        settings,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        clock=clock,
        sleep=sleep,
        event_handler=event_handler,
    )
    completed_at = _utc_now()
    return {
        "schema_version": "loomq-spinq-hardware-v1",
        "sdk_api": "spinqit-0.2.4",
        "backend": "spinq-cloud-hardware",
        "device_code": settings.platform,
        "job_id": job_id,
        "shots": shots,
        "counts": counts,
        "counts_normalization": normalization_source,
        "bit_order": "little",
        "timestamp": submitted_at,
        "meta": _standard_meta(
            circuit,
            settings,
            normalization_source,
            archived_source,
            submitted_source,
        ),
        "submitted_at": submitted_at,
        "completed_at": completed_at,
        "qasm_sha256": _sha256_text(submitted_source),
        "request": _request_record(
            circuit,
            settings,
            shots,
            archived_source,
            submitted_source,
            provenance="client submission request",
            task_name=task_name,
            task_description=task_description,
        ),
        "submission_status": submission.status,
        "poll_count": poll_count,
        "raw_result": raw_result,
    }


def recover_spinq_hardware(
    circuit: Circuit,
    shots: int,
    settings: SpinQHardwareSettings,
    job_id: str,
    *,
    source_qasm: Optional[str] = None,
    client: Optional[SpinQCloudClient] = None,
    timeout_seconds: float = 1800.0,
    poll_interval_seconds: float = 5.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    event_handler: Optional[Callable[[str, Mapping[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Read and normalize an existing SpinQ task without submitting a new one."""

    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")
    validated_job_id = _validated_job_id(job_id)
    cloud = SpinQitCloudClient(settings) if client is None else client
    counts, raw_result, poll_count, normalization_source = _poll_hardware_task(
        cloud,
        validated_job_id,
        circuit,
        shots,
        settings,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        clock=clock,
        sleep=sleep,
        event_handler=event_handler,
    )
    archived_source = emit_spinq(circuit) if source_qasm is None else source_qasm
    submitted_source = emit_spinq_cloud(circuit)
    recovered_at = _utc_now()
    return {
        "schema_version": "loomq-spinq-hardware-v1",
        "sdk_api": "spinqit-0.2.4",
        "backend": "spinq-cloud-hardware",
        "device_code": settings.platform,
        "job_id": validated_job_id,
        "shots": shots,
        "counts": counts,
        "counts_normalization": normalization_source,
        "bit_order": "little",
        "timestamp": recovered_at,
        "meta": _standard_meta(
            circuit,
            settings,
            normalization_source,
            archived_source,
            submitted_source,
        ),
        "recovered_existing_job": True,
        "recovered_at": recovered_at,
        "qasm_sha256": _sha256_text(submitted_source),
        "request": _request_record(
            circuit,
            settings,
            shots,
            archived_source,
            submitted_source,
            provenance=(
                "read-only recovery arguments; original task name and "
                "description were not queried"
            ),
        ),
        "poll_count": poll_count,
        "raw_result": raw_result,
    }


def build_dry_run_manifest(
    circuit: Circuit, shots: int, circuit_name: str
) -> Dict[str, Any]:
    """Describe a future task without reading credentials or loading SpinQit."""

    source = emit_spinq_cloud(circuit)
    return {
        "mode": "dry-run",
        "will_submit": False,
        "sdk_api": "spinqit-0.2.4",
        "circuit": circuit_name,
        "shots": shots,
        "qubits": circuit.qubit_count,
        "classical_bits": circuit.classical_count,
        "measured_qubits": list(_measured_qubits(circuit)),
        "qasm_sha256": _sha256_text(source),
        "required_environment": list(REQUIRED_ENVIRONMENT),
        "optional_environment_defaults": dict(OPTIONAL_ENVIRONMENT_DEFAULTS),
        "required_confirmation": SUBMISSION_CONFIRMATION,
    }
