"""Explicit OriginQ real-hardware client for LoomQ L1 evidence runs.

This module deliberately stays outside ``adapter.run``: importing the starter kit
must never submit a paid cloud job.  The implementation targets the QCloud API
shipped by the repository's pinned ``pyqpanda3==0.4.0`` dependency.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, Mapping, MutableMapping, Optional, Protocol, Sequence, Tuple
from urllib.parse import urlsplit

from loomq_l1 import Circuit, emit_originq, normalize_counts


TOKEN_ENV = "LOOMQ_ORIGINQ_TOKEN"
CHIP_ID_ENV = "LOOMQ_ORIGINQ_CHIP_ID"
QCLOUD_URL_ENV = "LOOMQ_ORIGINQ_QCLOUD_URL"
POLL_INTERVAL_ENV = "LOOMQ_ORIGINQ_POLL_INTERVAL_SECONDS"
JOB_TIMEOUT_ENV = "LOOMQ_ORIGINQ_JOB_TIMEOUT_SECONDS"
IS_AMEND_ENV = "LOOMQ_ORIGINQ_IS_AMEND"
IS_MAPPING_ENV = "LOOMQ_ORIGINQ_IS_MAPPING"
IS_OPTIMIZATION_ENV = "LOOMQ_ORIGINQ_IS_OPTIMIZATION"
SUBMISSION_CONFIRMATION = "ORIGINQ_HARDWARE"
DEFAULT_QCLOUD_URL = "https://pyqanda-admin.qpanda.cn"
STATUS_QUERY_RETRY_LIMIT = 3

ENVIRONMENT_FIELDS = (
    TOKEN_ENV,
    CHIP_ID_ENV,
    QCLOUD_URL_ENV,
    POLL_INTERVAL_ENV,
    JOB_TIMEOUT_ENV,
    IS_AMEND_ENV,
    IS_MAPPING_ENV,
    IS_OPTIMIZATION_ENV,
)


class OriginQHardwareError(RuntimeError):
    """Base class for safe-to-display hardware client failures."""

    def __init__(self, message: str, raw_record: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.raw_record = raw_record


class OriginQHardwareTimeout(OriginQHardwareError):
    """The remote job did not reach a terminal state before the deadline."""


class OriginQHardwareJobFailed(OriginQHardwareError):
    """The remote service reported a terminal failure state."""


class OriginQHardwareStatusQueryError(OriginQHardwareError):
    """A potentially transient ``QCloudJob.status`` request failed."""


class OriginQHardwareResultQueryError(OriginQHardwareError):
    """A potentially transient ``QCloudJob.result`` request failed."""


def _parse_positive_float(name: str, value: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("%s must be a positive number" % name) from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError("%s must be a positive number" % name)
    return parsed


def _parse_bool(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("%s must be true or false" % name)


def _validate_qcloud_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "%s must be an HTTPS URL without credentials, query, or fragment"
            % QCLOUD_URL_ENV
        )
    return value.rstrip("/")


@dataclass(frozen=True)
class OriginQHardwareConfig:
    """Validated QCloud settings, with the token excluded from representations."""

    token: str = field(repr=False)
    chip_id: str
    qcloud_url: str = DEFAULT_QCLOUD_URL
    poll_interval_seconds: float = 5.0
    job_timeout_seconds: float = 1800.0
    is_amend: bool = True
    is_mapping: bool = True
    is_optimization: bool = True

    def __post_init__(self) -> None:
        token = self.token.strip()
        if not token or token.lower() in {
            "changeme",
            "fill-me",
            "your-token",
            "your_api_token",
        }:
            raise ValueError("%s is missing or still contains a placeholder" % TOKEN_ENV)
        object.__setattr__(self, "token", token)
        if isinstance(self.chip_id, bool):
            raise ValueError("%s must be a QCloud backend name" % CHIP_ID_ENV)
        backend_name = str(self.chip_id).strip()
        if (
            not backend_name
            or len(backend_name) > 128
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", backend_name)
        ):
            raise ValueError("%s must be a QCloud backend name" % CHIP_ID_ENV)
        object.__setattr__(self, "chip_id", backend_name)
        object.__setattr__(
            self, "qcloud_url", _validate_qcloud_url(self.qcloud_url)
        )
        for name, value in (
            (POLL_INTERVAL_ENV, self.poll_interval_seconds),
            (JOB_TIMEOUT_ENV, self.job_timeout_seconds),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("%s must be a positive number" % name)
            if not math.isfinite(float(value)) or value <= 0:
                raise ValueError("%s must be a positive number" % name)

    @classmethod
    def from_env(
        cls, environ: Optional[Mapping[str, str]] = None
    ) -> "OriginQHardwareConfig":
        values = os.environ if environ is None else environ
        token = values.get(TOKEN_ENV, "")
        chip_raw = values.get(CHIP_ID_ENV, "")
        missing = [
            name
            for name, value in ((TOKEN_ENV, token), (CHIP_ID_ENV, chip_raw))
            if not value.strip()
        ]
        if missing:
            raise ValueError(
                "missing required environment variables: " + ", ".join(missing)
            )
        url = values.get(QCLOUD_URL_ENV, "").strip() or DEFAULT_QCLOUD_URL
        return cls(
            token=token,
            chip_id=chip_raw,
            qcloud_url=url,
            poll_interval_seconds=_parse_positive_float(
                POLL_INTERVAL_ENV, values.get(POLL_INTERVAL_ENV, "5")
            ),
            job_timeout_seconds=_parse_positive_float(
                JOB_TIMEOUT_ENV, values.get(JOB_TIMEOUT_ENV, "1800")
            ),
            is_amend=_parse_bool(IS_AMEND_ENV, values.get(IS_AMEND_ENV, "true")),
            is_mapping=_parse_bool(
                IS_MAPPING_ENV, values.get(IS_MAPPING_ENV, "true")
            ),
            is_optimization=_parse_bool(
                IS_OPTIMIZATION_ENV,
                values.get(IS_OPTIMIZATION_ENV, "true"),
            ),
        )


def _load_sdk():
    try:
        from pyqpanda3.core import CPUQVM
        from pyqpanda3.intermediate_compiler import (
            convert_originir_string_to_qprog,
        )
        from pyqpanda3.qcloud import (
            JobStatus,
            QCloudJob,
            QCloudOptions,
            QCloudService,
        )
    except ImportError as exc:
        raise OriginQHardwareError(
            "OriginQ hardware execution requires the pinned pyqpanda3 dependency"
        ) from exc
    return SimpleNamespace(
        CPUQVM=CPUQVM,
        JobStatus=JobStatus,
        QCloudJob=QCloudJob,
        QCloudOptions=QCloudOptions,
        QCloudService=QCloudService,
        convert_originir_string_to_qprog=convert_originir_string_to_qprog,
    )


def run_pyqpanda3_cpuqvm(
    circuit: Circuit, shots: int, *, sdk: Optional[Any] = None
) -> Tuple[Mapping[Any, Any], str, str, Dict[str, Any]]:
    """Run the hardware preflight without importing legacy pyQPanda 2.x."""

    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    active_sdk = _load_sdk() if sdk is None else sdk
    origin_ir = emit_originq(circuit)
    try:
        program = active_sdk.convert_originir_string_to_qprog(origin_ir)
        qvm = active_sdk.CPUQVM()
        qvm.run(program, shots)
        counts = qvm.result().get_counts()
    except Exception:
        raise OriginQHardwareError(
            "pyqpanda3 CPUQVM preflight failed; SDK details suppressed"
        ) from None
    if not isinstance(counts, Mapping):
        raise OriginQHardwareError("pyqpanda3 CPUQVM returned invalid counts")
    return (
        counts,
        "originq-pyqpanda3-cpuqvm",
        "originq-local-" + uuid.uuid4().hex,
        {"qubits": circuit.qubit_count, "engine": "pyqpanda3 0.4.0 CPUQVM"},
    )


class OriginQHardwareClient(Protocol):
    """Small injectable boundary used by the offline state-machine tests."""

    def submit(self, origin_ir: str, shots: int, task_name: str) -> str:
        ...

    def attach(self, job_id: str) -> str:
        ...

    def poll(self, job_id: str) -> Any:
        ...

    def close(self) -> None:
        ...


class PyQPandaQCloudClient:
    """Adapter for the pyqpanda3 0.4.0 asynchronous QCloud API."""

    def __init__(
        self, config: OriginQHardwareConfig, sdk: Optional[Any] = None
    ) -> None:
        self.config = config
        self.sdk = _load_sdk() if sdk is None else sdk
        self.service: Optional[Any] = None
        self.backend: Optional[Any] = None
        self.options: Optional[Any] = None
        self.jobs: Dict[str, Any] = {}
        self._initialized = False

    def _initialize_service(self) -> None:
        if self.service is not None:
            return
        try:
            # Never inherit pyqpanda3 0.4.0's plaintext HTTP default.
            self.service = self.sdk.QCloudService(
                self.config.token, self.config.qcloud_url
            )
        except Exception as exc:
            raise OriginQHardwareError(
                "pyqpanda3 QCloud initialization failed: %s"
                % _redact_text(str(exc), (self.config.token,))
            ) from None

    def _initialize(self) -> None:
        if self._initialized:
            return
        self._initialize_service()
        try:
            assert self.service is not None
            self.backend = self.service.backend(self.config.chip_id)
            self.options = self.sdk.QCloudOptions()
            self.options.set_amend(self.config.is_amend)
            self.options.set_mapping(self.config.is_mapping)
            self.options.set_optimization(self.config.is_optimization)
            self._initialized = True
        except Exception as exc:
            raise OriginQHardwareError(
                "pyqpanda3 QCloud initialization failed: %s"
                % _redact_text(str(exc), (self.config.token,))
            ) from None

    def submit(self, origin_ir: str, shots: int, task_name: str) -> str:
        self._initialize()
        try:
            program = self.sdk.convert_originir_string_to_qprog(origin_ir)
            job = self.backend.run(program, shots, self.options)
            job_id = _validated_job_id(job.job_id())
        except Exception as exc:
            raise OriginQHardwareError(
                "pyqpanda3 QCloud submission failed: %s"
                % _redact_text(str(exc), (self.config.token,))
            ) from None
        self.jobs[job_id] = job
        return job_id

    def attach(self, job_id: str) -> str:
        """Attach to an existing job without calling ``QCloudBackend.run``."""

        validated = _validated_job_id(job_id)
        self._initialize_service()
        try:
            job = self.sdk.QCloudJob(validated)
        except Exception as exc:
            raise OriginQHardwareError(
                "pyqpanda3 QCloud job attachment failed: %s"
                % _redact_text(str(exc), (self.config.token,))
            ) from None
        self.jobs[validated] = job
        return validated

    def poll(self, job_id: str) -> Any:
        job = self.jobs.get(job_id)
        if job is None:
            raise OriginQHardwareError("QCloud job is not attached to this client")
        try:
            status = job.status()
        except Exception as exc:
            raise OriginQHardwareStatusQueryError(
                "pyqpanda3 QCloud status query failed: %s"
                % _redact_text(str(exc), (self.config.token,))
            ) from None
        response: Dict[str, Any] = {"status": status}
        if _coerce_state(status) != 3:
            return response
        try:
            result = job.result()
            try:
                distribution = result.get_probs()
                response["result_kind"] = "probabilities"
            except Exception:
                distribution = result.get_counts()
                response["result_kind"] = "counts"
            response["result"] = distribution
            response["origin_data"] = _parse_origin_data(result.origin_data())
            return response
        except Exception as exc:
            if isinstance(exc, OriginQHardwareError):
                raise
            raise OriginQHardwareResultQueryError(
                "pyqpanda3 QCloud result retrieval failed: %s"
                % _redact_text(str(exc), (self.config.token,))
            ) from None

    def close(self) -> None:
        # pyqpanda3 QCloudService/QCloudJob expose no finalize method. Drop all
        # references deterministically so a client cannot accidentally be reused.
        self.jobs.clear()
        self.options = None
        self.backend = None
        self.service = None
        self._initialized = False


_SENSITIVE_KEY = re.compile(
    r"(?:token|api[_-]?key|authorization|cookie|secret|password|credential|"
    r"account|user[_-]?(?:id|name)|email|phone)",
    re.IGNORECASE,
)


def _validated_job_id(value: Any) -> str:
    job_id = str(value).strip()
    if (
        not job_id
        or len(job_id) > 256
        or not re.fullmatch(r"[A-Za-z0-9._:-]+", job_id)
    ):
        raise OriginQHardwareError("QCloud returned an invalid job ID")
    return job_id
_AUTH_TEXT = re.compile(
    r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+|"
    r"((?:token|api[_-]?key|authorization|cookie|secret|password|"
    r"account(?:[_-]?id)?|user[_-]?id|email|phone)\s*[:=]\s*)"
    r"[^\s,;]+"
)


def _redact_text(value: str, secrets: Sequence[str] = ()) -> str:
    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")

    def replace(match: re.Match[str]) -> str:
        prefix = match.group(1) or match.group(2) or ""
        return prefix + "[REDACTED]"

    return _AUTH_TEXT.sub(replace, redacted)


def sanitize_for_json(value: Any, secrets: Sequence[str] = ()) -> Any:
    """Return a JSON-safe copy with credentials and account fields removed."""

    if isinstance(value, Mapping):
        safe: MutableMapping[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if _SENSITIVE_KEY.search(text_key):
                safe[text_key] = "[REDACTED]"
            else:
                safe[text_key] = sanitize_for_json(item, secrets)
        return dict(safe)
    if isinstance(value, (list, tuple)):
        return [sanitize_for_json(item, secrets) for item in value]
    if isinstance(value, str):
        return _redact_text(value, secrets)
    if value is None or isinstance(value, (bool, int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        return value
    enum_value = getattr(value, "value", None)
    if enum_value is not None and enum_value is not value:
        return sanitize_for_json(enum_value, secrets)
    return _redact_text(repr(value), secrets)


_STATE_NAMES = {
    1: "WAITING",
    2: "COMPUTING",
    3: "FINISHED",
    4: "FAILED",
    5: "QUEUING",
}
_STATE_FROM_NAME = {name: state for state, name in _STATE_NAMES.items()}
_PENDING_STATES = {1, 2, 5}
_FAILED_STATES = {4}


@dataclass(frozen=True)
class PollSnapshot:
    state: int
    result: Any
    error: str
    raw: Any

    @property
    def state_name(self) -> str:
        return _STATE_NAMES.get(self.state, "UNKNOWN")


def _coerce_state(value: Any) -> int:
    enum_value = getattr(value, "value", value)
    if isinstance(enum_value, str):
        token = enum_value.strip().upper()
        if token in _STATE_FROM_NAME:
            return _STATE_FROM_NAME[token]
        try:
            enum_value = float(token)
        except ValueError as exc:
            raise OriginQHardwareError("QCloud returned an unknown task state") from exc
    if isinstance(enum_value, bool) or not isinstance(enum_value, (int, float)):
        raise OriginQHardwareError("QCloud returned an invalid task state")
    if not float(enum_value).is_integer():
        raise OriginQHardwareError("QCloud returned an invalid task state")
    return int(enum_value)


def parse_poll_response(raw: Any) -> PollSnapshot:
    """Parse the documented QCloud ``[state, result, optional error]`` response."""

    state: Any
    result: Any = None
    error: Any = ""
    if isinstance(raw, Mapping):
        state = next(
            (raw[key] for key in ("state", "status", "task_status") if key in raw),
            None,
        )
        result = next(
            (raw[key] for key in ("result", "data", "measure_result") if key in raw),
            None,
        )
        error = next(
            (raw[key] for key in ("error", "error_msg", "message") if key in raw),
            "",
        )
        if state is None:
            raise OriginQHardwareError("QCloud status response has no task state")
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        if len(raw) < 2:
            raise OriginQHardwareError("QCloud status response is incomplete")
        state, result = raw[0], raw[1]
        if len(raw) > 3 and raw[3]:
            error = raw[3]
        elif len(raw) > 2:
            error = raw[2]
    else:
        raise OriginQHardwareError("QCloud returned an invalid status response")
    return PollSnapshot(_coerce_state(state), result, "" if error is None else str(error), raw)


def _decode_json(value: Any) -> Any:
    decoded = value
    for _ in range(3):
        if not isinstance(decoded, str):
            break
        try:
            decoded = json.loads(decoded)
        except json.JSONDecodeError:
            break
    return decoded


def _parse_origin_data(value: Any) -> Any:
    """Decode QCloudResult.origin_data so nested secrets can be redacted."""

    decoded = _decode_json(value)
    if isinstance(decoded, str) or not isinstance(
        decoded, (Mapping, list, tuple)
    ):
        raise OriginQHardwareError("QCloud returned invalid origin_data JSON")
    return decoded


def _looks_like_distribution(value: Mapping[Any, Any]) -> bool:
    if not value:
        return False
    for key, count in value.items():
        if isinstance(key, bool) or not isinstance(key, (str, int)):
            return False
        if isinstance(count, bool) or not isinstance(count, (int, float)):
            return False
    return True


def extract_distribution(result: Any) -> Mapping[Any, Any]:
    """Extract one measurement distribution without depending on private REST fields."""

    decoded = _decode_json(result)
    if isinstance(decoded, Mapping):
        if _looks_like_distribution(decoded):
            return decoded
        for key in (
            "counts",
            "probabilities",
            "measure_result",
            "measureResult",
            "result",
            "data",
        ):
            if key in decoded:
                try:
                    return extract_distribution(decoded[key])
                except OriginQHardwareError:
                    pass
    if (
        isinstance(decoded, Sequence)
        and not isinstance(decoded, (str, bytes, bytearray))
        and len(decoded) == 1
    ):
        return extract_distribution(decoded[0])
    raise OriginQHardwareError("QCloud finished without a measurement distribution")


def _largest_remainder_counts(
    distribution: Mapping[Any, Any], shots: int
) -> Dict[Any, int]:
    values = [(key, float(value)) for key, value in distribution.items()]
    if any(not math.isfinite(value) or value < 0 for _, value in values):
        raise OriginQHardwareError("QCloud returned invalid measurement values")
    total = sum(value for _, value in values)
    if total <= 0:
        raise OriginQHardwareError("QCloud returned an empty measurement distribution")
    if not math.isclose(total, 1.0, rel_tol=1e-6, abs_tol=1e-6) and not math.isclose(
        total, float(shots), rel_tol=1e-6, abs_tol=1e-6
    ):
        raise OriginQHardwareError(
            "QCloud measurement values sum to neither one nor the requested shots"
        )
    scale = float(shots) if math.isclose(total, 1.0, rel_tol=1e-6, abs_tol=1e-6) else 1.0
    exact = [(key, value * scale) for key, value in values]
    rounded = {key: int(math.floor(value)) for key, value in exact}
    missing = shots - sum(rounded.values())
    if missing < 0 or missing > len(exact):
        raise OriginQHardwareError("QCloud measurement values cannot be normalized")
    order = sorted(exact, key=lambda item: (-(item[1] - math.floor(item[1])), str(item[0])))
    for key, _value in order[:missing]:
        rounded[key] += 1
    return rounded


def normalize_hardware_distribution(
    distribution: Mapping[Any, Any], shots: int, width: int
) -> Dict[str, int]:
    """Normalize QCloud probabilities (or integral counts) to LoomQ counts."""

    if not isinstance(distribution, Mapping) or not distribution:
        raise OriginQHardwareError("QCloud returned an invalid measurement distribution")
    if all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in distribution.values()
    ) and sum(distribution.values()) == shots:
        count_map: Mapping[Any, Any] = distribution
    else:
        count_map = _largest_remainder_counts(distribution, shots)
    try:
        return normalize_counts(count_map, shots, width)
    except ValueError as exc:
        raise OriginQHardwareError("invalid QCloud measurement result: %s" % exc) from None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _base_raw_record(
    circuit: Circuit,
    shots: int,
    config: OriginQHardwareConfig,
    origin_ir: str,
    task_name: str,
    submitted_at: datetime,
) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "provider": "originq",
        "sdk": "pyqpanda3 0.4.0 QCloud",
        "device_id": str(config.chip_id),
        "shots": shots,
        "qubits": circuit.qubit_count,
        "classical_bits": circuit.classical_count,
        "task_name": _redact_text(task_name, (config.token,)),
        "submitted_at": _iso_utc(submitted_at),
        "origin_ir_sha256": hashlib.sha256(origin_ir.encode("utf-8")).hexdigest(),
    }


@dataclass(frozen=True)
class OriginQHardwareRun:
    origin_ir: str
    raw_record: Dict[str, Any]
    summary: Dict[str, Any]


def run_originq_hardware(
    circuit: Circuit,
    shots: int,
    config: OriginQHardwareConfig,
    *,
    confirmation: Optional[str],
    task_name: str = "LoomQ L1 hardware",
    client: Optional[OriginQHardwareClient] = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = _utc_now,
    on_submitted: Optional[Callable[[str], None]] = None,
    _resume_job_id: Optional[str] = None,
) -> OriginQHardwareRun:
    """Submit and poll one explicitly requested OriginQ hardware execution.

    ``_resume_job_id`` is reserved for :func:`resume_originq_hardware`; normal
    callers must pass the exact paid-submission confirmation.
    """

    is_resume = _resume_job_id is not None
    if not is_resume and confirmation != SUBMISSION_CONFIRMATION:
        raise OriginQHardwareError(
            "OriginQ hardware submission requires explicit confirmation"
        )
    if is_resume and confirmation is not None:
        raise OriginQHardwareError(
            "OriginQ job recovery must not include submission confirmation"
        )
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    if (
        not isinstance(task_name, str)
        or not task_name.strip()
        or len(task_name.strip()) > 128
        or any(ord(character) < 32 or ord(character) == 127 for character in task_name)
    ):
        raise ValueError("task_name must be non-empty text")
    task_name = task_name.strip()
    origin_ir = emit_originq(circuit)
    active_client = PyQPandaQCloudClient(config) if client is None else client
    assert active_client is not None
    started = monotonic()
    submitted_at = now()
    raw_record = _base_raw_record(
        circuit, shots, config, origin_ir, task_name, submitted_at
    )
    if is_resume:
        raw_record.pop("submitted_at")
        raw_record["resumed_at"] = _iso_utc(submitted_at)
        raw_record["resume_only"] = True
    job_id: Optional[str] = None
    last_raw_response: Any = None
    primary_error: Optional[BaseException] = None
    consecutive_query_failures = 0
    status_query_retries = 0
    result_query_retries = 0
    try:
        if is_resume:
            job_id = _validated_job_id(_resume_job_id)
            raw_record["job_id"] = job_id
            attached_job_id = _validated_job_id(active_client.attach(job_id))
            if attached_job_id != job_id:
                raise OriginQHardwareError(
                    "QCloud attached a different job than requested"
                )
        else:
            job_id = active_client.submit(origin_ir, shots, task_name)
            job_id = _validated_job_id(job_id)
            raw_record["job_id"] = job_id
        if on_submitted is not None:
            on_submitted(job_id)
        while True:
            try:
                last_raw_response = active_client.poll(job_id)
            except (
                OriginQHardwareStatusQueryError,
                OriginQHardwareResultQueryError,
            ) as query_exc:
                consecutive_query_failures += 1
                elapsed = monotonic() - started
                if elapsed >= config.job_timeout_seconds:
                    query_state = (
                        "STATUS_QUERY_FAILED"
                        if isinstance(query_exc, OriginQHardwareStatusQueryError)
                        else "RESULT_QUERY_FAILED"
                    )
                    raw_record.update(
                        {
                            "observed_at": _iso_utc(now()),
                            "terminal_state": "TIMEOUT",
                            "last_remote_state": query_state,
                        }
                    )
                    raise OriginQHardwareTimeout(
                        "OriginQ job %s timed out after %.1f seconds"
                        % (job_id, config.job_timeout_seconds),
                        raw_record,
                    ) from None
                if consecutive_query_failures > STATUS_QUERY_RETRY_LIMIT:
                    raise
                if isinstance(query_exc, OriginQHardwareStatusQueryError):
                    status_query_retries += 1
                    raw_record["status_query_retries"] = status_query_retries
                else:
                    result_query_retries += 1
                    raw_record["result_query_retries"] = result_query_retries
                sleep(
                    min(
                        config.poll_interval_seconds,
                        config.job_timeout_seconds - elapsed,
                    )
                )
                continue
            consecutive_query_failures = 0
            snapshot = parse_poll_response(last_raw_response)
            if snapshot.state == 3:
                distribution = extract_distribution(snapshot.result)
                counts = normalize_hardware_distribution(
                    distribution, shots, circuit.classical_count
                )
                completed_at = now()
                raw_record.update(
                    {
                        "completed_at": _iso_utc(completed_at),
                        "terminal_state": snapshot.state_name,
                        "sdk_response": sanitize_for_json(
                            snapshot.raw, (config.token,)
                        ),
                    }
                )
                summary: Dict[str, Any] = {
                    "backend": "originq-qcloud-%s" % config.chip_id,
                    "job_id": job_id,
                    "shots": shots,
                    "counts": counts,
                    "bit_order": "little",
                    "timestamp": _iso_utc(completed_at),
                    "meta": {
                        "provider": "Origin Quantum",
                        "device_id": str(config.chip_id),
                        "engine": "pyqpanda3 0.4.0 QCloud",
                        "task_name": _redact_text(task_name, (config.token,)),
                        "origin_ir_sha256": raw_record["origin_ir_sha256"],
                    },
                }
                if is_resume:
                    summary["meta"]["resumed"] = True
                return OriginQHardwareRun(origin_ir, raw_record, summary)
            if snapshot.state in _FAILED_STATES:
                raw_record.update(
                    {
                        "completed_at": _iso_utc(now()),
                        "terminal_state": snapshot.state_name,
                        "sdk_response": sanitize_for_json(
                            snapshot.raw, (config.token,)
                        ),
                    }
                )
                detail = _redact_text(snapshot.error, (config.token,)).strip()
                raise OriginQHardwareJobFailed(
                    "OriginQ job %s failed in state %s%s"
                    % (job_id, snapshot.state_name, ": " + detail if detail else ""),
                    raw_record,
                )
            if snapshot.state not in _PENDING_STATES:
                raw_record.update(
                    {
                        "completed_at": _iso_utc(now()),
                        "terminal_state": "UNKNOWN",
                        "sdk_response": sanitize_for_json(
                            snapshot.raw, (config.token,)
                        ),
                    }
                )
                raise OriginQHardwareJobFailed(
                    "OriginQ job %s returned unknown state %s"
                    % (job_id, snapshot.state),
                    raw_record,
                )
            elapsed = monotonic() - started
            if elapsed >= config.job_timeout_seconds:
                raw_record.update(
                    {
                        "observed_at": _iso_utc(now()),
                        "terminal_state": "TIMEOUT",
                        "last_remote_state": snapshot.state_name,
                        "sdk_response": sanitize_for_json(
                            snapshot.raw, (config.token,)
                        ),
                    }
                )
                raise OriginQHardwareTimeout(
                    "OriginQ job %s timed out after %.1f seconds"
                    % (job_id, config.job_timeout_seconds),
                    raw_record,
                )
            sleep(
                min(
                    config.poll_interval_seconds,
                    config.job_timeout_seconds - elapsed,
                )
            )
    except (KeyboardInterrupt, SystemExit) as exc:
        primary_error = exc
        raise
    except Exception as exc:
        primary_error = exc
        if isinstance(exc, OriginQHardwareError):
            if exc.raw_record is None and job_id:
                raw_record.update(
                    {
                        "observed_at": _iso_utc(now()),
                        "terminal_state": "CLIENT_ERROR",
                    }
                )
                if last_raw_response is not None:
                    raw_record["sdk_response"] = sanitize_for_json(
                        last_raw_response, (config.token,)
                    )
                raise exc.__class__(str(exc), raw_record) from None
            raise
        safe_message = _redact_text(str(exc), (config.token,))
        raise OriginQHardwareError(
            "OriginQ hardware execution failed: %s" % safe_message,
            raw_record if job_id else None,
        ) from None
    finally:
        try:
            active_client.close()
        except Exception as close_exc:
            if primary_error is None:
                raise OriginQHardwareError(
                    "OriginQ QCloud cleanup failed: %s"
                    % _redact_text(str(close_exc), (config.token,))
                ) from None


def resume_originq_hardware(
    circuit: Circuit,
    shots: int,
    config: OriginQHardwareConfig,
    *,
    job_id: str,
    task_name: str = "LoomQ L1 hardware recovery",
    client: Optional[OriginQHardwareClient] = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = _utc_now,
    on_attached: Optional[Callable[[str], None]] = None,
) -> OriginQHardwareRun:
    """Attach to and poll an existing OriginQ job without submitting a task."""

    return run_originq_hardware(
        circuit,
        shots,
        config,
        confirmation=None,
        task_name=task_name,
        client=client,
        monotonic=monotonic,
        sleep=sleep,
        now=now,
        on_submitted=on_attached,
        _resume_job_id=job_id,
    )


def write_json(
    path: Path, payload: Mapping[str, Any], *, exclusive: bool = False
) -> None:
    """Write deterministic UTF-8 JSON; callers choose the evidence path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    handle = None
    try:
        handle = path.open(mode, encoding="utf-8", newline="\n")
        with handle:
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
        # An exclusive evidence write owns the path only after open("x")
        # succeeds. Remove that partial file, but never delete a pre-existing
        # path when open("x") itself raises FileExistsError.
        if exclusive and handle is not None:
            path.unlink(missing_ok=True)
        raise
