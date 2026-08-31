"""Answer a contextual question about the active circuit or its results."""

from ..context import AgentContext
from ..models import AgentIntent, AgentResult
from .base import TaskHandler


class ExplainCurrentHandler(TaskHandler):
    task_type = "explain_current"

    def execute(self, intent: AgentIntent, context: AgentContext) -> AgentResult:
        english = intent.response_language == "en"
        explanation = intent.explanation or (
            "I could not produce a reliable explanation of the current circuit."
            if english
            else "我暂时无法可靠解释当前电路。"
        )
        return AgentResult(
            ok=True,
            task_type=self.task_type,
            response_language=intent.response_language,
            explanation=explanation,
        )
