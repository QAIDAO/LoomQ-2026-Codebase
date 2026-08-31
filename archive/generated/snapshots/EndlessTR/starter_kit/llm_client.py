#!/usr/bin/env python3
"""Small OpenAI-compatible transport helper for LoomQ L2 entrants.

This module deliberately contains no prompting strategy or scoring logic. Teams
may use it, replace it, or call the same environment-variable contract from any
language.
"""

from __future__ import annotations

import json
import math
import os
from contextlib import contextmanager
from contextvars import ContextVar
import urllib.error
import urllib.request
from typing import Any, Iterator


REQUIRED_ENV = ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")

# Web requests may use a configuration saved in the running QuantumHelper
# process.  A ContextVar keeps that override local to the current request/thread;
# mutating os.environ around a network call would let concurrent requests see
# one another's credentials.
_CONFIGURATION_OVERRIDE: ContextVar[tuple[str, str, str] | None] = ContextVar(
    "loomq_llm_configuration_override", default=None
)


class LoomQLLMConfigurationError(RuntimeError):
    """Raised when the organizer-provided L2 runtime configuration is invalid."""


class LoomQLLMTransportError(RuntimeError):
    """Raised when an OpenAI-compatible L2 request cannot be completed."""


@contextmanager
def configuration_override(
    base_url: str, api_key: str, model: str
) -> Iterator[None]:
    """Temporarily override the required triple in the current call context.

    This is intentionally process-memory only.  It is used by the web layer and
    does not change the organizer-provided environment-variable contract.
    """
    if not all(isinstance(value, str) and value for value in (base_url, api_key, model)):
        raise LoomQLLMConfigurationError("invalid LoomQ L2 configuration override")
    token = _CONFIGURATION_OVERRIDE.set((base_url.rstrip("/"), api_key, model))
    try:
        yield
    finally:
        _CONFIGURATION_OVERRIDE.reset(token)


def _configuration() -> tuple[str, str, str, float, int]:
    override = _CONFIGURATION_OVERRIDE.get()
    if override is None:
        missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
        if missing:
            raise LoomQLLMConfigurationError(
                "missing required LoomQ L2 environment variable(s): " + ", ".join(missing)
            )
        base_url, api_key, model = (os.environ[name] for name in REQUIRED_ENV)
    else:
        base_url, api_key, model = override
    try:
        timeout = float(os.environ.get("LOOMQ_LLM_TIMEOUT_SECONDS", "120"))
        max_output = int(os.environ.get("LOOMQ_LLM_MAX_OUTPUT_TOKENS", "4096"))
    except ValueError as exc:
        raise LoomQLLMConfigurationError("invalid LoomQ L2 numeric environment variable") from exc
    if timeout <= 0 or max_output <= 0:
        raise LoomQLLMConfigurationError(
            "LoomQ L2 timeout and output-token limit must be positive"
        )
    return (
        base_url.rstrip("/"),
        api_key,
        model,
        timeout,
        max_output,
    )


def chat_completion(messages: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    """Create one non-streaming chat completion using the public L2 contract."""
    base_url, api_key, model, timeout, max_output = _configuration()
    # Internal transport control: callers may share one case-level deadline
    # across multiple attempts.  Pop it before building the API payload so it
    # is never sent to the OpenAI-compatible endpoint.
    request_timeout = extra.pop("_request_timeout_seconds", None)
    if request_timeout is not None:
        try:
            request_timeout = float(request_timeout)
        except (TypeError, ValueError) as exc:
            raise LoomQLLMConfigurationError("invalid L2 request timeout") from exc
        if not math.isfinite(request_timeout) or request_timeout <= 0:
            raise LoomQLLMConfigurationError("L2 request timeout must be positive and finite")
        timeout = min(timeout, request_timeout)
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": 0,
        "max_tokens": max_output,
    }
    if model == "deepseek-v4-flash":
        payload["thinking"] = {"type": "disabled"}
    payload.update(extra)
    request = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            try:
                return json.loads(response.read())
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LoomQLLMTransportError("LoomQ L2 API returned invalid JSON") from exc
    except urllib.error.HTTPError as exc:
        raise LoomQLLMTransportError("LoomQ L2 API returned HTTP %d" % exc.code) from exc
    except urllib.error.URLError as exc:
        raise LoomQLLMTransportError("LoomQ L2 API is unreachable") from exc
