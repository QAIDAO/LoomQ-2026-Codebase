"""Web-only teaching explanations for an already validated circuit trace."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any, Mapping, Sequence

try:
    # 支持从仓库根目录按 starter_kit 包导入。
    from starter_kit import llm_client
except ImportError:  # pragma: no cover - 由 starter_kit 根目录运行时使用
    import llm_client  # type: ignore[no-redef]

from .debug_trace import TraceEvent


TEACHING_SYSTEM_PROMPT = """你是 LoomQ Web Quantum Debugger 的教学解释器。
输入中的 QASM 已经通过独立 Parser 和语义验证；你只能解释，不能修改、纠错、评分或重新生成电路。
只返回一个 JSON 对象，不返回 JSON 外散文：
{"circuit_goal":"一句话目标","steps":[{"operation_index":0,"purpose":"为什么当前目标在这里需要这一步","concept":"叠加或 null","concept_explanation":"1 到 3 句最低限度解释或 null"}]}
每个 operation_index 必须来自输入 circuit_steps。purpose 必须结合整个电路目标和前后步骤，不能只是复述 Gate 的固定定义。
measurement 也需要解释为什么最终要读成经典结果。不是每一步都需要新概念；不需要时 concept 和 concept_explanation 都返回 null。
只在 Trace 确实体现时提供最低限度概念：出现多个同时保留的基态分支时可解释“叠加”；受控操作把多个量子位关联为整体时可解释“纠缠”；概率不变但复振幅改变时可解释“相位”。
面向懂软件开发但没有量子背景的人，不讲完整线性代数、量子力学历史或无关理论。"""

_JSON_FENCE_RE = re.compile(
    r"^```json\s*\n(?P<body>.*?)\n```$", re.IGNORECASE | re.DOTALL
)
_MAX_GOAL_LENGTH = 160
_MAX_PURPOSE_LENGTH = 240
_MAX_CONCEPT_LENGTH = 40
_MAX_CONCEPT_EXPLANATION_LENGTH = 360


@dataclass(frozen=True)
class TeachingStep:
    operation_index: int
    purpose: str
    concept: str | None
    concept_explanation: str | None


@dataclass(frozen=True)
class TeachingExplanation:
    circuit_goal: str
    steps: tuple[TeachingStep, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _response_content(response: Any) -> str:
    if not isinstance(response, Mapping):
        raise ValueError("teaching response must be an object")
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("teaching response is missing choices")
    choice = choices[0]
    if not isinstance(choice, Mapping):
        raise ValueError("teaching response choice is invalid")
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("teaching response message is invalid")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("teaching response content is empty")
    return content.strip()


def _bounded_text(value: Any, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split()).strip()
    if not text or len(text) > maximum:
        return None
    return text


def parse_teaching_response(
    response: Any, allowed_operation_indices: set[int]
) -> TeachingExplanation:
    """Validate model output and ignore steps that do not map to the real trace."""
    content = _response_content(response)
    fence = _JSON_FENCE_RE.fullmatch(content)
    if fence is not None:
        content = fence.group("body").strip()
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("teaching response is not valid JSON") from None
    if not isinstance(payload, Mapping):
        raise ValueError("teaching response JSON must be an object")

    circuit_goal = _bounded_text(payload.get("circuit_goal"), _MAX_GOAL_LENGTH)
    raw_steps = payload.get("steps")
    if circuit_goal is None or not isinstance(raw_steps, list):
        raise ValueError("teaching response schema is invalid")

    steps: list[TeachingStep] = []
    seen_indices: set[int] = set()
    for raw_step in raw_steps:
        if not isinstance(raw_step, Mapping):
            continue
        operation_index = raw_step.get("operation_index")
        purpose = _bounded_text(raw_step.get("purpose"), _MAX_PURPOSE_LENGTH)
        if (
            not isinstance(operation_index, int)
            or isinstance(operation_index, bool)
            or operation_index not in allowed_operation_indices
            or operation_index in seen_indices
            or purpose is None
        ):
            continue
        concept = _bounded_text(raw_step.get("concept"), _MAX_CONCEPT_LENGTH)
        concept_explanation = _bounded_text(
            raw_step.get("concept_explanation"),
            _MAX_CONCEPT_EXPLANATION_LENGTH,
        )
        # 概念名与解释必须成对出现，避免 UI 渲染空教学卡片。
        if concept is None or concept_explanation is None:
            concept = None
            concept_explanation = None
        steps.append(
            TeachingStep(
                operation_index=operation_index,
                purpose=purpose,
                concept=concept,
                concept_explanation=concept_explanation,
            )
        )
        seen_indices.add(operation_index)
    return TeachingExplanation(circuit_goal=circuit_goal, steps=tuple(steps))


def _state_payload(value: Any) -> list[dict[str, float | str]]:
    if not isinstance(value, list):
        return []
    safe_entries = []
    for item in value:
        if not isinstance(item, Mapping) or not isinstance(item.get("basis"), str):
            continue
        safe_entries.append(
            {
                "basis": item["basis"],
                "real": float(item.get("real", 0.0)),
                "imag": float(item.get("imag", 0.0)),
                "probability": float(item.get("probability", 0.0)),
            }
        )
    return safe_entries


def _circuit_step_payload(event: TraceEvent) -> dict[str, Any]:
    data = event.data
    payload: dict[str, Any] = {
        "stage": event.stage,
        "operation_index": data.get("operation_index"),
        "gate": data.get("gate", "measure"),
        "qubits": data.get("qubits", []),
        "parameters": data.get("parameters", []),
    }
    if event.stage == "gate_step":
        payload["state_before"] = _state_payload(data.get("state_before"))
        payload["state_after"] = _state_payload(data.get("state_after"))
    else:
        payload["probabilities_before"] = data.get("probabilities_before", [])
        payload["mappings"] = data.get("mappings", [])
    return payload


def explain_validated_circuit(
    original_prompt: str,
    final_validated_qasm: str,
    circuit_events: Sequence[TraceEvent],
) -> TeachingExplanation | None:
    """Call the optional Web explainer once; failures never affect correctness."""
    actionable_events = tuple(
        event
        for event in circuit_events
        if event.stage in ("gate_step", "measurement")
        and isinstance(event.data.get("operation_index"), int)
    )
    if not actionable_events:
        return None
    allowed_indices = {
        int(event.data["operation_index"]) for event in actionable_events
    }
    input_payload = {
        "original_prompt": original_prompt,
        "final_validated_qasm": final_validated_qasm,
        "circuit_steps": [
            _circuit_step_payload(event) for event in actionable_events
        ],
    }
    try:
        response = llm_client.chat_completion(
            [
                {"role": "system", "content": TEACHING_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(input_payload, ensure_ascii=False),
                },
            ]
        )
        return parse_teaching_response(response, allowed_indices)
    except Exception:
        # 教学解释是 Web 附加体验，任何模型或协议错误都静默降级。
        return None


__all__ = [
    "TeachingExplanation",
    "TeachingStep",
    "explain_validated_circuit",
    "parse_teaching_response",
]
