"""LoomQ L2 orchestration: model planning, program tools, and verification."""

from __future__ import annotations

import importlib
from typing import Any

_llm_client = importlib.import_module(
    "starter_kit.llm_client" if (__package__ or "").startswith("starter_kit.") else "llm_client"
)

from .prompts import CORRECTION_PROMPT, SYSTEM_PROMPT
from .response import AgentPlan, ModelResponseError, parse_agent_plan
from .selector import select_backends
from .verifier import VerificationReport, verify_qasm


_MAX_PROMPT_CHARS = 32_768
_MAX_MODEL_CONTENT_CHARS = 65_536


def _content(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelResponseError("model API response is missing assistant content") from exc
    if not isinstance(content, str) or not content.strip():
        raise ModelResponseError("model API returned empty assistant content")
    if len(content) > _MAX_MODEL_CONTENT_CHARS:
        raise ModelResponseError("model response is too large")
    return content


def _complete(messages: list[dict[str, str]]) -> str:
    return _content(_llm_client.chat_completion(messages))


def _verify_plan(plan: AgentPlan) -> VerificationReport | None:
    if plan.task == "recommend":
        return None
    assert plan.qasm is not None
    return verify_qasm(plan.qasm)


def _plan_with_one_correction(prompt: str) -> tuple[AgentPlan, VerificationReport | None]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    first_content = _complete(messages)
    try:
        first_plan = parse_agent_plan(first_content)
        return first_plan, _verify_plan(first_plan)
    except (ModelResponseError, ValueError, RuntimeError) as exc:
        correction = (
            f"{CORRECTION_PROMPT}\n"
            f"Verifier error: {type(exc).__name__}: {exc}\n"
            "Return the corrected JSON now."
        )
        corrected_content = _complete(
            messages
            + [
                {"role": "assistant", "content": first_content},
                {"role": "user", "content": correction},
            ]
        )
        try:
            corrected_plan = parse_agent_plan(corrected_content)
            return corrected_plan, _verify_plan(corrected_plan)
        except (ModelResponseError, ValueError, RuntimeError) as second_exc:
            raise RuntimeError(
                f"LoomQ could not verify the corrected model result: {type(second_exc).__name__}: {second_exc}"
            ) from second_exc


def _render_program(plan: AgentPlan, report: VerificationReport) -> str:
    checks = "、".join(report.checks)
    return (
        f"{plan.explanation}\n\n"
        f"验证通过：{checks}。参考分布：{report.summary}。\n\n"
        f"{report.qasm}"
    )


def _render_recommendation(plan: AgentPlan) -> str:
    assert plan.constraints is not None
    backends = select_backends(plan.constraints)
    if not backends:
        return f"{plan.explanation}\n\n没有后端同时满足这些约束。请降低比特数或放宽排队、费用、账号条件。"
    lines = [plan.explanation, "", "满足全部约束的规范后端 ID："]
    for backend in backends:
        lines.append(
            f"- {backend['id']} — {backend['name']}；最多 {backend['max_qubits']} 比特，"
            f"排队={backend['queue']}，费用={backend['cost']}"
        )
    return "\n".join(lines)


def agent_chat(prompt: str) -> str:
    """Call the configured model once or twice, then return tool-verified output."""

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be non-empty text")
    if len(prompt) > _MAX_PROMPT_CHARS:
        raise ValueError(f"prompt exceeds {_MAX_PROMPT_CHARS} characters")
    plan, report = _plan_with_one_correction(prompt.strip())
    if plan.task == "recommend":
        return _render_recommendation(plan)
    assert report is not None
    return _render_program(plan, report)
