"""Local LLM configuration storage with browser-safe status reporting."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from ..run_l2 import (
        DEFAULT_ENV_FILE,
        PLACEHOLDER_VALUES,
        REQUIRED_ENVIRONMENT,
        read_env_file,
    )
except ImportError:
    from run_l2 import (  # type: ignore
        DEFAULT_ENV_FILE,
        PLACEHOLDER_VALUES,
        REQUIRED_ENVIRONMENT,
        read_env_file,
    )


CONFIGURATION_FIELDS = (
    {
        "name": "LOOMQ_LLM_BASE_URL",
        "label": "API 根地址",
        "description": "OpenAI-compatible API 根地址",
        "default": "https://api.deepseek.com",
        "secret": False,
    },
    {
        "name": "LOOMQ_LLM_API_KEY",
        "label": "API Key",
        "description": "当前运行凭证，仅保存在本机",
        "default": "",
        "secret": True,
    },
    {
        "name": "LOOMQ_LLM_MODEL",
        "label": "模型",
        "description": "正式评测使用 deepseek-v4-flash",
        "default": "deepseek-v4-flash",
        "secret": False,
    },
    {
        "name": "LOOMQ_LLM_TIMEOUT_SECONDS",
        "label": "请求超时",
        "description": "单次请求最长等待秒数",
        "default": "120",
        "secret": False,
    },
)


class ConfigurationService:
    """Read, validate, and persist the local OpenAI-compatible endpoint config."""

    def __init__(self, env_file: Path = DEFAULT_ENV_FILE):
        self.env_file = Path(env_file)

    def status(self) -> Dict[str, Any]:
        """Return readiness details without ever exposing secret field values."""
        file_values, file_error = self._read_file_safely()
        effective = {
            field["name"]: os.environ.get(field["name"], file_values.get(field["name"], ""))
            for field in CONFIGURATION_FIELDS
        }
        valid_by_name = self._validity(effective)
        fields = []
        for definition in CONFIGURATION_FIELDS:
            name = definition["name"]
            field = dict(definition)
            field["configured"] = valid_by_name[name]
            field["value"] = "" if definition["secret"] else effective.get(name, "")
            field["source"] = (
                "environment"
                if os.environ.get(name)
                else "file"
                if file_values.get(name)
                else "default"
            )
            fields.append(field)
        return {
            "ready": all(valid_by_name[name] for name in REQUIRED_ENVIRONMENT)
            and valid_by_name["LOOMQ_LLM_TIMEOUT_SECONDS"],
            "fields": fields,
            "file_error": file_error,
        }

    def save(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        allowed = {field["name"] for field in CONFIGURATION_FIELDS}
        if set(payload) - allowed:
            raise ValueError("unsupported configuration field")
        current_by_name = {field["name"]: field for field in self.status()["fields"]}
        values: Dict[str, str] = {}
        for definition in CONFIGURATION_FIELDS:
            name = definition["name"]
            value = payload.get(name, "")
            if not isinstance(value, str):
                raise ValueError("configuration values must be strings")
            value = value.strip()
            if "\n" in value or "\r" in value:
                raise ValueError("configuration values cannot contain line breaks")
            if definition["secret"] and not value and current_by_name[name]["configured"]:
                value = self._existing_secret(name)
            values[name] = value or str(definition["default"])
        self._validate(values)
        self._write(values)
        for name, value in values.items():
            os.environ[name] = value
        return self.status()

    def _read_file_safely(self) -> tuple[Dict[str, str], Optional[str]]:
        if not self.env_file.exists():
            return {}, None
        try:
            return read_env_file(self.env_file), None
        except RuntimeError as exc:
            return {}, str(exc)

    def _existing_secret(self, name: str) -> str:
        value = os.environ.get(name, "")
        if value or not self.env_file.exists():
            return value
        return read_env_file(self.env_file).get(name, "")

    @staticmethod
    def _validity(values: Dict[str, str]) -> Dict[str, bool]:
        key = values.get("LOOMQ_LLM_API_KEY", "").strip()
        key_valid = (
            bool(key)
            and key.lower() not in PLACEHOLDER_VALUES
            and not key.startswith("<")
        )
        return {
            "LOOMQ_LLM_BASE_URL": bool(values.get("LOOMQ_LLM_BASE_URL", "").strip()),
            "LOOMQ_LLM_API_KEY": key_valid,
            "LOOMQ_LLM_MODEL": bool(values.get("LOOMQ_LLM_MODEL", "").strip()),
            "LOOMQ_LLM_TIMEOUT_SECONDS": ConfigurationService._valid_timeout(
                values.get("LOOMQ_LLM_TIMEOUT_SECONDS", "120")
            ),
        }

    @staticmethod
    def _validate(values: Dict[str, str]) -> None:
        if not values["LOOMQ_LLM_BASE_URL"].startswith(("http://", "https://")):
            raise ValueError("API 根地址必须以 http:// 或 https:// 开头")
        if not values["LOOMQ_LLM_MODEL"]:
            raise ValueError("模型不能为空")
        key = values["LOOMQ_LLM_API_KEY"]
        if not key or key.lower() in PLACEHOLDER_VALUES or key.startswith("<"):
            raise ValueError("请填写有效的 API Key")
        if not ConfigurationService._valid_timeout(
            values["LOOMQ_LLM_TIMEOUT_SECONDS"]
        ):
            raise ValueError("请求超时必须是大于 0 的数字")

    def _write(self, values: Dict[str, str]) -> None:
        max_output = os.environ.get("LOOMQ_LLM_MAX_OUTPUT_TOKENS", "4096")
        if self.env_file.exists():
            try:
                max_output = read_env_file(self.env_file).get(
                    "LOOMQ_LLM_MAX_OUTPUT_TOKENS", max_output
                )
            except RuntimeError:
                pass
        lines = ["# LoomQ local L2 configuration. This file is ignored by Git."]
        lines.extend(
            "%s=%s" % (field["name"], values[field["name"]])
            for field in CONFIGURATION_FIELDS
        )
        lines.append("LOOMQ_LLM_MAX_OUTPUT_TOKENS=%s" % max_output)
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        self.env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            self.env_file.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def _valid_timeout(value: str) -> bool:
        try:
            return 0 < float(value) <= 3600
        except (TypeError, ValueError):
            return False
