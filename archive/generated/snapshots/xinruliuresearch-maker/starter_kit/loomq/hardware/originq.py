"""OriginQ real-QPU execution through verified pyqpanda3 0.4.0 APIs."""

from dataclasses import dataclass
import importlib
from importlib import metadata as package_metadata
import json
import os
from typing import Any, Callable, Mapping, Optional

from .common import dry_run_plan, validate_http_url, validate_identifier, validate_qasm2, validate_shots
from .errors import ConfigurationError, HardwareQualificationError, ResultValidationError, VendorExecutionError
from .evidence import EvidenceBundle, make_hardware_result, redact_payload, utc_timestamp


@dataclass(frozen=True)
class OriginQCredentials:
    api_key: str = ""
    backend_name: str = ""
    service_url: Optional[str] = None

    def __repr__(self) -> str:
        return "OriginQCredentials(api_key='[REDACTED]', backend_name=%r, service_url='[REDACTED]')" % (
            self.backend_name,
        )


@dataclass(frozen=True)
class OriginQBindings:
    service_class: Callable[..., Any]
    convert_qasm_string_to_qprog: Callable[[str], Any]
    database_binary: Any
    version: str


def load_credentials(
    backend_override: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> OriginQCredentials:
    env = os.environ if environ is None else environ
    api_key = env.get("QPANDA_QCLOUD_API_KEY", "")
    backend_name = backend_override or env.get("QPANDA_QCLOUD_BACKEND", "")
    missing = []
    if not isinstance(api_key, str) or not api_key.strip():
        missing.append("QPANDA_QCLOUD_API_KEY")
    if not isinstance(backend_name, str) or not backend_name.strip():
        missing.append("QPANDA_QCLOUD_BACKEND/--backend")
    if missing:
        raise ConfigurationError("Missing required OriginQ setting(s): %s." % ", ".join(missing))
    raw_url = env.get("QPANDA_QCLOUD_URL", "")
    service_url = validate_http_url(raw_url, "QPANDA_QCLOUD_URL") if raw_url else None
    return OriginQCredentials(
        api_key=api_key.strip(),
        backend_name=validate_identifier(backend_name, "backend"),
        service_url=service_url,
    )


def load_bindings() -> OriginQBindings:
    """Import pyqpanda3 only when a real execution is requested."""

    try:
        qcloud = importlib.import_module("pyqpanda3.qcloud")
        compiler = importlib.import_module("pyqpanda3.intermediate_compiler")
    except Exception:
        raise ConfigurationError("OriginQ runtime is unavailable; install pyqpanda3==0.4.0 in an isolated environment.") from None
    service_class = getattr(qcloud, "QCloudService", None)
    database = getattr(qcloud, "DataBase", None)
    converter = getattr(compiler, "convert_qasm_string_to_qprog", None)
    if not callable(service_class) or database is None or not hasattr(database, "Binary") or not callable(converter):
        raise ConfigurationError("Installed pyqpanda3 does not expose the verified 0.4.0 QCloud/QASM surface.")
    try:
        version = package_metadata.version("pyqpanda3")
    except package_metadata.PackageNotFoundError:
        version = "unreported"
    if version != "0.4.0":
        raise ConfigurationError("OriginQ runner is verified only for pyqpanda3==0.4.0.")
    return OriginQBindings(service_class, converter, database.Binary, version)


def _call(callable_: Callable[..., Any], phase: str, *args: Any, **kwargs: Any) -> Any:
    try:
        return callable_(*args, **kwargs)
    except Exception:
        raise VendorExecutionError(
            "OriginQ vendor call failed during %s; credential values and the raw exception were not printed." % phase
        ) from None


def _origin_data(result: Any) -> Any:
    raw_text = _call(result.origin_data, "raw result retrieval")
    if not isinstance(raw_text, str):
        return {"origin_data": str(raw_text)}
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {"origin_data": raw_text}


def build_dry_run(qasm: str, shots: int, backend_name: str):
    source = validate_qasm2(qasm)
    validate_shots(shots)
    backend_name = validate_identifier(backend_name, "backend")
    plan = dry_run_plan("originq", backend_name, shots, source)
    plan.update(
        {
            "required_environment": ["QPANDA_QCLOUD_API_KEY"],
            "optional_environment": ["QPANDA_QCLOUD_URL"],
            "verified_vendor_surface": "pyqpanda3 0.4.0 QCloudService/QCloudBackend",
            "qpu_qualification": "QCloudBackend.chip_info() must succeed",
        }
    )
    return plan


def execute(
    qasm: str,
    shots: int,
    credentials: Optional[OriginQCredentials] = None,
    bindings: Optional[OriginQBindings] = None,
) -> EvidenceBundle:
    source = validate_qasm2(qasm)
    validate_shots(shots)
    creds = credentials or load_credentials()
    vendor = bindings or load_bindings()

    prog = _call(vendor.convert_qasm_string_to_qprog, "QASM conversion", source)
    if creds.service_url:
        service = _call(vendor.service_class, "service initialization", creds.api_key, creds.service_url)
    else:
        service = _call(vendor.service_class, "service initialization", creds.api_key)

    available = _call(service.backends, "backend discovery")
    if not isinstance(available, Mapping) or available.get(creds.backend_name) is not True:
        raise HardwareQualificationError("Selected OriginQ backend is absent or unavailable in live discovery.")
    backend = _call(service.backend, "backend selection", creds.backend_name)

    # Official 0.4.0 docs specify that chip_info() is QPU-only and raises on
    # full/partial/single-amplitude simulators.  It is our fail-closed proof.
    chip_info = _call(backend.chip_info, "QPU qualification")
    chip_id = _call(chip_info.chip_id, "chip identity retrieval")
    qubit_count = _call(chip_info.qubits_num, "chip capacity retrieval")
    if not isinstance(chip_id, str) or not chip_id.strip():
        raise HardwareQualificationError("OriginQ chip_info did not provide a non-empty chip ID.")
    if isinstance(qubit_count, bool) or not isinstance(qubit_count, int) or qubit_count < 1:
        raise HardwareQualificationError("OriginQ chip_info did not provide a valid QPU capacity.")

    submitted_at = utc_timestamp()
    job = _call(backend.run, "QPU submission", prog, shots)
    job_id = _call(job.job_id, "job identity retrieval")
    if not isinstance(job_id, str) or not job_id.strip():
        raise ResultValidationError("OriginQ QCloudJob did not provide a vendor job ID.")
    job_id = job_id.strip()
    result_obj = _call(job.result, "QPU result retrieval")
    result_job_id = _call(result_obj.job_id, "result job identity retrieval")
    if result_job_id != job_id:
        raise ResultValidationError("OriginQ job and result IDs do not match.")
    counts = _call(result_obj.get_counts, "binary count retrieval", base=vendor.database_binary)
    raw_result = _origin_data(result_obj)
    status = str(_call(result_obj.job_status, "job status retrieval"))
    error_message = _call(result_obj.error_message, "job error retrieval")
    if isinstance(error_message, str) and error_message.strip():
        raise VendorExecutionError("OriginQ returned a non-empty QPU job error; no hardware evidence was written.")

    completed_at = utc_timestamp()
    normalized = make_hardware_result(
        backend="originq:%s" % creds.backend_name,
        job_id=job_id,
        shots=shots,
        counts=counts,
        provider="originq",
        timestamp=completed_at,
        meta={
            "chip_id": chip_id,
            "chip_qubits": qubit_count,
            "job_status": status,
            "vendor_package": "pyqpanda3",
            "vendor_version": vendor.version,
            "bit_order_verified": False,
        },
    )
    metadata = {
        "execution_kind": "qpu",
        "qpu_verified": True,
        "provider": "originq",
        "backend": normalized["backend"],
        "job_id": job_id,
        "shots": shots,
        "timestamp": completed_at,
        "submitted_at": submitted_at,
        "qualification": "QCloudBackend.chip_info() succeeded and returned chip_id/qubits_num",
        "chip_id": chip_id,
        "chip_qubits": qubit_count,
        "job_status": status,
        "vendor_package": "pyqpanda3",
        "vendor_version": vendor.version,
        "redaction_applied": True,
    }
    submission = {
        "provider": "originq",
        "backend": creds.backend_name,
        "shots": shots,
        "submitted_at": submitted_at,
        "qasm_converter": "pyqpanda3.intermediate_compiler.convert_qasm_string_to_qprog",
        "execution_api": "QCloudBackend.run(QProg, shots)",
    }
    return EvidenceBundle(
        provider="originq",
        input_qasm=source,
        submission=submission,
        raw_result=redact_payload(raw_result, (creds.api_key,)),
        normalized_result=normalized,
        metadata=metadata,
    )
