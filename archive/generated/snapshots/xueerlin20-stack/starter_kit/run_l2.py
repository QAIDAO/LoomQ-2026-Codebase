#!/usr/bin/env python3
"""Load local L2 configuration and invoke adapter.agent_chat conveniently."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Dict

try:
    from .adapter import agent_chat
except ImportError:
    from adapter import agent_chat


DEFAULT_ENV_FILE = Path(__file__).resolve().with_name(".env.l2")
ALLOWED_ENVIRONMENT = frozenset(
    {
        "LOOMQ_LLM_BASE_URL",
        "LOOMQ_LLM_API_KEY",
        "LOOMQ_LLM_MODEL",
        "LOOMQ_LLM_TIMEOUT_SECONDS",
        "LOOMQ_LLM_MAX_OUTPUT_TOKENS",
    }
)
REQUIRED_ENVIRONMENT = (
    "LOOMQ_LLM_BASE_URL",
    "LOOMQ_LLM_API_KEY",
    "LOOMQ_LLM_MODEL",
)
PLACEHOLDER_VALUES = frozenset(
    {"placeholder", "placeholder-key", "your-key", "<your_own_key>"}
)


def reexec_with_bundled_venv_if_needed() -> None:
    """Use starter_kit/.venv automatically when system Python lacks SpinQit."""
    if importlib.util.find_spec("spinqit") is not None:
        return
    if os.name == "nt":
        bundled_python = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
    else:
        bundled_python = Path(__file__).resolve().parent / ".venv" / "bin" / "python"
    if not bundled_python.is_file():
        return
    try:
        if bundled_python.resolve() == Path(sys.executable).resolve():
            return
    except OSError:
        pass
    os.execv(
        str(bundled_python),
        # Preserve the program the user actually launched. This helper is also
        # reused by web_app.py; hard-coding run_l2.py here silently turned a web
        # launch into the CLI after switching interpreters.
        [str(bundled_python), str(Path(sys.argv[0]).resolve()), *sys.argv[1:]],
    )


def read_env_file(path: Path) -> Dict[str, str]:
    """Read a small KEY=VALUE file without executing it as shell code."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(
            "L2 配置文件不存在：%s；请复制 .env.l2.example 为 .env.l2" % path
        ) from exc

    values: Dict[str, str] = {}
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RuntimeError("L2 配置文件第 %d 行不是 KEY=VALUE" % line_number)
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in ALLOWED_ENVIRONMENT:
            raise RuntimeError("L2 配置文件包含不支持的字段：%s" % key)
        if not value:
            raise RuntimeError("L2 配置字段不能为空：%s" % key)
        values[key] = value
    return values


def load_environment(path: Path = DEFAULT_ENV_FILE) -> Dict[str, str]:
    """Load local values, preserving variables already set by the caller."""
    file_values = read_env_file(path)
    for key, value in file_values.items():
        os.environ.setdefault(key, value)

    missing = [key for key in REQUIRED_ENVIRONMENT if not os.environ.get(key)]
    if missing:
        raise RuntimeError("缺少 L2 配置：" + ", ".join(missing))
    return {key: os.environ[key] for key in ALLOWED_ENVIRONMENT if key in os.environ}


def validate_ready(configuration: Dict[str, str]) -> None:
    key = configuration["LOOMQ_LLM_API_KEY"].strip().lower()
    if key in PLACEHOLDER_VALUES or key.startswith("<"):
        raise RuntimeError(
            "LOOMQ_LLM_API_KEY 仍是 placeholder；请编辑 starter_kit/.env.l2 填入自己的 Key"
        )


def configuration_summary(configuration: Dict[str, str]) -> str:
    return "\n".join(
        [
            "LoomQ L2 配置已加载：",
            "  Base URL: %s" % configuration["LOOMQ_LLM_BASE_URL"],
            "  Model: %s" % configuration["LOOMQ_LLM_MODEL"],
            "  Timeout: %s 秒"
            % configuration.get("LOOMQ_LLM_TIMEOUT_SECONDS", "120"),
            "  Max output: %s tokens"
            % configuration.get("LOOMQ_LLM_MAX_OUTPUT_TOKENS", "4096"),
            "  API Key: 已设置（不会显示）",
        ]
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run LoomQ L2 Agent locally")
    parser.add_argument("prompt", nargs="*", help="natural-language Agent request")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="local environment file (default: starter_kit/.env.l2)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate and show configuration without calling the model",
    )
    args = parser.parse_args(argv)

    configuration = load_environment(args.env_file)
    validate_ready(configuration)
    if args.check:
        print(configuration_summary(configuration))
        return 0

    prompt = " ".join(args.prompt).strip()
    if not prompt:
        prompt = input("请输入你的量子计算需求：").strip()
    if not prompt:
        parser.error("prompt cannot be empty")

    print(agent_chat(prompt))
    return 0


if __name__ == "__main__":
    reexec_with_bundled_venv_if_needed()
    sys.exit(main())
