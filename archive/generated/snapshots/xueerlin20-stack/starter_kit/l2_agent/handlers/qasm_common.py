"""Shared one-repair validation flow for QASM handlers."""

from __future__ import annotations

from ..context import AgentContext
from ..models import AgentIntent, AgentResult


def validate_with_one_repair(
    intent: AgentIntent,
    context: AgentContext,
) -> AgentResult:
    candidate = intent.candidate_qasm
    if not isinstance(candidate, str) or not candidate.strip():
        message = (
            "The model did not provide a QASM candidate."
            if intent.response_language == "en"
            else "模型没有提供 QASM 候选。"
        )
        return AgentResult.failure(
            intent.task_type, message, intent.response_language
        )

    validation = context.validator.validate(candidate, intent)
    repaired = False
    if not validation.ok and validation.repairable:
        candidate = context.llm.repair_qasm(
            user_goal=intent.user_goal,
            broken_qasm=validation.qasm,
            validation_error=validation.explanation,
            source_qasm=intent.source_qasm,
        )
        repaired = True
        validation = context.validator.validate(candidate, intent)

    if not validation.ok:
        if intent.response_language == "en":
            prefix = (
                "The circuit still failed validation after one repair"
                if repaired
                else "The circuit failed validation"
            )
            separator = ": "
        else:
            prefix = (
                "电路在一次修复后仍未通过验证"
                if repaired
                else "电路未通过验证"
            )
            separator = "："
        return AgentResult.failure(
            intent.task_type,
            prefix + separator + validation.explanation,
            intent.response_language,
        )

    validation_details = {
        "status": validation.status,
        "explanation": validation.explanation,
        "repaired": repaired,
        **validation.details,
    }
    if validation.fidelity is not None:
        validation_details["fidelity"] = validation.fidelity

    return AgentResult(
        ok=True,
        task_type=intent.task_type,
        response_language=intent.response_language,
        qasm=validation.qasm,
        explanation=intent.explanation,
        validation=validation_details,
    )
