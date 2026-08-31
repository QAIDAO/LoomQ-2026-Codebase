"""Structured, UI-independent debug trace events for LoomQ."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import re
from typing import Any, Mapping


_LAYERS = {"agent", "circuit"}
_EXECUTORS = {"llm", "local"}
_STATUSES = {"running", "ok", "warning", "error"}
_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_)])(?:[A-Za-z]:\\|/)[^\s\"')]+"
)
_BEARER_RE = re.compile(r"(?i)(?:authorization\s*:\s*)?bearer\s+\S+")
_ENVIRONMENT_NAME_RE = re.compile(r"\bLOOMQ_[A-Z0-9_]+\b")


def _safe_text(value: str) -> str:
    """Remove credential and host-path details before an event is retained."""
    api_key = os.environ.get("LOOMQ_LLM_API_KEY")
    if api_key:
        value = value.replace(api_key, "<credential>")
    value = _BEARER_RE.sub("<credential>", value)
    value = value.replace(".env.l2.local", "<local-env-file>")
    value = _ENVIRONMENT_NAME_RE.sub("<environment-variable>", value)
    return _ABSOLUTE_PATH_RE.sub("<path>", value)


def _safe_value(value: Any) -> Any:
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, Mapping):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _safe_text(str(value))


@dataclass(frozen=True)
class TraceEvent:
    """One stable event consumable by either the thin CLI or a future Web UI."""

    seq: int
    layer: str
    stage: str
    executor: str
    status: str
    summary: str
    data: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class TraceRecorder:
    """Assign sequence numbers and retain sanitized trace events in memory."""

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

    def emit(
        self,
        *,
        layer: str,
        stage: str,
        executor: str,
        status: str,
        summary: str,
        data: Mapping[str, Any] | None = None,
    ) -> TraceEvent:
        if layer not in _LAYERS:
            raise ValueError("trace layer must be agent or circuit")
        if executor not in _EXECUTORS:
            raise ValueError("trace executor must be llm or local")
        if status not in _STATUSES:
            raise ValueError("trace status is invalid")
        if not isinstance(stage, str) or not stage:
            raise ValueError("trace stage must be a non-empty string")
        event = TraceEvent(
            seq=len(self._events) + 1,
            layer=layer,
            stage=stage,
            executor=executor,
            status=status,
            summary=_safe_text(summary),
            data=_safe_value(data or {}),
        )
        self._events.append(event)
        return event


__all__ = ["TraceEvent", "TraceRecorder"]
