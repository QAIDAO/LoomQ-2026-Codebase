#!/usr/bin/env python3
"""Small OpenAI-compatible transport helper for LoomQ L2 entrants.

This module deliberately contains no prompting strategy or scoring logic. Teams
may use it, replace it, or call the same environment-variable contract from any
language.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


REQUIRED_ENV = ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")
MAX_RESPONSE_BYTES = 1_048_576
DEFAULT_MAX_OUTPUT_TOKENS = 900
MAX_OUTPUT_TOKENS = 1_000


class SuccessfulHTTPResponseError(RuntimeError):
    """The API returned a successful HTTP response with an unusable body."""


def output_token_limit() -> int:
    try:
        max_output = int(os.environ.get(
            "LOOMQ_LLM_MAX_OUTPUT_TOKENS", str(DEFAULT_MAX_OUTPUT_TOKENS)
        ))
    except ValueError as exc:
        raise RuntimeError("invalid LoomQ L2 numeric environment variable") from exc
    if max_output <= 0:
        raise RuntimeError("LoomQ L2 timeout and output-token limit must be positive")
    if max_output > MAX_OUTPUT_TOKENS:
        raise RuntimeError(
            "LoomQ L2 output-token limit must not exceed %d" % MAX_OUTPUT_TOKENS
        )
    return max_output


def _configuration() -> tuple[str, str, str, float, int]:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError("missing required LoomQ L2 environment variable(s): " + ", ".join(missing))
    try:
        timeout = float(os.environ.get("LOOMQ_LLM_TIMEOUT_SECONDS", "120"))
    except ValueError as exc:
        raise RuntimeError("invalid LoomQ L2 numeric environment variable") from exc
    max_output = output_token_limit()
    if timeout <= 0 or max_output <= 0:
        raise RuntimeError("LoomQ L2 timeout and output-token limit must be positive")
    return (
        os.environ["LOOMQ_LLM_BASE_URL"].rstrip("/"),
        os.environ["LOOMQ_LLM_API_KEY"],
        os.environ["LOOMQ_LLM_MODEL"],
        timeout,
        max_output,
    )


def chat_completion(
    messages: list[dict[str, Any]], *, transport_timeout: float | None = None,
    request_max_tokens: int | None = None,
    **extra: Any
) -> dict[str, Any]:
    """Create one non-streaming chat completion using the public L2 contract."""
    base_url, api_key, model, timeout, max_output = _configuration()
    if transport_timeout is not None:
        if not isinstance(transport_timeout, (int, float)) or transport_timeout <= 0:
            raise ValueError("transport_timeout must be positive")
        timeout = min(timeout, float(transport_timeout))
    if request_max_tokens is not None:
        if (type(request_max_tokens) is not int or request_max_tokens <= 0 or
                request_max_tokens > max_output):
            raise ValueError(
                "request_max_tokens must be positive and not exceed the configured limit"
            )
        max_output = request_max_tokens
    reserved = {"model", "messages", "stream", "temperature", "thinking", "max_tokens"}
    if reserved.intersection(extra):
        raise ValueError("formal LoomQ L2 request fields cannot be overridden")
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
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise SuccessfulHTTPResponseError(
                    "LoomQ L2 API response exceeds size limit"
                )
            try:
                value = json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
                raise SuccessfulHTTPResponseError(
                    "LoomQ L2 API returned invalid JSON"
                ) from exc
            if not isinstance(value, dict):
                raise SuccessfulHTTPResponseError(
                    "LoomQ L2 API returned invalid JSON"
                )
            return value
    except urllib.error.HTTPError as exc:
        raise RuntimeError("LoomQ L2 API returned HTTP %d" % exc.code) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("LoomQ L2 API is unreachable") from exc
