"""Deterministic guardrails around the organizer-provided L2 model call."""

from __future__ import annotations

import json
import inspect
import re
import time
from pathlib import Path
from typing import Any, Tuple

try:
    from . import llm_client
    from .l2_errors import L2Error, L2ValidationError
    from .l2_semantics import validate_prompt_reply
    from .loomq_l1.parser import parse_qasm
except ImportError:
    import llm_client
    from l2_errors import L2Error, L2ValidationError
    from l2_semantics import validate_prompt_reply
    from loomq_l1.parser import parse_qasm


_QASM_PATTERN = re.compile(r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", re.DOTALL | re.MULTILINE)
_STRUCTURED_REQUEST_PATTERN = re.compile(
    r"\b(?:qasm|openqasm|circuit|backend|platform|device|simulator)\b|"
    r"电路|后端|平台|设备|模拟器|真机",
    re.IGNORECASE,
)


CASE_TIMEOUT_SECONDS = 120.0
_DEADLINE_EXHAUSTED = "l2_case_deadline_exhausted"


def _supports_deadline_argument(callable_: object) -> bool:
    """Detect keyword support without turning client TypeErrors into fallback calls."""
    try:
        parameters = inspect.signature(callable_).parameters.values()
    except (TypeError, ValueError):
        return True
    return any(
        parameter.name == "deadline_monotonic"
        or parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


def _request(
    messages: list[dict[str, str]], *, deadline_monotonic: float | None = None
) -> dict[str, Any]:
    """Request through the current client attribute so runtime patches apply."""
    client = llm_client.chat_completion
    if deadline_monotonic is not None and _supports_deadline_argument(client):
        return client(messages, deadline_monotonic=deadline_monotonic)
    return client(messages)


def _load_backend_capabilities() -> tuple[dict[str, Any], ...]:
    path = Path(__file__).with_name("backend_capabilities.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        backends = payload["backends"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("LoomQ backend capability table is unavailable") from exc
    if not isinstance(backends, list) or not all(
        isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
        for item in backends
    ):
        raise RuntimeError("LoomQ backend capability table is invalid")
    return tuple(backends)


def _system_prompt(backends: tuple[dict[str, Any], ...]) -> str:
    snapshot = json.dumps({"backends": backends}, ensure_ascii=False, separators=(",", ":"))
    return (
        "You are the LoomQ competition quantum assistant. Follow the user's request. "
        "For quantum-program generation or repair, return a complete parseable OpenQASM 2.0 "
        "program with qelib1.inc, registers, and measurements. For backend selection, choose only "
        "a canonical backend id from the capability table below and include that exact id. Do not "
        "invent ids. Keep the answer concise. Capability table: "
        + snapshot
    )


def _completion_content(response: Any) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise L2ValidationError("model returned an invalid completion payload") from exc
    if not isinstance(content, str) or not content.strip():
        raise L2ValidationError("model returned an empty completion")
    return content.strip()


def _valid_reply(text: str, backend_ids: tuple[str, ...]) -> Tuple[bool, str]:
    match = _QASM_PATTERN.search(text)
    if match is not None:
        try:
            parse_qasm(match.group(0).strip())
        except Exception:
            return False, "structured_reply_invalid"
        return True, ""

    for backend_id in backend_ids:
        if re.search(r"(?<![A-Za-z0-9_])" + re.escape(backend_id) + r"(?![A-Za-z0-9_])", text):
            return True, ""
    return False, "structured_reply_required"


def _ensure_case_budget(deadline: float) -> None:
    if deadline - time.monotonic() <= 0:
        raise L2ValidationError(_DEADLINE_EXHAUSTED)


def _request_completion(messages: list[dict[str, str]], deadline: float) -> str:
    try:
        _ensure_case_budget(deadline)
        return _completion_content(
            _request(messages, deadline_monotonic=deadline)
        )
    except L2Error:
        raise
    except Exception as exc:
        raise L2ValidationError("model request failed") from exc


def _validation_category(prompt: str, reply: str, backend_ids: tuple[str, ...]) -> str | None:
    try:
        semantic_reason = validate_prompt_reply(prompt, reply)
    except Exception:
        return "semantic_validation_unavailable"
    if semantic_reason is not None:
        return "semantic_requirement_not_met"

    valid, shape_category = _valid_reply(reply, backend_ids)
    if valid or not _STRUCTURED_REQUEST_PATTERN.search(prompt):
        return None
    return shape_category


def _repair_message(prompt: str, category: str) -> str:
    return (
        "The previous answer did not meet the required response contract "
        f"(category: {category}). Original user request: {prompt}"
    )


def agent_chat(prompt: str) -> str:
    """Make an L2 model call and enforce the competition's result contract."""
    if type(prompt) is not str:
        raise TypeError("prompt must be a string")
    deadline = time.monotonic() + CASE_TIMEOUT_SECONDS
    backends = _load_backend_capabilities()
    backend_ids = tuple(item["id"] for item in backends)
    messages = [
        {"role": "system", "content": _system_prompt(backends)},
        {"role": "user", "content": prompt},
    ]
    reply = _request_completion(messages, deadline)
    category = _validation_category(prompt, reply, backend_ids)
    if category is None:
        return reply

    repair_messages = messages + [
        {
            "role": "user",
            "content": _repair_message(prompt, category),
        },
    ]
    repaired = _request_completion(repair_messages, deadline)
    repair_category = _validation_category(prompt, repaired, backend_ids)
    if repair_category is None:
        return repaired
    raise L2ValidationError(
        "model response did not satisfy the requested requirement after one repair attempt"
    )


__all__ = ["agent_chat"]
