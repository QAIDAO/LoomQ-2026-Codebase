"""Local-only provider shortcuts for the OpenAI-compatible LoomQ L2 CLI."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Mapping

from starter_kit.l2_errors import L2ConfigurationError


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    base_url: str | None
    default_model: str | None
    key_environment: str


PROFILES: dict[str, ProviderProfile] = {
    "bailian-token-plan": ProviderProfile(
        "bailian-token-plan",
        "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "qwen3.8-max",
        "DASHSCOPE_API_KEY",
    ),
    "dashscope": ProviderProfile(
        "dashscope",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen-plus",
        "DASHSCOPE_API_KEY",
    ),
    "openai": ProviderProfile("openai", "https://api.openai.com/v1", None, "OPENAI_API_KEY"),
    "deepseek": ProviderProfile("deepseek", "https://api.deepseek.com/v1", None, "DEEPSEEK_API_KEY"),
    "custom": ProviderProfile("custom", None, None, "LOOMQ_LLM_API_KEY"),
}


def provider_names() -> tuple[str, ...]:
    return tuple(PROFILES)


def local_settings(
    provider: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
) -> dict[str, str]:
    """Build temporary formal-contract variables for one explicit local profile."""
    try:
        profile = PROFILES[provider]
    except KeyError as exc:
        raise L2ConfigurationError(
            "unknown local provider profile: " + provider,
            variable_names=("--provider",),
        ) from exc

    settings: dict[str, str] = {}
    effective_base_url = base_url or profile.base_url
    effective_model = model or profile.default_model
    api_key = os.environ.get(profile.key_environment)
    if not api_key:
        raise L2ConfigurationError(
            "missing API key for local provider profile: " + profile.name,
            variable_names=(profile.key_environment,),
        )
    if not effective_base_url:
        raise L2ConfigurationError(
            "local provider profile requires an endpoint override",
            variable_names=("--base-url",),
        )
    if not effective_model:
        raise L2ConfigurationError(
            "local provider profile requires a model id",
            variable_names=("--model",),
        )
    settings["LOOMQ_LLM_BASE_URL"] = effective_base_url
    settings["LOOMQ_LLM_MODEL"] = effective_model
    settings["LOOMQ_LLM_API_KEY"] = api_key
    return settings


@contextmanager
def temporary_environment(settings: Mapping[str, str]) -> Iterator[None]:
    """Temporarily inject local settings without persisting keys or endpoints."""
    original = {name: os.environ.get(name) for name in settings}
    try:
        os.environ.update(settings)
        yield
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
