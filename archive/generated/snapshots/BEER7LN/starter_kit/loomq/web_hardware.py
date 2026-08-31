"""Local-only credential storage and asynchronous real-hardware execution."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import time
from typing import Any, Callable, Mapping
import unicodedata
from urllib.parse import urlsplit
import uuid

from .hardware import (
    extract_originq_counts,
    extract_spinq_counts,
    load_env_file,
    prepare_spinq_cloud_qasm,
)
from .qasm import Program, parse_openqasm2


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPOSITORY_ROOT / ".env.hardware.local"
CREDENTIALS_DIR = REPOSITORY_ROOT / "local_docs" / "credentials"
PROFILE_INDEX_FILE = CREDENTIALS_DIR / "profiles.json"
HARDWARE_JOBS_DIR = REPOSITORY_ROOT / "local_docs" / "hardware_jobs"
HARDWARE_DATABASE_FILE = REPOSITORY_ROOT / "local_docs" / "loomq.sqlite3"
LOCAL_OWNER_ID = "local"

ORIGINQ_CONFIRMATION = "ORIGINQ_WUKONG_180_REAL_QPU"
SPINQ_CONFIRMATION = "SPINQ_REAL_QPU"
CONFIRMATIONS = {
    "originq_wukong": ORIGINQ_CONFIRMATION,
    "spinq_cloud_qpu": SPINQ_CONFIRMATION,
}

MANAGED_ENV_NAMES = (
    "LOOMQ_ORIGINQ_API_TOKEN",
    "LOOMQ_ORIGINQ_BACKEND",
    "LOOMQ_SPINQ_USERNAME",
    "LOOMQ_SPINQ_KEYFILE",
    "LOOMQ_SPINQ_HOST",
    "LOOMQ_SPINQ_PLATFORM_CODE",
)
SECRET_ENV_NAMES = (
    "LOOMQ_ORIGINQ_API_TOKEN",
    "LOOMQ_SPINQ_USERNAME",
    "LOOMQ_SPINQ_KEYFILE",
)
PROVIDER_ENVIRONMENT = {
    "originq": "originq_wukong",
    "spinq": "spinq_cloud_qpu",
}
SYSTEM_PROFILE_IDS = {
    "originq": "system-originq-wukong",
    "spinq": "system-spinq-cloud-qpu",
}
SYSTEM_PROFILE_LABELS = {
    "originq": "系统配置 · 本源悟空",
    "spinq": "系统配置 · SpinQ",
}
PROVIDER_REQUIRED_ENV = {
    "originq": ("LOOMQ_ORIGINQ_API_TOKEN", "LOOMQ_ORIGINQ_BACKEND"),
    "spinq": (
        "LOOMQ_SPINQ_USERNAME",
        "LOOMQ_SPINQ_KEYFILE",
        "LOOMQ_SPINQ_HOST",
        "LOOMQ_SPINQ_PLATFORM_CODE",
    ),
}
_SIMPLE_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_USERNAME = re.compile(r"^[^\s\x00-\x1f\x7f]{1,256}$")
_PROFILE_ID = re.compile(r"^[0-9a-f]{32}$")
_MAX_QASM_LENGTH = 64_000

HardwareProgress = Callable[[str, str, Mapping[str, object] | None], None]


def _report_progress(
    progress: HardwareProgress | None,
    stage: str,
    message: str,
    **details: object,
) -> None:
    if progress is not None:
        progress(stage, message, details or None)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _plain_text(value: object, name: str, *, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise ValueError(f"{name} has an invalid length")
    if any(character in normalized for character in ("\r", "\n", "\x00")):
        raise ValueError(f"{name} must be a single-line value")
    return normalized


def _validate_private_key(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("private_key must be text")
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"
    if not 64 <= len(normalized.encode("utf-8")) <= 32_768 or "\x00" in normalized:
        raise ValueError("private_key has an invalid length")
    lines = normalized.splitlines()
    if (
        len(lines) < 3
        or not re.fullmatch(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", lines[0])
        or not re.fullmatch(r"-----END [A-Z0-9 ]*PRIVATE KEY-----", lines[-1])
        or any(len(line) > 4096 for line in lines)
    ):
        raise ValueError("private_key must be PEM private-key text")
    return normalized


def _validate_host(value: object) -> str:
    host = _plain_text(value, "host", minimum=8, maximum=2048)
    parsed = urlsplit(host)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("host must be an http(s) URL without credentials, query, or fragment")
    return host.rstrip("/")


def _restrict_permissions(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass


def _atomic_write(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _restrict_permissions(path.parent, 0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        _restrict_permissions(temporary, mode)
        os.replace(temporary, path)
        _restrict_permissions(path, mode)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_label(value: object) -> str:
    label = _plain_text(value, "label", minimum=1, maximum=80)
    if any(unicodedata.category(character).startswith("C") for character in label):
        raise ValueError("label must not contain control characters")
    return label


def _validate_credentials(
    provider: object, credentials: object
) -> dict[str, str]:
    if not isinstance(credentials, Mapping):
        raise ValueError("credentials must be an object")
    if provider == "originq":
        if set(credentials) != {"token", "backend"}:
            raise ValueError("OriginQ credentials must contain only token and backend")
        token = _plain_text(credentials.get("token"), "token", minimum=8, maximum=4096)
        if any(character.isspace() for character in token):
            raise ValueError("token must not contain whitespace")
        backend = _plain_text(credentials.get("backend"), "backend", minimum=1, maximum=128)
        if not _SIMPLE_CODE.fullmatch(backend):
            raise ValueError("backend contains unsupported characters")
        return {"token": token, "backend": backend}
    elif provider == "spinq":
        expected = {"username", "private_key", "host", "platform_code"}
        if set(credentials) != expected:
            raise ValueError(
                "SpinQ credentials must contain only username, private_key, host, and platform_code"
            )
        username = _plain_text(
            credentials.get("username"), "username", minimum=1, maximum=256
        )
        if not _USERNAME.fullmatch(username):
            raise ValueError("username contains unsupported characters")
        private_key = _validate_private_key(credentials.get("private_key"))
        host = _validate_host(credentials.get("host"))
        platform_code = _plain_text(
            credentials.get("platform_code"),
            "platform_code",
            minimum=1,
            maximum=128,
        )
        if not _SIMPLE_CODE.fullmatch(platform_code):
            raise ValueError("platform_code contains unsupported characters")
        return {
            "username": username,
            "private_key": private_key,
            "host": host,
            "platform_code": platform_code,
        }
    raise ValueError("provider must be originq or spinq")


def _masked_username(username: str) -> str:
    if len(username) <= 2:
        return "*" * len(username)
    return username[0] + ("*" * min(8, len(username) - 2)) + username[-1]


def _public_metadata(provider: str, credentials: Mapping[str, str]) -> dict[str, str]:
    if provider == "originq":
        return {"backend": credentials["backend"], "token": "configured"}
    return {
        "username": _masked_username(credentials["username"]),
        "private_key": "configured",
        "host": credentials["host"],
        "platform_code": credentials["platform_code"],
    }


class ProfileNotFoundError(ValueError):
    pass


class ProfileReadOnlyError(ValueError):
    pass


class HardwareExecutionError(RuntimeError):
    """Credential-safe execution failure suitable for the browser."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.public_message = message


class HardwareProfiles:
    """Thread-safe, session-only user hardware profile repository."""

    def __init__(
        self,
        *,
        credentials_dir: Path = CREDENTIALS_DIR,
        env_file: Path = ENV_FILE,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.credentials_dir = Path(credentials_dir)
        self.index_file = self.credentials_dir / "profiles.json"
        self.env_file = Path(env_file)
        self.environ = os.environ if environ is None else environ
        self._lock = threading.RLock()
        self._user_profiles: list[dict[str, object]] = []
        self._user_credentials: dict[str, dict[str, str]] = {}

    def _read_index(self) -> list[dict[str, object]]:
        return [dict(profile) for profile in self._user_profiles]

    def _write_index(self, profiles: list[dict[str, object]]) -> None:
        self._user_profiles = [dict(profile) for profile in profiles]

    def _secret_file(self, profile_id: str) -> Path:
        if not _PROFILE_ID.fullmatch(profile_id):
            raise ProfileNotFoundError("hardware profile not found")
        return self.credentials_dir / "secrets" / f"{profile_id}.json"

    def _system_environment(self) -> dict[str, str]:
        file_values: dict[str, str] = {}
        if self.env_file.is_file():
            try:
                file_values = load_env_file(self.env_file)
            except (OSError, ValueError) as exc:
                raise RuntimeError("system hardware configuration is unavailable") from exc
        return {
            name: str(self.environ.get(name) or file_values.get(name) or "").strip()
            for name in MANAGED_ENV_NAMES
        }

    def _system_profiles(
        self, *, include_credentials: bool = False
    ) -> list[tuple[dict[str, object], dict[str, str] | None]]:
        environment = self._system_environment()
        profiles: list[tuple[dict[str, object], dict[str, str] | None]] = []
        for provider in ("originq", "spinq"):
            if not all(environment.get(name) for name in PROVIDER_REQUIRED_ENV[provider]):
                continue
            if provider == "originq":
                credentials = {
                    "token": environment["LOOMQ_ORIGINQ_API_TOKEN"],
                    "backend": environment["LOOMQ_ORIGINQ_BACKEND"],
                }
            else:
                key_file = Path(environment["LOOMQ_SPINQ_KEYFILE"])
                if not key_file.is_file():
                    continue
                credentials = {
                    "username": environment["LOOMQ_SPINQ_USERNAME"],
                    "private_key": (
                        key_file.read_text(encoding="utf-8") if include_credentials else ""
                    ),
                    "host": environment["LOOMQ_SPINQ_HOST"],
                    "platform_code": environment["LOOMQ_SPINQ_PLATFORM_CODE"],
                }
            public = {
                "id": SYSTEM_PROFILE_IDS[provider],
                "label": SYSTEM_PROFILE_LABELS[provider],
                "provider": provider,
                "source": "system",
                "environment_id": PROVIDER_ENVIRONMENT[provider],
                "metadata": _public_metadata(provider, credentials),
            }
            profiles.append((public, credentials if include_credentials else None))
        return profiles

    def list(self) -> dict[str, object]:
        with self._lock:
            users = self._read_index()
            return {"profiles": [dict(profile) for profile in users]}

    def _ensure_unique_label(
        self, label: str, profiles: list[dict[str, object]], exclude_id: str | None = None
    ) -> None:
        occupied = {
            str(profile.get("label", "")).casefold()
            for profile in profiles
            if profile.get("id") != exclude_id
        }
        if label.casefold() in occupied:
            raise ValueError("label must be unique")

    def create(self, request: Mapping[str, object]) -> dict[str, object]:
        if set(request) != {"label", "provider", "credentials"}:
            raise ValueError("request must contain only label, provider, and credentials")
        label = _validate_label(request.get("label"))
        provider = request.get("provider")
        credentials = _validate_credentials(provider, request.get("credentials"))
        provider_name = str(provider)
        with self._lock:
            profiles = self._read_index()
            self._ensure_unique_label(label, profiles)
            profile_id = uuid.uuid4().hex
            public = {
                "id": profile_id,
                "label": label,
                "provider": provider_name,
                "source": "user",
                "environment_id": PROVIDER_ENVIRONMENT[provider_name],
                "metadata": _public_metadata(provider_name, credentials),
            }
            self._user_credentials[profile_id] = dict(credentials)
            self._write_index(profiles + [public])
            return dict(public)

    def update(self, profile_id: str, request: Mapping[str, object]) -> dict[str, object]:
        if not request or not set(request) <= {"label", "credentials"}:
            raise ValueError("request may contain only label and credentials")
        if profile_id in SYSTEM_PROFILE_IDS.values():
            raise ProfileReadOnlyError("system hardware profiles are read-only")
        with self._lock:
            profiles = self._read_index()
            position = next(
                (index for index, item in enumerate(profiles) if item.get("id") == profile_id),
                None,
            )
            if position is None:
                raise ProfileNotFoundError("hardware profile not found")
            current = dict(profiles[position])
            label = (
                _validate_label(request["label"])
                if "label" in request
                else str(current["label"])
            )
            self._ensure_unique_label(label, profiles, exclude_id=profile_id)
            credentials = self._user_credentials.get(profile_id)
            if credentials is None:
                raise RuntimeError("hardware profile credentials are invalid")
            credentials = dict(credentials)
            if "credentials" in request:
                changes = request["credentials"]
                if not isinstance(changes, Mapping):
                    raise ValueError("credentials must be an object")
                allowed = (
                    {"token", "backend"}
                    if current["provider"] == "originq"
                    else {"username", "private_key", "host", "platform_code"}
                )
                if not changes or not set(changes) <= allowed:
                    raise ValueError("credentials contain unsupported fields")
                credentials.update(changes)
                credentials = _validate_credentials(current["provider"], credentials)
                self._user_credentials[profile_id] = dict(credentials)
            current.update(
                {
                    "label": label,
                    "metadata": _public_metadata(str(current["provider"]), credentials),
                }
            )
            profiles[position] = current
            self._write_index(profiles)
            return dict(current)

    def delete(self, profile_id: str) -> dict[str, object]:
        if profile_id in SYSTEM_PROFILE_IDS.values():
            raise ProfileReadOnlyError("system hardware profiles are read-only")
        with self._lock:
            profiles = self._read_index()
            remaining = [item for item in profiles if item.get("id") != profile_id]
            if len(remaining) == len(profiles):
                raise ProfileNotFoundError("hardware profile not found")
            self._write_index(remaining)
            self._user_credentials.pop(profile_id, None)
            return {"deleted": True, "id": profile_id}

    def resolve(self, profile_id: str) -> tuple[dict[str, object], dict[str, str]]:
        with self._lock:
            if not _PROFILE_ID.fullmatch(profile_id):
                raise ProfileNotFoundError("hardware profile not found")
            profile = next(
                (item for item in self._read_index() if item.get("id") == profile_id),
                None,
            )
            if profile is None:
                raise ProfileNotFoundError("hardware profile not found")
            raw = self._user_credentials.get(profile_id)
            if raw is None:
                raise RuntimeError("hardware profile credentials are unavailable")
            credentials = _validate_credentials(profile.get("provider"), raw)
            return dict(profile), credentials


PROFILES = HardwareProfiles()


def configure_hardware(
    request: Mapping[str, object],
    *,
    env_file: Path = ENV_FILE,
    credentials_dir: Path = CREDENTIALS_DIR,
) -> dict[str, object]:
    """Compatibility wrapper that creates a user profile without changing system env."""

    if not set(request) <= {"label", "provider", "credentials"}:
        raise ValueError("request may contain only label, provider, and credentials")
    provider = request.get("provider")
    default_label = f"{'OriginQ' if provider == 'originq' else 'SpinQ'} 用户配置"
    profile_request = {
        "label": request.get("label", default_label),
        "provider": provider,
        "credentials": request.get("credentials"),
    }
    store = (
        PROFILES
        if Path(credentials_dir) == CREDENTIALS_DIR and Path(env_file) == ENV_FILE
        else HardwareProfiles(credentials_dir=credentials_dir, env_file=env_file)
    )
    return store.create(profile_request)


def _validate_submission(
    request: Mapping[str, object],
) -> tuple[str, str, str, int, Program]:
    allowed = {
        "profile_id",
        "environment_id",
        "qasm",
        "shots",
        "confirm",
        "confirmation_token",
    }
    if set(request) != allowed:
        raise ValueError(
            "request must contain only profile_id, environment_id, qasm, shots, confirm, and confirmation_token"
        )
    profile_id = request.get("profile_id")
    if not isinstance(profile_id, str) or not profile_id:
        raise ValueError("profile_id must identify a hardware profile")
    environment_id = request.get("environment_id")
    if environment_id not in CONFIRMATIONS:
        raise ValueError("unsupported hardware environment")
    if request.get("confirm") is not True:
        raise ValueError("explicit hardware confirmation is required")
    if request.get("confirmation_token") != CONFIRMATIONS[environment_id]:
        raise ValueError("hardware confirmation token is invalid")
    qasm = request.get("qasm")
    if not isinstance(qasm, str) or not qasm.strip() or len(qasm) > _MAX_QASM_LENGTH:
        raise ValueError("qasm must be a non-empty OpenQASM program within 64000 characters")
    shots = request.get("shots")
    if not isinstance(shots, int) or isinstance(shots, bool) or not 1 <= shots <= 4096:
        raise ValueError("shots must be an integer between 1 and 4096")
    program = parse_openqasm2(qasm)
    return profile_id, str(environment_id), qasm.strip(), shots, program


def _originq_timestamp(timing: Mapping[str, object], fallback: str) -> str:
    for key in ("startTime", "createTime", "submitTime", "endTime"):
        value = timing.get(key)
        if isinstance(value, str) and value:
            if value.isdigit():
                epoch = int(value)
                seconds = epoch / 1000 if epoch > 10_000_000_000 else epoch
                return datetime.fromtimestamp(seconds, timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                )
            return value
    return fallback


def run_originq(
    qasm: str,
    shots: int,
    program: Program,
    config: Mapping[str, str],
    progress: HardwareProgress | None = None,
) -> dict[str, object]:
    """Submit arbitrary supported QASM through pyqpanda3 and wait for completion."""

    import adapter
    from pyqpanda3.intermediate_compiler import convert_originir_string_to_qprog
    from pyqpanda3.qcloud import DataBase, JobStatus, QCloudOptions, QCloudService

    _report_progress(progress, "compiling", "正在编译并检查本源悟空电路。")
    executed = adapter.transpile(qasm, "originq")
    qprog = convert_originir_string_to_qprog(executed)
    backend_name = config["backend"]
    service = QCloudService(config["token"])
    backend = service.backend(backend_name)
    _report_progress(progress, "connecting", "正在读取本源悟空设备与调度状态。")
    try:
        chip_info = backend.chip_info()
    except Exception as exc:
        if "unauthorized" in str(exc).lower():
            raise HardwareExecutionError(
                "originq_unauthorized",
                "本源悟空认证失败，请在本源量子云重新生成 API Token 后更新系统配置。",
            ) from None
        raise HardwareExecutionError(
            "originq_backend_unavailable",
            "无法读取本源悟空设备状态，请稍后重试。",
        ) from None
    if chip_info.qubits_num() != 180:
        raise ValueError("configured OriginQ backend is not a Wukong 180 QPU")
    blocks = backend.best_qubit_blocks(
        qubit_num=program.quantum_register.size, label=1, qubit_block_num=1
    )
    if blocks.empty():
        raise HardwareExecutionError(
            "originq_no_qubit_block",
            "所选本源悟空实例当前没有可调度的逻辑 qubit 块。",
        )
    selected_block = list(blocks.block(0))
    options = QCloudOptions()
    options.set_mapping(True)
    options.set_optimization(True)
    options.set_amend(True)
    if selected_block:
        options.set_specified_block(selected_block)
    submitted_at = utc_now()
    try:
        job = backend.run(
            qprog, shots=shots, options=options, batch_id="LoomQ-Web-Hardware"
        )
    except Exception:
        raise HardwareExecutionError(
            "originq_submission_failed",
            "本源悟空未接受任务，请检查账户额度、设备权限与电路兼容性。",
        ) from None
    job_id = job.job_id()
    if not job_id:
        raise HardwareExecutionError(
            "originq_missing_job_id",
            "本源悟空接受了请求但没有返回任务 ID，请先检查平台任务列表。",
        )
    _report_progress(
        progress,
        "submitted",
        "任务已由本源平台接收，正在排队或执行。",
        provider_job_id=str(job_id),
        backend=backend_name,
        physical_qubits=selected_block,
    )
    deadline = time.monotonic() + float(os.environ.get("LOOMQ_HARDWARE_TIMEOUT", "7200"))
    poll_seconds = float(os.environ.get("LOOMQ_HARDWARE_POLL_SECONDS", "10"))
    try:
        status = job.status()
    except Exception:
        raise HardwareExecutionError(
            "originq_status_failed",
            f"本源任务 {job_id} 已创建，但暂时无法读取状态。",
        ) from None
    while status not in (JobStatus.FINISHED, JobStatus.FAILED):
        if time.monotonic() >= deadline:
            raise HardwareExecutionError(
                "originq_timeout",
                f"本源任务 {job_id} 仍在运行，已停止本地轮询。",
            )
        time.sleep(max(0.1, poll_seconds))
        try:
            status = job.status()
        except Exception:
            raise HardwareExecutionError(
                "originq_status_failed",
                f"本源任务 {job_id} 已创建，但暂时无法读取状态。",
            ) from None
        _report_progress(
            progress,
            "running",
            "本源平台正在排队、映射物理 qubit 或执行电路。",
            provider_job_id=str(job_id),
            provider_status=getattr(status, "name", str(status)),
        )
    if status == JobStatus.FAILED:
        raise HardwareExecutionError(
            "originq_provider_failed",
            f"本源平台将任务 {job_id} 标记为失败。",
        )
    _report_progress(
        progress,
        "reading_result",
        "真机执行已结束，正在读取并校验 counts。",
        provider_job_id=str(job_id),
    )
    try:
        result = job.result(
            keys=[
                "mappingQprog",
                "mappingQubit",
                "probCount",
                "convertQProg",
                "srcQubits",
                "targetCbits",
                "measureQubits",
            ]
        )
    except (RuntimeError, TypeError):
        try:
            result = job.result()
        except Exception:
            raise HardwareExecutionError(
                "originq_result_failed",
                f"本源任务 {job_id} 已完成，但结果暂时无法读取。",
            ) from None
    width = program.classical_register.size
    try:
        raw_counts = dict(result.get_counts(base=DataBase.Binary))
    except Exception:
        raise HardwareExecutionError(
            "originq_result_invalid",
            f"本源任务 {job_id} 返回了当前 SDK 无法解析的结果。",
        ) from None
    if raw_counts:
        counts: dict[str, int] = {}
        for raw_state, raw_count in raw_counts.items():
            state = str(raw_state).replace(" ", "")
            state = (
                format(int(state, 16), f"0{width}b")
                if state.lower().startswith("0x")
                else state.zfill(width)
            )
            if set(state) - {"0", "1"} or len(state) != width:
                raise ValueError("OriginQ result contains an invalid bitstring")
            counts[state] = counts.get(state, 0) + int(raw_count)
        if sum(counts.values()) != shots:
            raise ValueError("OriginQ counts do not sum to shots")
        counts = dict(sorted(counts.items()))
    else:
        counts = extract_originq_counts(
            dict(result.get_probs(base=DataBase.Binary)), shots, width
        )
    return {
        "platform": "Origin Quantum Cloud",
        "backend": backend_name,
        "job_id": str(job_id),
        "timestamp": _originq_timestamp(dict(result.timing_info()), submitted_at),
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
    }


def _compile_spinq_ir(qasm: str) -> object:
    from spinqit import get_compiler

    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".qasm", delete=False, encoding="utf-8"
        ) as temporary:
            temporary.write(qasm)
            temporary_name = temporary.name
        return get_compiler("qasm").compile(temporary_name, 0)
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def run_spinq(
    qasm: str,
    shots: int,
    program: Program,
    config: Mapping[str, str],
    progress: HardwareProgress | None = None,
) -> dict[str, object]:
    """Submit arbitrary supported QASM through spinqit and wait for completion."""

    import adapter
    from spinqit import SpinQCloudConfig, get_spinq_cloud

    _report_progress(progress, "compiling", "正在编译并检查 SpinQ 电路。")
    try:
        transpiled = adapter.transpile(qasm, "spinq")
        executed = prepare_spinq_cloud_qasm(transpiled)
        ir = _compile_spinq_ir(executed)
    except Exception:
        raise HardwareExecutionError(
            "spinq_compile_failed",
            "当前电路无法编译为 SpinQ 真机任务。",
        ) from None
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pem", delete=False, encoding="utf-8"
        ) as key_stream:
            key_stream.write(config["private_key"])
            temporary_name = key_stream.name
        _restrict_permissions(Path(temporary_name), 0o600)
        _report_progress(progress, "connecting", "正在连接 SpinQ 云服务并读取设备状态。")
        try:
            backend = get_spinq_cloud(
                config["username"], temporary_name, config["host"]
            )
            platform = backend.get_platform(config["platform_code"])
        except Exception:
            raise HardwareExecutionError(
                "spinq_connection_failed",
                "无法连接或登录 SpinQ 云服务，请检查网络后重试。",
            ) from None
        if platform.simu:
            raise HardwareExecutionError(
                "spinq_not_hardware",
                "所选 SpinQ 平台不是量子真机。",
            )
        if program.quantum_register.size > platform.max_bitnum:
            raise HardwareExecutionError(
                "spinq_qubit_limit",
                f"当前电路需要 {program.quantum_register.size} qubit，但所选 SpinQ 真机最多支持 {platform.max_bitnum} qubit。",
            )
        if not platform.available():
            raise HardwareExecutionError(
                "spinq_offline",
                "所选 SpinQ 真机当前离线。",
            )
        submitted_at = utc_now()
        cloud_config = SpinQCloudConfig()
        cloud_config.configure_platform(platform.code)
        cloud_config.configure_shots(shots)
        task_name = f"LoomQ-web-{submitted_at[:19].replace(':', '')}Z"
        cloud_config.configure_task(task_name, "LoomQ web real-hardware task")
        try:
            status, _message, job_id = backend.submit_task(
                ir, cloud_config, debug=False
            )
        except Exception:
            raise HardwareExecutionError(
                "spinq_submission_failed",
                "SpinQ 未确认任务创建；请先在平台任务列表核对，避免重复提交。",
            ) from None
        if not job_id:
            raise HardwareExecutionError(
                "spinq_missing_job_id",
                f"SpinQ 未返回任务 ID（状态 {status}），请在平台任务列表核对。",
            )
        _report_progress(
            progress,
            "submitted",
            "任务已由 SpinQ 平台接收，正在排队或执行。",
            provider_job_id=str(job_id),
            backend=str(platform.code),
            provider_status=str(status),
        )
        deadline = time.monotonic() + float(
            os.environ.get("LOOMQ_HARDWARE_TIMEOUT", "1800")
        )
        poll_seconds = float(os.environ.get("LOOMQ_HARDWARE_POLL_SECONDS", "5"))
        result_payload: Mapping[str, object] | None = None
        query_failures = 0
        while time.monotonic() < deadline:
            try:
                response = backend._api_client.task_result(str(job_id))
                query_failures = 0
            except Exception:
                query_failures += 1
                if query_failures >= 3:
                    raise HardwareExecutionError(
                        "spinq_poll_failed",
                        f"SpinQ 任务 {job_id} 已提交，但连续三次无法读取结果；请稍后用任务 ID 查询。",
                    ) from None
                time.sleep(max(0.1, poll_seconds))
                continue
            if response.status_code == 412:
                _report_progress(
                    progress,
                    "running",
                    "SpinQ 平台正在排队或执行电路。",
                    provider_job_id=str(job_id),
                    provider_status="processing",
                )
                time.sleep(max(0.1, poll_seconds))
                continue
            if response.status_code not in (200, 202):
                raise HardwareExecutionError(
                    "spinq_result_http_error",
                    f"SpinQ 任务 {job_id} 已提交，但结果查询返回 HTTP {response.status_code}。",
                )
            candidate = json.loads(bytes(response.content).decode("utf-8"))
            if candidate.get("taskStatus") == "F":
                raise HardwareExecutionError(
                    "spinq_provider_failed",
                    f"SpinQ 平台将任务 {job_id} 标记为失败。",
                )
            run = candidate.get("run")
            if isinstance(run, Mapping) and (run.get("count") or run.get("module")):
                result_payload = candidate
                break
            _report_progress(
                progress,
                "running",
                "SpinQ 平台正在排队或执行电路。",
                provider_job_id=str(job_id),
                provider_status=str(candidate.get("taskStatus") or "processing"),
            )
            time.sleep(max(0.1, poll_seconds))
        if result_payload is None:
            raise HardwareExecutionError(
                "spinq_timeout",
                f"SpinQ 任务 {job_id} 仍在运行，已停止本地轮询；可稍后用任务 ID 查询。",
            )
        _report_progress(
            progress,
            "reading_result",
            "真机执行已结束，正在读取并校验 counts。",
            provider_job_id=str(job_id),
        )
        return {
            "platform": "SpinQ Cloud",
            "backend": str(platform.code),
            "job_id": str(job_id),
            "timestamp": submitted_at,
            "shots": shots,
            "counts": extract_spinq_counts(
                result_payload, shots, program.classical_register.size
            ),
            "bit_order": "little",
        }
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


Runner = Callable[[str, int, Program, Mapping[str, str]], dict[str, object]]


class HardwareJobs:
    """Thread-safe, credential-free persistent hardware task history."""

    def __init__(
        self,
        runners: Mapping[str, Runner] | None = None,
        thread_factory: Callable[..., threading.Thread] = threading.Thread,
        profiles: HardwareProfiles | None = None,
        database_file: Path | None = None,
        owner_id: str = LOCAL_OWNER_ID,
    ) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, object]] = {}
        self._runners = dict(
            runners
            or {
                "originq_wukong": run_originq,
                "spinq_cloud_qpu": run_spinq,
            }
        )
        self._thread_factory = thread_factory
        self._profiles = profiles or PROFILES
        self.owner_id = _plain_text(owner_id, "owner_id", minimum=1, maximum=128)
        self.database_file = Path(
            database_file
            or (
                HARDWARE_DATABASE_FILE
                if profiles is None or profiles is PROFILES
                else self._profiles.credentials_dir.parent / "loomq.sqlite3"
            )
        )
        self.legacy_history_dir = self.database_file.parent / "hardware_jobs"
        self._initialize_database()
        self._migrate_legacy_history()
        self._load_history()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_file, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_database(self) -> None:
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        _restrict_permissions(self.database_file.parent, 0o700)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS hardware_jobs (
                        task_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS hardware_jobs_owner_created
                    ON hardware_jobs(owner_id, created_at DESC)
                    """
                )
        _restrict_permissions(self.database_file, 0o600)

    def _write_database_record(self, job: Mapping[str, object]) -> None:
        payload = json.dumps(dict(job), ensure_ascii=False, separators=(",", ":"))
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO hardware_jobs(
                        task_id, owner_id, status, created_at, updated_at, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(task_id) DO UPDATE SET
                        owner_id=excluded.owner_id,
                        status=excluded.status,
                        created_at=excluded.created_at,
                        updated_at=excluded.updated_at,
                        payload_json=excluded.payload_json
                    """,
                    (
                        job["task_id"],
                        self.owner_id,
                        job["status"],
                        job["created_at"],
                        job["updated_at"],
                        payload,
                    ),
                )
        _restrict_permissions(self.database_file, 0o600)

    def _migrate_legacy_history(self) -> None:
        if not self.legacy_history_dir.is_dir():
            return
        for path in self.legacy_history_dir.glob("*.json"):
            if not re.fullmatch(r"[0-9a-f]{32}\.json", path.name):
                continue
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(job, dict) or job.get("task_id") != path.stem:
                continue
            self._write_database_record(job)
            path.unlink(missing_ok=True)
        try:
            self.legacy_history_dir.rmdir()
        except OSError:
            pass

    def _persist_unlocked(self, task_id: str) -> None:
        self._write_database_record(self._jobs[task_id])

    def _load_history(self) -> None:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM hardware_jobs
                WHERE owner_id = ?
                ORDER BY created_at ASC
                """,
                (self.owner_id,),
            ).fetchall()
        for (payload_json,) in rows:
            try:
                job = json.loads(payload_json)
            except json.JSONDecodeError:
                continue
            task_id = job.get("task_id") if isinstance(job, dict) else None
            if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-f]{32}", task_id):
                continue
            if job.get("status") in {"pending", "running"}:
                job.update(
                    {
                        "status": "interrupted",
                        "stage": "interrupted",
                        "stage_message": "本地服务曾在任务完成前停止；平台任务不会因此自动取消。",
                        "updated_at": utc_now(),
                    }
                )
            self._jobs[task_id] = job
            self._persist_unlocked(task_id)

    def _update(self, task_id: str, update: Mapping[str, object]) -> None:
        with self._lock:
            current = self._jobs.get(task_id)
            if current is None:
                return
            self._jobs[task_id] = {
                **current,
                **dict(update),
                "updated_at": utc_now(),
            }
            self._persist_unlocked(task_id)

    def _progress(
        self,
        task_id: str,
        stage: str,
        message: str,
        details: Mapping[str, object] | None,
    ) -> None:
        allowed_details = {
            key: value
            for key, value in dict(details or {}).items()
            if key
            in {
                "provider_job_id",
                "backend",
                "physical_qubits",
                "provider_status",
            }
        }
        self._update(
            task_id,
            {
                "status": "running",
                "stage": stage,
                "stage_message": message,
                **allowed_details,
            },
        )

    def submit(self, request: Mapping[str, object]) -> dict[str, object]:
        profile_id, environment_id, qasm, shots, program = _validate_submission(request)
        profile, credentials = self._profiles.resolve(profile_id)
        if profile.get("environment_id") != environment_id:
            raise ValueError("hardware profile does not match the selected environment")
        expected_provider = (
            "originq" if environment_id == "originq_wukong" else "spinq"
        )
        if profile.get("provider") != expected_provider:
            raise ValueError("hardware profile provider does not match the selected environment")
        if (
            environment_id == "spinq_cloud_qpu"
            and credentials.get("platform_code") == "gemini_vp"
            and program.quantum_register.size > 2
        ):
            raise ValueError(
                f"当前电路需要 {program.quantum_register.size} qubit，但 SpinQ gemini_vp 真机最多支持 2 qubit"
            )
        task_id = uuid.uuid4().hex
        created_at = utc_now()
        public = {
            "task_id": task_id,
            "environment_id": environment_id,
            "profile_id": profile_id,
            "profile_label": profile["label"],
            "provider": profile["provider"],
            "status": "pending",
            "stage": "accepted",
            "stage_message": "本地服务已接受任务，正在启动真机执行流程。",
            "created_at": created_at,
            "updated_at": created_at,
            "shots": shots,
            "qubits": program.quantum_register.size,
            "qasm": qasm,
        }
        with self._lock:
            self._jobs[task_id] = public
            self._persist_unlocked(task_id)
        thread = self._thread_factory(
            target=self._execute,
            args=(task_id, environment_id, qasm, shots, program, dict(credentials)),
            daemon=True,
            name=f"loomq-hardware-{task_id[:8]}",
        )
        thread.start()
        return dict(public)

    def _execute(
        self,
        task_id: str,
        environment_id: str,
        qasm: str,
        shots: int,
        program: Program,
        credentials: Mapping[str, str],
    ) -> None:
        self._update(
            task_id,
            {
                "status": "running",
                "stage": "starting",
                "stage_message": "正在准备 SDK 与凭据快照。",
                "started_at": utc_now(),
            },
        )
        try:
            runner = self._runners[environment_id]
            if runner is run_originq or runner is run_spinq:
                result = runner(
                    qasm,
                    shots,
                    program,
                    credentials,
                    lambda stage, message, details=None: self._progress(
                        task_id, stage, message, details
                    ),
                )
            else:
                result = runner(qasm, shots, program, credentials)
            required = {
                "platform",
                "backend",
                "job_id",
                "timestamp",
                "shots",
                "counts",
                "bit_order",
            }
            if set(result) != required:
                raise RuntimeError("hardware runner returned an invalid result")
            update = {
                "status": "completed",
                "stage": "completed",
                "stage_message": "真机任务已完成，counts 已保存。",
                "completed_at": utc_now(),
                "provider_job_id": result["job_id"],
                "backend": result["backend"],
                "result": result,
            }
        except HardwareExecutionError as exc:
            update = {
                "status": "failed",
                "stage": "failed",
                "stage_message": exc.public_message,
                "completed_at": utc_now(),
                "error_code": exc.code,
                "error": exc.public_message,
            }
        except Exception:
            # Provider exceptions are deliberately not exposed: SDKs may echo credentials.
            update = {
                "status": "failed",
                "stage": "failed",
                "stage_message": "真机执行失败，未暴露供应商原始异常。",
                "completed_at": utc_now(),
                "error_code": "hardware_execution_failed",
                "error": "Hardware execution failed; check provider access and local service diagnostics.",
            }
        self._update(task_id, update)

    def get(self, task_id: str) -> dict[str, object] | None:
        if not re.fullmatch(r"[0-9a-f]{32}", task_id):
            return None
        with self._lock:
            job = self._jobs.get(task_id)
            return dict(job) if job is not None else None

    def list(self) -> dict[str, object]:
        with self._lock:
            jobs = sorted(
                self._jobs.values(),
                key=lambda item: str(item.get("created_at", "")),
                reverse=True,
            )
            summaries = [
                {
                    key: value
                    for key, value in job.items()
                    if key not in {"qasm", "result"}
                }
                | {
                    "has_qasm": bool(job.get("qasm")),
                    "has_result": bool(job.get("result")),
                }
                for job in jobs
            ]
            return {"jobs": summaries}


JOBS = HardwareJobs()
