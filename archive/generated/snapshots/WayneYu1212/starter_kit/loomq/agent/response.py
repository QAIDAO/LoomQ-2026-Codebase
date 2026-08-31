"""Strict, typed parsing of the LLM-to-program tool protocol."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal


TaskName = Literal["generate", "repair", "recommend"]
BackendKind = Literal["simulator", "qpu", "cloud"]


class ModelResponseError(ValueError):
    """Raised when a model response cannot safely drive LoomQ tools."""


@dataclass(frozen=True, slots=True)
class BackendConstraints:
    qubits: int | None = None
    kind: BackendKind | None = None
    zero_queue: bool | None = None
    avoid_paid: bool | None = None
    accountless: bool | None = None


@dataclass(frozen=True, slots=True)
class AgentPlan:
    task: TaskName
    qasm: str | None
    constraints: BackendConstraints | None
    explanation: str


_PLAN_KEYS = {"task", "qasm", "constraints", "explanation"}
_CONSTRAINT_KEYS = {"qubits", "kind", "zero_queue", "avoid_paid", "accountless"}


def _json_text(text: str) -> str:
    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.I | re.S)
    if fenced is not None:
        return fenced.group(1)
    if not stripped.startswith("{") or not stripped.endswith("}"):
        raise ModelResponseError("model response must be one JSON object")
    return stripped


def _optional_bool(payload: dict[str, object], name: str) -> bool | None:
    value = payload.get(name)
    if value is not None and not isinstance(value, bool):
        raise ModelResponseError(f"constraint `{name}` must be boolean or null")
    return value


def _constraints(payload: object) -> BackendConstraints:
    if not isinstance(payload, dict):
        raise ModelResponseError("recommend constraints must be an object")
    extra = set(payload) - _CONSTRAINT_KEYS
    if extra:
        raise ModelResponseError("unknown backend constraint: " + ", ".join(sorted(extra)))
    qubits = payload.get("qubits")
    if qubits is not None and (
        isinstance(qubits, bool) or not isinstance(qubits, int) or qubits <= 0
    ):
        raise ModelResponseError("constraint `qubits` must be a positive integer or null")
    kind = payload.get("kind")
    if kind is not None and kind not in {"simulator", "qpu", "cloud"}:
        raise ModelResponseError("constraint `kind` is invalid")
    return BackendConstraints(
        qubits=qubits,
        kind=kind,
        zero_queue=_optional_bool(payload, "zero_queue"),
        avoid_paid=_optional_bool(payload, "avoid_paid"),
        accountless=_optional_bool(payload, "accountless"),
    )


def parse_agent_plan(text: str) -> AgentPlan:
    """Parse one model response into the only data allowed to drive tools."""

    if not isinstance(text, str) or not text.strip():
        raise ModelResponseError("model response must be non-empty text")
    try:
        payload = json.loads(_json_text(text))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ModelResponseError("model response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ModelResponseError("model response JSON must be an object")
    if set(payload) != _PLAN_KEYS:
        raise ModelResponseError("model response has missing or extra keys")

    task = payload["task"]
    if task not in {"generate", "repair", "recommend"}:
        raise ModelResponseError("model task must be generate, repair, or recommend")
    explanation = payload["explanation"]
    if not isinstance(explanation, str) or not explanation.strip():
        raise ModelResponseError("model explanation must be non-empty text")

    qasm = payload["qasm"]
    constraint_payload = payload["constraints"]
    if task in {"generate", "repair"}:
        if not isinstance(qasm, str) or not qasm.strip():
            raise ModelResponseError(f"{task} plan must contain QASM")
        if constraint_payload is not None:
            raise ModelResponseError(f"{task} plan constraints must be null")
        return AgentPlan(task, qasm.strip() + "\n", None, explanation.strip())

    if qasm is not None:
        raise ModelResponseError("recommend plan qasm must be null")
    return AgentPlan("recommend", None, _constraints(constraint_payload), explanation.strip())
