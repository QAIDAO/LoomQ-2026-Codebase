"""Handler for repairing QASM while preserving the declared user goal."""

from ..context import AgentContext
from ..models import AgentIntent, AgentResult
from .base import TaskHandler
from .qasm_common import validate_with_one_repair


class RepairQasmHandler(TaskHandler):
    task_type = "repair_qasm"

    def execute(self, intent: AgentIntent, context: AgentContext) -> AgentResult:
        return validate_with_one_repair(intent, context)
