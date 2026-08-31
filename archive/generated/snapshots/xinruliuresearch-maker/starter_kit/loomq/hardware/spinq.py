"""SpinQ Cloud real-QPU execution through the official QASM submitter."""

from dataclasses import dataclass
from contextlib import contextmanager
import importlib
from importlib import metadata as package_metadata
import os
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Optional

from .common import dry_run_plan, validate_http_url, validate_identifier, validate_qasm2, validate_shots
from .errors import (
    ConfigurationError,
    HardwareQualificationError,
    ResultValidationError,
    VendorExecutionError,
)
from .evidence import EvidenceBundle, make_hardware_result, normalize_counts, redact_payload, utc_timestamp


OFFICIAL_SUBMITTER_SHOTS = 1000


@dataclass(frozen=True)
class SpinQCredentials:
    username: str = ""
    private_key_path: Path = Path()
    host: str = ""

    def __repr__(self) -> str:
        return "SpinQCredentials(username='[REDACTED]', private_key_path='[REDACTED]', host='[REDACTED]')"


@dataclass(frozen=True)
class SpinQBindings:
    get_platforms: Callable[[], Any]
    qasm_submit: Callable[[str, str, str], Any]
    get_task_result_by_id: Callable[[str], Any]
    version: str


def load_credentials(environ: Optional[Mapping[str, str]] = None) -> SpinQCredentials:
    env = os.environ if environ is None else environ
    missing = [
        name
        for name in ("PRIVATEKEYPATH", "SPINQCLOUDUSERNAME", "SPINQCLOUDHOST")
        if not isinstance(env.get(name), str) or not env.get(name, "").strip()
    ]
    if missing:
        raise ConfigurationError("Missing required SpinQ environment variable(s): %s." % ", ".join(missing))
    key_path = Path(env["PRIVATEKEYPATH"].strip()).expanduser()
    try:
        resolved_key = key_path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ConfigurationError("PRIVATEKEYPATH does not identify a readable private-key file.") from None
    if not resolved_key.is_file():
        raise ConfigurationError("PRIVATEKEYPATH does not identify a regular file.")
    return SpinQCredentials(
        username=env["SPINQCLOUDUSERNAME"].strip(),
        private_key_path=resolved_key,
        host=validate_http_url(env["SPINQCLOUDHOST"], "SPINQCLOUDHOST"),
    )


def load_bindings() -> SpinQBindings:
    """Import the optional vendor module only on the real execution path."""

    try:
        module = importlib.import_module("spinqit_mcp_tools.qasm_submitter")
    except Exception:
        raise ConfigurationError(
            "SpinQ runtime is unavailable; install the verified spinqit_mcp_tools environment from the runbook."
        ) from None
    required = ("get_platforms", "qasm_submit", "get_task_result_by_id")
    if any(not callable(getattr(module, name, None)) for name in required):
        raise ConfigurationError("Installed SpinQ submitter does not expose the verified QASM tool surface.")
    try:
        version = package_metadata.version("spinqit_mcp_tools")
    except package_metadata.PackageNotFoundError:
        version = "unreported"
    return SpinQBindings(
        get_platforms=module.get_platforms,
        qasm_submit=module.qasm_submit,
        get_task_result_by_id=module.get_task_result_by_id,
        version=version,
    )


def _call(callable_: Callable[..., Any], phase: str, *args: Any) -> Any:
    try:
        return callable_(*args)
    except Exception:
        raise VendorExecutionError(
            "SpinQ vendor call failed during %s; credential values and the raw exception were not printed." % phase
        ) from None


def _select_qpu(platform_response: Any, platform_code: str) -> Mapping[str, Any]:
    if not isinstance(platform_response, Mapping):
        raise HardwareQualificationError("SpinQ platform discovery did not return the documented mapping.")
    items = platform_response.get("items")
    if not isinstance(items, list):
        raise HardwareQualificationError("SpinQ platform discovery did not return an items list.")
    matches = [item for item in items if isinstance(item, Mapping) and item.get("pcode") == platform_code]
    if len(matches) != 1:
        raise HardwareQualificationError("Selected SpinQ platform was not uniquely present in live discovery.")
    platform = matches[0]
    if platform.get("simu") is not False:
        raise HardwareQualificationError("Selected SpinQ platform is a simulator or lacks an explicit QPU flag.")
    online = platform.get("countOnlineMachine")
    if isinstance(online, bool) or not isinstance(online, int) or online < 1:
        raise HardwareQualificationError("Selected SpinQ QPU has no online machine in live discovery.")
    return platform


def _task_code(submission: Any) -> str:
    if not isinstance(submission, Mapping):
        raise ResultValidationError("SpinQ submission response must be a mapping.")
    if submission.get("status") not in (200, 202):
        raise VendorExecutionError("SpinQ did not accept the QPU task.")
    task = submission.get("task")
    code = task.get("tcode") if isinstance(task, Mapping) else None
    if not isinstance(code, str) or not code.strip():
        raise ResultValidationError("SpinQ accepted response did not include task.tcode.")
    return code.strip()


def _completed_counts(raw_result: Any, expected_shots: int) -> Mapping[str, int]:
    if not isinstance(raw_result, Mapping):
        raise ResultValidationError("SpinQ task result must be a mapping.")
    if raw_result.get("taskStatus") == "F":
        raise VendorExecutionError("SpinQ reported that the QPU task failed.")
    run = raw_result.get("run")
    if not isinstance(run, Mapping) or not isinstance(run.get("count"), Mapping):
        raise ResultValidationError("SpinQ completed response did not include run.count.")
    returned_shots = raw_result.get("shots")
    if returned_shots != expected_shots:
        raise ResultValidationError("SpinQ returned shots do not match the submitted value.")
    return normalize_counts(run["count"], expected_shots)


def _validate_request(qasm: str, shots: int, platform_code: str, task_name: str):
    source = validate_qasm2(qasm)
    validate_shots(shots)
    platform_code = validate_identifier(platform_code, "platform_code")
    task_name = validate_identifier(task_name, "task_name")
    if shots != OFFICIAL_SUBMITTER_SHOTS:
        raise ConfigurationError("SpinQ qasm_submitter 0.0.2 supports exactly 1000 shots.")
    lowered = source.lower()
    if "measure" in lowered:
        raise ConfigurationError("SpinQ qasm_submitter requires QASM without explicit measure statements.")
    if "//" in source or "/*" in source:
        raise ConfigurationError("SpinQ qasm_submitter requires QASM without comments.")
    if "\\" in source:
        raise ConfigurationError("SpinQ qasm_submitter rejects backslash-escaped QASM text.")
    return source, platform_code, task_name


def build_dry_run(qasm: str, shots: int, platform_code: str, task_name: str):
    source, platform_code, task_name = _validate_request(qasm, shots, platform_code, task_name)
    plan = dry_run_plan("spinq", platform_code, shots, source)
    plan.update(
        {
            "task_name": task_name,
            "required_environment": ["PRIVATEKEYPATH", "SPINQCLOUDUSERNAME", "SPINQCLOUDHOST"],
            "verified_vendor_surface": "spinqit_mcp_tools.qasm_submitter 0.0.2",
        }
    )
    return plan


@contextmanager
def _vendor_environment(credentials: SpinQCredentials):
    names = ("PRIVATEKEYPATH", "SPINQCLOUDUSERNAME", "SPINQCLOUDHOST")
    previous = {name: os.environ.get(name) for name in names}
    os.environ["PRIVATEKEYPATH"] = str(credentials.private_key_path)
    os.environ["SPINQCLOUDUSERNAME"] = credentials.username
    os.environ["SPINQCLOUDHOST"] = credentials.host
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _submit_and_wait(
    source: str,
    shots: int,
    platform_code: str,
    task_name: str,
    credentials: SpinQCredentials,
    vendor: SpinQBindings,
    timeout_seconds: float,
    poll_interval: float,
    sleep: Callable[[float], None],
    clock: Callable[[], float],
):
    with _vendor_environment(credentials):
        platform_response = _call(vendor.get_platforms, "platform discovery")
        platform = _select_qpu(platform_response, platform_code)
        submitted_at = utc_timestamp()
        submission_response = _call(vendor.qasm_submit, "QPU submission", source, task_name, platform_code)
        job_id = _task_code(submission_response)

        deadline = clock() + timeout_seconds
        raw_result: Any = None
        while clock() < deadline:
            candidate = _call(vendor.get_task_result_by_id, "result polling", job_id)
            if isinstance(candidate, Mapping) and candidate.get("taskStatus") == "F":
                raise VendorExecutionError("SpinQ reported that the QPU task failed.")
            if isinstance(candidate, Mapping) and isinstance(candidate.get("run"), Mapping):
                raw_result = candidate
                break
            sleep(min(poll_interval, max(0.0, deadline - clock())))
        if raw_result is None:
            raise VendorExecutionError("SpinQ QPU result polling timed out; no hardware evidence was written.")
    return platform, submitted_at, submission_response, job_id, raw_result


def execute(
    qasm: str,
    shots: int,
    platform_code: str,
    task_name: str,
    credentials: Optional[SpinQCredentials] = None,
    bindings: Optional[SpinQBindings] = None,
    timeout_seconds: float = 600.0,
    poll_interval: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> EvidenceBundle:
    """Submit and wait for one SpinQ real-QPU result.

    The official 0.0.2 QASM submitter hard-codes ``shots=1000``.  Other values
    are rejected instead of being silently changed.
    """

    source, platform_code, task_name = _validate_request(qasm, shots, platform_code, task_name)
    if timeout_seconds <= 0 or timeout_seconds > 86_400:
        raise ConfigurationError("timeout must be greater than zero and no more than 86400 seconds.")
    if poll_interval <= 0 or poll_interval > 60:
        raise ConfigurationError("poll interval must be greater than zero and no more than 60 seconds.")

    creds = credentials or load_credentials()
    vendor = bindings or load_bindings()
    # The official module reads these exact environment variables at call time.
    platform, submitted_at, submission_response, job_id, raw_result = _submit_and_wait(
        source,
        shots,
        platform_code,
        task_name,
        creds,
        vendor,
        timeout_seconds,
        poll_interval,
        sleep,
        clock,
    )

    counts = _completed_counts(raw_result, shots)
    completed_at = utc_timestamp()
    result = make_hardware_result(
        backend="spinq_cloud:%s" % platform_code,
        job_id=job_id,
        shots=shots,
        counts=counts,
        provider="spinq",
        timestamp=completed_at,
        meta={
            "platform_code": platform_code,
            "vendor_package": "spinqit_mcp_tools",
            "vendor_version": vendor.version,
            "bit_order_verified": False,
        },
    )
    metadata = {
        "execution_kind": "qpu",
        "qpu_verified": True,
        "provider": "spinq",
        "backend": result["backend"],
        "job_id": job_id,
        "shots": shots,
        "timestamp": completed_at,
        "submitted_at": submitted_at,
        "qualification": "live platform item had simu=false and countOnlineMachine>0",
        "platform_snapshot": redact_payload(platform),
        "vendor_package": "spinqit_mcp_tools",
        "vendor_version": vendor.version,
        "redaction_applied": True,
    }
    submission = {
        "provider": "spinq",
        "platform_code": platform_code,
        "shots": shots,
        "task_name": task_name,
        "submitted_at": submitted_at,
        "vendor_response": redact_payload(submission_response),
    }
    return EvidenceBundle(
        provider="spinq",
        input_qasm=source,
        submission=submission,
        raw_result=raw_result,
        normalized_result=result,
        metadata=metadata,
    )
