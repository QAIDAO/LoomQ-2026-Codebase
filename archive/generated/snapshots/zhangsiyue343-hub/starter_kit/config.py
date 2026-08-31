#!/usr/bin/env python3
"""Configuration-as-code: every external dependency enters the system here.

Sources merge in priority order: built-in defaults < YAML file < environment
variables. The resulting LoomqConfig is a frozen dataclass that the DI
container hands to whoever needs it — no module reads os.environ directly,
which keeps evaluation-injected settings testable and explicit.

YAML support uses a deliberately tiny subset loader (nested maps, scalars,
inline comments) so we stay on the standard library.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class LlmConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: float = 120.0
    max_output_tokens: int = 4096
    repair_rounds: int = 2
    verification_shots: int = 2048
    fidelity_threshold: float = 0.97

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


@dataclass(frozen=True)
class EngineConfig:
    default_shots: int = 8192
    max_qubits_internal: int = 26
    concurrency: int = 4
    deterministic_sampling: bool = False     # seed sampling in tests only
    sampling_seed: int = 20260825


@dataclass(frozen=True)
class PluginConfig:
    directory: str = ""                      # empty -> packaged plugins/
    disabled: tuple[str, ...] = ()

    def is_enabled(self, target_id: str) -> bool:
        return target_id not in self.disabled


@dataclass(frozen=True)
class BackendsConfig:
    """Real-hardware credentials — always injected via environment variables,
    never hardcoded and never committed (same policy as the LLM settings).

    LOOMQ_SPINQ_TOKEN          SpinQ cloud / Taurus superconducting QPU token
    LOOMQ_ORIGINQ_TOKEN        OriginQ cloud / Wukong 72-qubit QPU token
    AWS_ACCESS_KEY_ID etc.     standard boto3 names, read natively by braket
    LOOMQ_PREFER_REAL_MACHINE  when truthy and a credential exists, plugins
                               attempt the cloud device first; failures are
                               reported honestly instead of silently falling
                               back to simulation.
    """

    spinq_token: str = ""
    originq_token: str = ""
    aws_region: str = ""
    prefer_real_machine: bool = False

    def configured_backends(self) -> tuple[str, ...]:
        names = []
        if self.spinq_token:
            names.append("spinq")
        if self.originq_token:
            names.append("originq")
        if self.aws_region:
            names.append("braket")
        return tuple(names)


@dataclass(frozen=True)
class LoomqConfig:
    llm: LlmConfig = field(default_factory=LlmConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)
    backends: BackendsConfig = field(default_factory=BackendsConfig)

    @classmethod
    def load(cls, env: Optional[Mapping[str, str]] = None,
             config_path: Optional[str] = None) -> "LoomqConfig":
        environ = dict(os.environ if env is None else env)
        if env is None:
            _merge_dotenv(environ)
        overrides: dict[str, Any] = {}
        path = config_path or environ.get("LOOMQ_CONFIG", "")
        if path and os.path.isfile(path):
            overrides = _read_simple_yaml(path)
        base: LoomqConfig = cls()
        base = _apply_mapping(base, overrides)
        return _apply_env(base, environ)


# --------------------------------------------------------------------------
# merge helpers (pure functions: mapping -> config -> config)
# --------------------------------------------------------------------------

_SECTIONS = {"llm": LlmConfig, "engine": EngineConfig,
             "plugins": PluginConfig, "backends": BackendsConfig}


def _coerce(section: str, values: Mapping[str, Any]) -> dict[str, Any]:
    if section != "llm":
        return dict(values)
    return {key: value for key, value in values.items()
            if key.lower() in LlmConfig.__dataclass_fields__}


def _apply_mapping(config: LoomqConfig, overrides: Mapping[str, Any]) -> LoomqConfig:
    updates: dict[str, Any] = {}
    for section_name, section_type in _SECTIONS.items():
        section_values = overrides.get(section_name)
        if isinstance(section_values, Mapping):
            current = getattr(config, section_name)
            coerced = _coerce(section_name, section_values)
            fields = {name: getattr(current, name) for name in current.__dataclass_fields__}
            for key, value in coerced.items():
                if key in fields:
                    fields[key] = value
            updates[section_name] = section_type(**fields)
    if overrides.get("plugins_directory") and "plugins" not in updates:
        fields = {name: getattr(config.plugins, name) for name in config.plugins.__dataclass_fields__}
        fields["directory"] = str(overrides["plugins_directory"])
        updates["plugins"] = PluginConfig(**fields)
    return replace(config, **updates) if updates else config


def _apply_env(config: LoomqConfig, environ: Mapping[str, str]) -> LoomqConfig:
    llm_updates = {
        "base_url": environ.get("LOOMQ_LLM_BASE_URL", config.llm.base_url),
        "api_key": environ.get("LOOMQ_LLM_API_KEY", config.llm.api_key),
        "model": environ.get("LOOMQ_LLM_MODEL", config.llm.model),
    }
    for env_name, attr in (
        ("LOOMQ_LLM_TIMEOUT_SECONDS", "timeout_seconds"),
        ("LOOMQ_LLM_MAX_OUTPUT_TOKENS", "max_output_tokens"),
        ("LOOMQ_LLM_REPAIR_ROUNDS", "repair_rounds"),
        ("LOOMQ_LLM_VERIFICATION_SHOTS", "verification_shots"),
    ):
        if environ.get(env_name):
            try:
                llm_updates[attr] = float(environ[env_name]) if "TIMEOUT" in env_name \
                    else int(environ[env_name])
            except ValueError:
                pass
    engine_updates = {
        "default_shots": _env_int(environ, "LOOMQ_DEFAULT_SHOTS", config.engine.default_shots),
        "concurrency": _env_int(environ, "LOOMQ_CONCURRENCY", config.engine.concurrency),
        "deterministic_sampling": environ.get("LOOMQ_DETERMINISTIC_SAMPLING", "") in
                                  ("1", "true", "yes", "on"),
    }
    disabled = tuple(t.strip() for t in environ.get("LOOMQ_DISABLED_TARGETS", "").split(",") if t.strip())
    plugin_updates = {"disabled": disabled or config.plugins.disabled}
    if environ.get("LOOMQ_PLUGIN_DIR"):
        plugin_updates["directory"] = environ["LOOMQ_PLUGIN_DIR"]
    backends_updates = {
        "spinq_token": environ.get("LOOMQ_SPINQ_TOKEN", config.backends.spinq_token),
        "originq_token": environ.get("LOOMQ_ORIGINQ_TOKEN", config.backends.originq_token),
        "aws_region": environ.get("AWS_REGION",
                       environ.get("AWS_DEFAULT_REGION", config.backends.aws_region)),
        "prefer_real_machine": environ.get("LOOMQ_PREFER_REAL_MACHINE", "") in
                               ("1", "true", "yes", "on"),
    }
    return replace(
        config,
        llm=LlmConfig(**{**{f: getattr(config.llm, f) for f in config.llm.__dataclass_fields__},
                         **{k: v for k, v in llm_updates.items() if v}}),
        engine=EngineConfig(**{**{f: getattr(config.engine, f) for f in config.engine.__dataclass_fields__},
                               **engine_updates}),
        plugins=PluginConfig(**{**{f: getattr(config.plugins, f) for f in config.plugins.__dataclass_fields__},
                                **plugin_updates}),
        backends=BackendsConfig(**{**{f: getattr(config.backends, f)
                                      for f in config.backends.__dataclass_fields__},
                                   **backends_updates}),
    )


def _env_int(environ: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(environ[name]) if environ.get(name) else default
    except ValueError:
        return default


def _merge_dotenv(environ: dict[str, str]) -> None:
    """Load a local .env (fork root or cwd) into `environ` without ever
    overriding variables that are already set. Values stay in memory only —
    .env is gitignored and is never echoed by describe()."""
    for directory in (os.getcwd(), os.path.dirname(os.getcwd())):
        path = os.path.join(directory, ".env")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8-sig") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in environ:
                        environ[key] = value
        except OSError:
            pass
        return


# --------------------------------------------------------------------------
# minimal YAML subset (maps / scalars / comments) — stdlib only
# --------------------------------------------------------------------------

def _read_simple_yaml(path: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.split("#", 1)[0].rstrip() if not raw_line.lstrip().startswith("#") else ""
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip(" "))
            content = line.strip()
            if ":" not in content:
                continue
            key, _, value_text = content.partition(":")
            key, value_text = key.strip(), value_text.strip()
            while stack and indent <= stack[-1][0]:
                stack.pop()
            parent = stack[-1][1]
            if value_text == "":
                child: dict[str, Any] = {}
                parent[key] = child
                stack.append((indent, child))
            else:
                parent[key] = _scalar(value_text)
    return root


def _scalar(text: str) -> Any:
    text = text.strip().strip('"').strip("'")
    lowered = text.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if lowered in ("null", "~", ""):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def describe(config: LoomqConfig) -> str:
    """Redacted one-line summary safe to print anywhere."""
    llm_state = "configured(%s)" % config.llm.model if config.llm.configured else "absent"
    return json.dumps({
        "llm": llm_state,
        "engine": {"shots": config.engine.default_shots,
                   "concurrency": config.engine.concurrency},
        "plugins_disabled": list(config.plugins.disabled),
        "real_machine_credentials": {
            name: "configured" for name in config.backends.configured_backends()
        } or "none",
    }, ensure_ascii=False)
