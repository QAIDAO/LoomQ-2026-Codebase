"""Top-level orchestration for the LoomQ L2 agent."""

from __future__ import annotations

from .context import AgentContext
from .models import AgentResult
from .registry import HandlerRegistry
from .renderer import render_result


class AgentEngine:
    """Understand, dispatch, execute, and render one user request."""

    def __init__(self, context: AgentContext, registry: HandlerRegistry) -> None:
        self._context = context
        self._registry = registry

    def respond(self, prompt: str) -> str:
        return render_result(self.execute(prompt))

    def execute(self, prompt: str) -> AgentResult:
        """Run one request and return structured data for interactive clients."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("L2 prompt must be a non-empty string")

        begin_request = getattr(self._context.llm, "begin_request", None)
        if callable(begin_request):
            begin_request()
        try:
            intent = self._context.llm.understand(prompt)
        except RuntimeError as exc:
            unreliable_prefixes = (
                "invalid LoomQ LLM response structure",
                "LoomQ LLM returned",
                "LoomQ LLM JSON",
                "LoomQ LLM intent",
                "LoomQ LLM response_language",
            )
            if not str(exc).startswith(unreliable_prefixes):
                raise
            english = not any("\u4e00" <= character <= "\u9fff" for character in prompt)
            return AgentResult.failure(
                "clarify",
                (
                    "I did not receive enough reliable information to answer, so I will not guess. Please rephrase the request with the circuit goal or desired change."
                    if english
                    else "我没有得到足够可靠的信息来理解并回答，因此不会猜测或编造。请换一种说法，并补充电路目标或希望修改的内容。"
                ),
                "en" if english else "zh",
            )
        intent.validate()

        handler = self._registry.get(intent.task_type)
        if handler is None:
            raise ValueError("no handler registered for task: %s" % intent.task_type)

        return handler.execute(intent, self._context)
