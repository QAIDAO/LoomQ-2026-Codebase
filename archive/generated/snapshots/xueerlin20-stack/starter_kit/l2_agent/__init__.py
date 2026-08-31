"""Composable LoomQ L2 agent framework.

The package deliberately keeps model transport and task implementation behind
small interfaces.  Tests can inject fakes now; the real LLM gateway and tools
can be added without changing the orchestration layer later.
"""

from .agent import AgentEngine
from .context import AgentContext
from .models import (
    AgentIntent,
    AgentResult,
    BackendSelection,
    ValidationResult,
)
from .registry import HandlerRegistry, default_registry

__all__ = [
    "AgentContext",
    "AgentEngine",
    "AgentIntent",
    "AgentResult",
    "BackendSelection",
    "HandlerRegistry",
    "ValidationResult",
    "default_registry",
]
