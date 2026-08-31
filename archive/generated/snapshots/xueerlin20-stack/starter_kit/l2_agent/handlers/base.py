"""Base interface shared by all task handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..context import AgentContext
from ..models import AgentIntent, AgentResult


class TaskHandler(ABC):
    task_type: str

    @abstractmethod
    def execute(self, intent: AgentIntent, context: AgentContext) -> AgentResult:
        """Execute a validated intent and return a unified result."""
