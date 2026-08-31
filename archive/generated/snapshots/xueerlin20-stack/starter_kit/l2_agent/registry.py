"""Task-handler registry used by the L2 agent engine."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from .handlers import (
    ClarifyHandler,
    ExplainCurrentHandler,
    GenerateQasmHandler,
    RecommendBackendHandler,
    RepairQasmHandler,
)
from .handlers.base import TaskHandler


class HandlerRegistry:
    def __init__(self, handlers: Iterable[TaskHandler] = ()) -> None:
        self._handlers: Dict[str, TaskHandler] = {}
        for handler in handlers:
            self.register(handler)

    def register(self, handler: TaskHandler) -> None:
        task_type = getattr(handler, "task_type", "")
        if not task_type:
            raise ValueError("handler task_type must be non-empty")
        if task_type in self._handlers:
            raise ValueError("duplicate handler for task type: %s" % task_type)
        self._handlers[task_type] = handler

    def get(self, task_type: str) -> Optional[TaskHandler]:
        return self._handlers.get(task_type)


def default_registry() -> HandlerRegistry:
    return HandlerRegistry(
        [
            GenerateQasmHandler(),
            RepairQasmHandler(),
            RecommendBackendHandler(),
            ExplainCurrentHandler(),
            ClarifyHandler(),
        ]
    )
