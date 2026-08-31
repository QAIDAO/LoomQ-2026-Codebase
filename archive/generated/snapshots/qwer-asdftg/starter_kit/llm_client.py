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
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starter_kit.l2_errors import L2ApiError, L2ConfigurationError, L2TransportError, L2ValidationError


REQUIRED_ENV = ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")
_DEADLINE_EXHAUSTED = "l2_case_deadline_exhausted"


def _configuration() -> tuple[str, str, str, float, int]:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise L2ConfigurationError(
            "missing required LoomQ L2 environment variable(s): " + ", ".join(missing),
            variable_names=tuple(missing),
        )
    try:
        timeout = float(os.environ.get("LOOMQ_LLM_TIMEOUT_SECONDS", "120"))
        max_output = int(os.environ.get("LOOMQ_LLM_MAX_OUTPUT_TOKENS", "4096"))
    except ValueError as exc:
        raise L2ConfigurationError("invalid LoomQ L2 numeric environment variable") from exc
    if timeout <= 0 or max_output <= 0:
        raise L2ConfigurationError("LoomQ L2 timeout and output-token limit must be positive")
    base_url = os.environ["LOOMQ_LLM_BASE_URL"].rstrip("/")
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise L2ConfigurationError("LOOMQ_LLM_BASE_URL must be an absolute http(s) URL")
    return (
        base_url,
        os.environ["LOOMQ_LLM_API_KEY"],
        os.environ["LOOMQ_LLM_MODEL"],
        timeout,
        max_output,
    )


def _open_request(request: urllib.request.Request, timeout: float):
    """Open HTTP without eagerly constructing an unused TLS context."""
    scheme = urllib.parse.urlsplit(request.full_url).scheme.lower()
    if scheme == "http":
        opener = urllib.request.OpenerDirector()
        opener.add_handler(urllib.request.HTTPHandler())
        opener.add_handler(urllib.request.HTTPDefaultErrorHandler())
        opener.add_handler(urllib.request.HTTPErrorProcessor())
    elif scheme == "https":
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler())
    else:
        raise L2ConfigurationError("LOOMQ_LLM_BASE_URL must use http or https")
    return opener.open(request, timeout=timeout)


def _request_timeout(configured_timeout: float, requested_timeout: float | None) -> float:
    """Return a positive per-request timeout bounded by configuration."""
    if requested_timeout is None:
        return configured_timeout
    try:
        requested = float(requested_timeout)
    except (TypeError, ValueError) as exc:
        raise L2ConfigurationError("LoomQ L2 request timeout must be a positive number") from exc
    if not math.isfinite(requested) or requested <= 0:
        raise L2ConfigurationError("LoomQ L2 request timeout must be a positive number")
    return min(requested, configured_timeout)


def _timeout_before_open(
    configured_timeout: float,
    requested_timeout: float | None,
    deadline_monotonic: float | None,
) -> float:
    """Compute the transport timeout immediately before opening the connection."""
    timeout = _request_timeout(configured_timeout, requested_timeout)
    if deadline_monotonic is None:
        return timeout
    return min(timeout, _remaining_deadline(deadline_monotonic))


def _remaining_deadline(deadline_monotonic: float) -> float:
    """Return positive remaining wall-clock budget or the stable deadline category."""
    try:
        deadline = float(deadline_monotonic)
    except (TypeError, ValueError) as exc:
        raise L2ConfigurationError("LoomQ L2 request deadline must be a finite number") from exc
    if not math.isfinite(deadline):
        raise L2ConfigurationError("LoomQ L2 request deadline must be a finite number")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise L2ValidationError(_DEADLINE_EXHAUSTED)
    return remaining


def _read_response_before_deadline(
    request: urllib.request.Request,
    configured_timeout: float,
    requested_timeout: float | None,
    deadline_monotonic: float,
    host: str,
) -> dict[str, Any]:
    """Bound the whole HTTP open/read/parse lifecycle by an absolute deadline."""
    result: queue.Queue[tuple[bool, object, float | None]] = queue.Queue(maxsize=1)

    def fetch() -> None:
        timeout: float | None = None
        try:
            timeout = _timeout_before_open(
                configured_timeout, requested_timeout, deadline_monotonic
            )
            with _open_request(request, timeout) as response:
                payload = json.loads(response.read())
            _remaining_deadline(deadline_monotonic)
        except Exception as exc:
            result.put((False, exc, timeout))
        else:
            result.put((True, payload, timeout))

    worker = threading.Thread(target=fetch, daemon=True)
    worker.start()
    try:
        completed, value, effective_timeout = result.get(
            timeout=_remaining_deadline(deadline_monotonic)
        )
    except queue.Empty as exc:
        raise L2ValidationError(_DEADLINE_EXHAUSTED) from exc
    _remaining_deadline(deadline_monotonic)
    if completed:
        return value  # type: ignore[return-value]
    if isinstance(value, (urllib.error.URLError, TimeoutError, OSError)):
        if effective_timeout is None:
            effective_timeout = _request_timeout(configured_timeout, requested_timeout)
        raise L2TransportError(host, effective_timeout) from value
    raise value  # type: ignore[misc]


def chat_completion(
    messages: list[dict[str, Any]],
    *,
    timeout_seconds: float | None = None,
    deadline_monotonic: float | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Create one non-streaming chat completion using the public L2 contract."""
    base_url, api_key, model, configured_timeout, max_output = _configuration()
    host = urllib.parse.urlsplit(base_url).hostname or "unknown host"
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
        if deadline_monotonic is not None:
            return _read_response_before_deadline(
                request, configured_timeout, timeout_seconds, deadline_monotonic, host
            )
        timeout = _timeout_before_open(configured_timeout, timeout_seconds, None)
        with _open_request(request, timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        request_id = exc.headers.get("x-request-id") if exc.headers else None
        raise L2ApiError(exc.code, host, request_id) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise L2TransportError(host, timeout) from exc
