#!/usr/bin/env python3
"""Runtime (in-memory) LLM configuration with environment-variable fallback.

任务书 §19/§20/§21/§22/§23:

* Priority is ``runtime web config -> environment variables -> not configured``.
* The competition environment contract is left untouched.  Web-only runtime
  values use a request-local context override, so concurrent calls never mutate
  or observe one another through process-global ``os.environ``.
* The API key never leaves the process as plaintext: ``effective()`` exposes only
  an ``api_key_present`` boolean; the full key is available only to ``resolve()``
  and is never serialized into any HTTP-facing payload (任务书 §21/§22).
"""

from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib.parse import urlsplit

ENV_BASE_URL = "LOOMQ_LLM_BASE_URL"
ENV_API_KEY = "LOOMQ_LLM_API_KEY"
ENV_MODEL = "LOOMQ_LLM_MODEL"
REQUIRED_ENV = (ENV_BASE_URL, ENV_API_KEY, ENV_MODEL)
OPTIONAL_ENV = (
    "QUANTUMHELPER_ENABLE_LLM",
    "LOOMQ_LLM_TIMEOUT_SECONDS",
    "LOOMQ_LLM_MAX_OUTPUT_TOKENS",
)
ENV_FILE_KEYS = frozenset(REQUIRED_ENV + OPTIONAL_ENV)

#: The three runtime sources ``effective()`` reports.
SOURCE_RUNTIME = "runtime"
SOURCE_ENVIRONMENT = "environment"
SOURCE_NONE = "none"


def _normalize_base_url(base_url: str) -> str:
    """Validate a model endpoint before a secret can be sent to it."""
    normalized = base_url.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Base URL 必须是完整的 http:// 或 https:// 地址")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Base URL 不能包含账号、密码、查询参数或片段")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("远程模型地址必须使用 HTTPS；HTTP 仅允许本机地址")
    return normalized


def load_env_file(path: Path) -> bool:
    """Load an optional server-side .env without overriding real environment.

    Only the small QuantumHelper allowlist is accepted.  Values are parsed as
    data (no shell expansion/evaluation), and neither keys nor values are logged.
    """
    if not path.is_file():
        return False
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError("模型 .env 包含无效行")
        name, value = line.split("=", 1)
        name = name.strip()
        if name not in ENV_FILE_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(name, value)
    return True


class RuntimeConfig:
    """Process-internal, thread-safe runtime LLM configuration.

    Holds at most one (base_url, api_key, model) triple in memory.  When no
    runtime value has been set (or after ``clear()``), resolution falls back to
    the ``LOOMQ_LLM_*`` environment variables; if those are absent the
    configuration is reported as ``"none"``.

    The full API key is stored only on this instance and is returned only by
    ``resolve()`` for in-process use.  ``effective()`` deliberately never
    includes it.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._base_url: str | None = None
        self._api_key: str | None = None
        self._model: str | None = None
        self._source: str | None = None

    def set(self, base_url, api_key, model, *, source: str = SOURCE_RUNTIME) -> None:
        """Store a runtime configuration (validates inputs, never writes to disk)."""
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("Base URL 必须是非空字符串")
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("API Key 必须是非空字符串")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("模型名必须是非空字符串")
        with self._lock:
            self._base_url = _normalize_base_url(base_url)
            self._api_key = api_key
            self._model = model.strip()
            self._source = source or SOURCE_RUNTIME

    def clear(self) -> None:
        """Return to "unconfigured / environment-only" state (drops the key)."""
        with self._lock:
            self._base_url = None
            self._api_key = None
            self._model = None
            self._source = None

    def _runtime_triple(self) -> tuple[str, str, str] | None:
        """The stored runtime triple, or ``None`` when incomplete."""
        if self._source is None:
            return None
        if not (self._base_url and self._api_key and self._model):
            return None
        return (self._base_url, self._api_key, self._model)

    @staticmethod
    def _env_triple() -> tuple[str, str, str] | None:
        """Read the LOOMQ_LLM_* environment (read-only, never mutates it)."""
        base_url = os.environ.get(ENV_BASE_URL)
        api_key = os.environ.get(ENV_API_KEY)
        model = os.environ.get(ENV_MODEL)
        if base_url and api_key and model:
            return (_normalize_base_url(base_url), api_key, model.strip())
        return None

    def resolve(self) -> tuple[str, str, str] | None:
        """Resolve the effective triple for an actual LLM call.

        Priority: runtime > environment > ``None``.  Returns the full
        ``(base_url, api_key, model)`` including the key — for in-process use
        only, never exposed through ``effective()``.
        """
        with self._lock:
            runtime = self._runtime_triple()
        if runtime is not None:
            return runtime
        return self._env_triple()

    def effective(self) -> dict[str, Any]:
        """Safe, serializable view: no full API key, only ``api_key_present``."""
        with self._lock:
            runtime = self._runtime_triple()
            runtime_model = runtime[2] if runtime is not None else None
            runtime_base_url = runtime[0] if runtime is not None else None
        env = self._env_triple()
        if runtime is not None:
            return {
                "configured": True,
                "source": SOURCE_RUNTIME,
                "model": runtime_model,
                "base_url": runtime_base_url,
                "api_key_present": True,
            }
        if env is not None:
            return {
                "configured": True,
                "source": SOURCE_ENVIRONMENT,
                "model": env[2],
                "base_url": env[0],
                "api_key_present": True,
            }
        return {
            "configured": False,
            "source": SOURCE_NONE,
            "model": None,
            "base_url": None,
            "api_key_present": False,
        }


#: Process-wide singleton (任务书 §19: in-process singleton).
_INSTANCE: RuntimeConfig | None = None
_INSTANCE_LOCK = threading.Lock()


def get_runtime_config() -> RuntimeConfig:
    """Return the process-wide :class:`RuntimeConfig` singleton."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = RuntimeConfig()
        return _INSTANCE


# --------------------------------------------------------------------------
# Connectivity probe (任务书 §20)
# --------------------------------------------------------------------------

def _chat_completion() -> Callable[..., dict]:
    """The organizer's OpenAI-compatible transport, under either layout."""
    try:
        from starter_kit.llm_client import chat_completion  # noqa: PLC0415
    except ModuleNotFoundError:  # extracted submission root has no outer package
        from llm_client import chat_completion  # type: ignore  # noqa: PLC0415
    return chat_completion


def _configuration_override() -> Callable[..., Any]:
    try:
        from starter_kit.llm_client import configuration_override  # noqa: PLC0415
    except ModuleNotFoundError:
        from llm_client import configuration_override  # type: ignore  # noqa: PLC0415
    return configuration_override


@contextmanager
def use_effective_config(cfg: RuntimeConfig | None = None) -> Iterator[None]:
    """Apply one resolved configuration to all model calls in this context."""
    target = cfg or get_runtime_config()
    resolved = target.resolve()
    if resolved is None:
        raise ValueError("模型配置不完整")
    with _configuration_override()(*resolved):
        yield


@contextmanager
def use_runtime_config_if_set() -> Iterator[None]:
    """Override only for a web-saved runtime value; preserve env contract."""
    cfg = get_runtime_config()
    if cfg.effective()["source"] != SOURCE_RUNTIME:
        yield
        return
    with use_effective_config(cfg):
        yield


def completion_for_config(cfg: RuntimeConfig | None = None) -> Callable[..., dict]:
    """Return a positional/keyword compatible, request-isolated completion."""
    completion = _chat_completion()

    def _configured_completion(*args: Any, **kwargs: Any) -> dict:
        with use_effective_config(cfg):
            return completion(*args, **kwargs)

    return _configured_completion


def _friendly_error(exc: BaseException) -> str:
    """Translate a transport/configuration error into a safe Chinese message.

    The raw exception (and any credential it might carry) is never surfaced.
    """
    text = str(exc)
    if "401" in text or "403" in text:
        return "API 密钥或地址不正确（服务返回 401/403）。请检查 Base URL 和 API Key。"
    if "429" in text:
        return "请求过于频繁（服务返回 429），请稍后再试。"
    if "unreachable" in text or "URLError" in text or "refused" in text or "timed out" in text:
        return "无法连接到模型服务。请确认 Base URL 可访问，且本机网络能到达该地址。"
    if "invalid JSON" in text:
        return "模型服务返回了无法解析的内容，请确认 Base URL 指向的是 OpenAI 兼容接口。"
    if "missing required" in text or "invalid" in text:
        return "模型配置不完整，请补全 Base URL、API Key 和模型名。"
    return "连接失败，请检查模型配置后重试。"


def test_connection(cfg: RuntimeConfig) -> dict[str, Any]:
    """Verify connectivity by sending one minimal request via ``chat_completion``.

    Never raises to the caller; failures come back as a friendly Chinese
    ``message``.  The resolved credentials are scoped to this request through
    the LLM client's context-local override and are never written to
    ``os.environ``.
    """
    resolved = cfg.resolve()
    if resolved is None:
        return {
            "ok": False,
            "message": "尚未配置模型服务。请在下方填写 Base URL、API Key 和模型名并保存，"
                       "或通过 LOOMQ_LLM_BASE_URL / LOOMQ_LLM_API_KEY / LOOMQ_LLM_MODEL 环境变量提供。",
            "latency_ms": None,
            "model": "",
        }
    base_url, api_key, model = resolved
    completion = completion_for_config(cfg)
    started = time.perf_counter()
    try:
        completion(
            [{"role": "user", "content": "请只回复两个字：正常"}],
            max_tokens=8,
        )
    except Exception as exc:  # noqa: BLE001 - surface a friendly message, not the traceback
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": False,
            "message": _friendly_error(exc),
            "latency_ms": latency_ms,
            "model": model,
        }
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "ok": True,
        "message": "API 连接正常",
        "latency_ms": latency_ms,
        "model": model,
    }
