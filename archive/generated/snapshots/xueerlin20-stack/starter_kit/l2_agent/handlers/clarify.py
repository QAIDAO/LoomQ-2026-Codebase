"""Honest fallback for ambiguous or unsupported requests."""

from ..context import AgentContext
from ..models import AgentIntent, AgentResult
from .base import TaskHandler


class ClarifyHandler(TaskHandler):
    task_type = "clarify"

    def execute(self, intent: AgentIntent, context: AgentContext) -> AgentResult:
        english = intent.response_language == "en"
        message = intent.explanation or (
            "I cannot understand the request reliably enough to act on it. "
            "Please describe the circuit goal, input, or desired change more specifically."
            if english
            else "我还不能可靠理解这个问题，因此不会猜测或编造结果。请补充电路目标、输入或希望修改的内容。"
        )
        return AgentResult.failure("clarify", message, intent.response_language)
