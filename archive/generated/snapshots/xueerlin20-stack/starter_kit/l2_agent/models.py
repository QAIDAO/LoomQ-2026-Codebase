"""Shared data models passed between the L2 agent layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


SUPPORTED_TASK_TYPES = frozenset(
    {"generate_qasm", "repair_qasm", "recommend_backend", "explain_current", "clarify"}
)


@dataclass(frozen=True)
class AgentIntent:
    """A model-produced work order understood by task handlers."""

    task_type: str
    user_goal: str
    response_language: str = "zh"
    candidate_qasm: Optional[str] = None
    source_qasm: Optional[str] = None
    circuit: Dict[str, Any] = field(default_factory=dict)
    backend_constraints: Dict[str, Any] = field(default_factory=dict)
    explanation: Optional[str] = None

    def validate(self) -> None:
        if self.task_type not in SUPPORTED_TASK_TYPES:
            raise ValueError("unsupported L2 task type: %s" % self.task_type)
        if not isinstance(self.user_goal, str) or not self.user_goal.strip():
            raise ValueError("L2 intent user_goal must be a non-empty string")
        if self.response_language not in {"zh", "en"}:
            raise ValueError("L2 intent response_language must be zh or en")


@dataclass(frozen=True)
class ValidationResult:
    """Result of running a candidate through L1 and checking its output."""

    ok: bool
    status: str
    explanation: str
    qasm: str
    fidelity: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    repairable: bool = True


@dataclass(frozen=True)
class BackendSelection:
    """Result returned by the deterministic backend-selection tool."""

    selected_id: Optional[str]
    explanation: str
    alternatives: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentResult:
    """Unified result produced by every task handler."""

    ok: bool
    task_type: str
    response_language: str = "zh"
    message: str = ""
    qasm: Optional[str] = None
    backend_id: Optional[str] = None
    explanation: Optional[str] = None
    alternatives: List[str] = field(default_factory=list)
    validation: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def failure(
        cls, task_type: str, message: str, response_language: str = "zh"
    ) -> "AgentResult":
        return cls(
            ok=False,
            task_type=task_type,
            message=message,
            response_language=response_language,
        )
