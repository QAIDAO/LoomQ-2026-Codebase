from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    task: str
    qasm: str | None = None
    target: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    backend_hint: str | None = None
    explanation: str = ""


def _json_object(text: str) -> dict[str, Any] | None:
    candidates = [text]
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        candidates.insert(0, fenced.group(1))
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict):
            return value
    return None


def parse_structured(text: str) -> AgentResult | None:
    value = _json_object(text)
    if value is None or value.get("task") not in {"generate", "repair", "backend"}:
        return None
    return AgentResult(
        task=value["task"],
        qasm=value.get("qasm") if isinstance(value.get("qasm"), str) else None,
        target=value.get("target") if isinstance(value.get("target"), dict) else {},
        constraints=(
            value.get("constraints") if isinstance(value.get("constraints"), dict) else {}
        ),
        backend_hint=(
            value.get("backend_hint")
            if isinstance(value.get("backend_hint"), str)
            else None
        ),
        explanation=(
            value.get("explanation")
            if isinstance(value.get("explanation"), str)
            else ""
        ),
    )


def parse_target(text: str) -> dict[str, Any] | None:
    """Parse a target-only response, while accepting a full AgentResult too."""
    value = _json_object(text)
    if value is None:
        return None
    target = value.get("target")
    return target if isinstance(target, dict) and target else None
