"""Stable text rendering for the automatic L2 evaluator."""

from .models import AgentResult


def render_result(result: AgentResult) -> str:
    english = result.response_language == "en"
    if not result.ok:
        return (
            "LoomQ Agent could not complete the task: %s" % result.message
            if english
            else "LoomQ Agent 无法完成该任务：%s" % result.message
        )

    if result.qasm:
        explanation = ""
        if result.explanation:
            explanation = "\n\n%s%s%s" % (
                "Explanation" if english else "说明",
                ": " if english else "：",
                result.explanation,
            )
        semantic = ""
        validation_text = result.validation.get("explanation")
        if validation_text:
            semantic = "\n\n%s%s%s" % (
                "Run validation" if english else "运行验证",
                ": " if english else "：",
                validation_text,
            )
        heading = (
            "Generated and validated successfully with LoomQ."
            if english
            else "已生成并通过 LoomQ 验证。"
        )
        return "%s\n\n```qasm\n%s\n```%s%s" % (
            heading,
            result.qasm.strip(),
            semantic,
            explanation,
        )

    if result.backend_id:
        explanation = result.explanation or (
            "It satisfies the stated constraints."
            if english
            else "满足用户声明的约束。"
        )
        alternatives = ""
        if result.alternatives:
            alternatives = "\n%s: %s" % (
                "Alternatives" if english else "备选",
                ", ".join(result.alternatives)
                if english
                else "、".join(result.alternatives),
            )
        return "%s: %s\n\n%s: %s%s" % (
            "Recommended backend" if english else "推荐后端",
            result.backend_id,
            "Reason" if english else "理由",
            explanation,
            alternatives,
        )

    return "LoomQ Agent completed the task." if english else "LoomQ Agent 已完成任务。"
