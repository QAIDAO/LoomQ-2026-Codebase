"""Minimal L2 model-call pipeline with one bounded QASM repair attempt."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any, Mapping

try:
    # 支持从仓库根目录按 starter_kit 包导入。
    from starter_kit import llm_client
except ImportError:  # pragma: no cover - 由 starter_kit 评测根目录运行时使用
    import llm_client  # type: ignore[no-redef]

from .backend_selector import Backend, BackendConstraints, select_backends
from .debug_trace import TraceRecorder
from .parser import parse_qasm
from .qasm_tools import QASMValidationError, extract_qasm, validate_qasm
from .semantic_verifier import (
    DEFAULT_FIDELITY_THRESHOLD,
    SemanticVerificationError,
    TargetSpecification,
    parse_target_specification,
    verify_semantics,
)


SYSTEM_PROMPT = """你是 LoomQ 的量子任务约束提取与 OpenQASM 2.0 助手。
只返回一个 JSON 对象，不要返回 JSON 之外的散文。生成或修复 QASM 时返回：
{"task_type":"generate_qasm 或 repair_qasm","qasm":"OPENQASM 2.0; ...","explanation":"简短说明"}
请判断用户是在生成还是修复 QASM，并设置对应 task_type。
qasm 必须是完整的 OpenQASM 2.0 程序，包含 include 和 qreg；用户明确要求测量时还必须包含 creg 和测量语句。
只可使用当前项目支持的门：h、x、s、sdg、t、tdg、ry、rz、cx、cu1、swap、ccx。
z 门不受支持，绝对不要输出 z；需要等价的 Z 相位时使用连续两个 s 门。
修复时必须保持用户明确声明的目标态、目标功能和测量语义，不能只修正语法而改变电路目标。
请根据用户的实际要求生成电路，不要硬编码公开 GHZ 示例的固定答案。
选择后端时只提取用户约束，不要推荐或输出 backend ID，并返回：
{"task_type":"select_backend","qasm":null,"backend_constraints":{"min_qubits":null,"require_qpu":null,"require_no_queue":false,"cost_policy":"free_only 或 free_or_quota 或 paid_allowed 或 unspecified","allow_account_required":null},"explanation":"简短说明"}
未声明的约束使用 null、false 或 unspecified，不要擅自收紧。
"""

# 正式评测每 case 为 120 秒；内部预留 5 秒给异常归一化和进程回收。
CASE_DEADLINE_SECONDS = 115.0
# 开发期失败诊断与正式 evidence 分离，绝不作为比赛证据写入。
L2_DEBUG_OUTPUT = Path(__file__).resolve().parents[1] / "runtime" / "l2-debug"
_SENSITIVE_TEXT_RE = re.compile(
    r"(?i)(?:bearer\s+|\bsk-)[A-Za-z0-9._~+/=-]{8,}"
    r"|(?:api[_-]?key|token)\s*[=:]\s*[^\s,;]+"
    r"|\b[a-f0-9]{32,}\b"
)

TARGET_JUDGE_SYSTEM_PROMPT = """你是独立的量子目标态规格提取器，只能依据用户原始请求判断目标，不能查看或猜测候选 QASM。
只返回一个 JSON 对象，不返回额外散文，也绝对不要返回 QASM。
如果目标可以可靠表示为纯态，返回：
{"verification_mode":"statevector","pure_state_requested":true,"qubit_count":2,"amplitudes":[{"basis":"00","real":0.7071067811865476,"imag":0.0},{"basis":"11","real":0.7071067811865476,"imag":0.0}],"explanation":"简短目标说明"}
basis 按 q[0] 到 q[n-1] 的顺序书写；未列出的 basis amplitude 视为 0。必须给出归一化、有限数值的复振幅，并保留用户要求的相对相位。
如果原始请求无法可靠转换为纯态目标，返回：
{"verification_mode":"unsupported","pure_state_requested":false,"unsupported_reason":"no_unique_target 或 mixed_state 或 distribution_only 或 insufficient_spec","explanation":"无法可靠进行纯态验证的原因"}
Bell、EPR、GHZ 等命名纯态，以及明确 ket、amplitude、relative phase、pure-state 或 state-preparation 目标必须返回 statevector。
不得因为目标复杂、包含相位或不知道如何构造电路而返回 unsupported。unsupported 只允许用于没有唯一目标态、mixed state、仅有测量分布或信息不足的请求。
"""

_JSON_FENCE_RE = re.compile(
    r"^```json\s*\n(?P<body>.*?)\n```$", re.IGNORECASE | re.DOTALL
)
_NEGATED_MEASUREMENT_RE = re.compile(
    r"(?:不(?:需要|要求|要|进行|做)?|无需(?:进行)?|省略|移除|删除)"
    r"(?:添加|进行|保留)?(?:任何)?(?:测量|测定|读出|采样)"
    r"|(?:without|no)\s+(?:any\s+)?(?:measurements?|measurement|measuring|readouts?|sampling)"
    r"|(?:do\s+not|don't|omit|remove)\s+(?:add\s+|include\s+|perform\s+)?"
    r"(?:any\s+)?(?:measurements?|measurement|measuring|readouts?|sampling)"
    r"|measurement[- ]free|unmeasured",
    re.IGNORECASE,
)
_MEASUREMENT_REQUEST_RE = re.compile(
    r"测量|测定|读出|采样|measure(?:ment|ments|d|s|ing)?|read[ -]?outs?|"
    r"sampl(?:e|es|ed|ing)|shots?|counts?",
    re.IGNORECASE,
)
_NAMED_PURE_STATE_RE = re.compile(
    r"\b(?:bell|epr|ghz)\b|贝尔|格林伯格[－—-]?霍恩[－—-]?蔡林格",
    re.IGNORECASE,
)
_KET_STATE_RE = re.compile(r"\|\s*[01]+\s*(?:>|⟩)")
_EXPLICIT_PURE_STATE_RE = re.compile(
    r"(?:basis|state|ket)\s+amplitudes?|"
    r"(?:指定|明确|目标|各(?:基态|基矢|态)).{0,8}振幅|振幅.{0,8}(?:为|分别|等于)|"
    r"relative\s+phase|phase\s+(?:offset|difference)|相对相位|相位差|"
    r"pure[-\s]?state|纯态|state[-\s]?preparation|"
    r"prepare\b.{0,32}\bquantum\s+state\b|"
    r"制备.{0,24}(?:量子态|目标态|纠缠态|叠加态)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GenerationResponse:
    """Validated fields from the model's structured response."""

    task_type: str
    qasm: str
    explanation: str


@dataclass(frozen=True)
class _CandidateResponse:
    """Structurally valid model fields before local QASM validation."""

    task_type: str
    qasm: str
    explanation: str


class _CandidateVerificationError(RuntimeError):
    """Bounded candidate failure suitable for the one repair prompt."""

    def __init__(self, diagnostic: str, fidelity: float | None = None) -> None:
        super().__init__("candidate QASM failed local verification")
        self.diagnostic = diagnostic
        self.fidelity = fidelity


@dataclass
class _FailureDebugTrace:
    """只保存已解析的安全字段，绝不保留 HTTP 或模型原始响应。"""

    user_request: str
    failure_stage: str = "initial"
    first_candidate_qasm: str | None = None
    repair_candidate_qasm: str | None = None
    target_spec: Mapping[str, Any] | None = None
    first_diagnostic: str | None = None
    second_diagnostic: str | None = None
    first_fidelity: float | None = None
    second_fidelity: float | None = None


def _redact_sensitive_text(value: str) -> str:
    """避免用户请求或 QASM 注释意外将凭据写入本地诊断文件。"""
    return _SENSITIVE_TEXT_RE.sub("[REDACTED]", value)


def _safe_debug_value(value: Any) -> Any:
    """递归清理将要落盘的已解析字段。"""
    if isinstance(value, str):
        return _redact_sensitive_text(value)
    if isinstance(value, Mapping):
        return {str(key): _safe_debug_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_debug_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return "[UNSUPPORTED DEBUG VALUE]"


def _write_failure_debug_trace(trace: _FailureDebugTrace) -> None:
    """最终失败时最佳努力写入诊断；写入失败绝不改变 Agent 的异常。"""
    payload = {
        "schema_version": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "user_request": _redact_sensitive_text(trace.user_request),
        "failure_stage": trace.failure_stage,
        "first_candidate_qasm": _safe_debug_value(trace.first_candidate_qasm),
        "repair_candidate_qasm": _safe_debug_value(trace.repair_candidate_qasm),
        "target_spec": _safe_debug_value(trace.target_spec),
        "first_verification_diagnostic": _safe_debug_value(trace.first_diagnostic),
        "second_verification_diagnostic": _safe_debug_value(trace.second_diagnostic),
        "fidelity_result": {
            "first": trace.first_fidelity,
            "second": trace.second_fidelity,
        },
    }
    try:
        L2_DEBUG_OUTPUT.mkdir(parents=True, exist_ok=True)
        filename = "l2-failure-%s-%d.json" % (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
            time.time_ns(),
        )
        (L2_DEBUG_OUTPUT / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        # 诊断目录权限或磁盘问题不能掩盖原始 Agent 失败。
        return


def _trace(
    trace_sink: TraceRecorder | None,
    *,
    stage: str,
    executor: str,
    status: str,
    summary: str,
    data: Mapping[str, Any] | None = None,
) -> None:
    if trace_sink is not None:
        trace_sink.emit(
            layer="agent",
            stage=stage,
            executor=executor,
            status=status,
            summary=summary,
            data=data,
        )


def _response_content(response: Any) -> str:
    """Read choices[0].message.content without echoing the raw response."""
    if not isinstance(response, Mapping):
        raise RuntimeError("L2 model response must be an object")
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("L2 model response is missing choices")
    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        raise RuntimeError("L2 model response choice must be an object")
    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        raise RuntimeError("L2 model response is missing message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("L2 model response content must be a non-empty string")
    return content.strip()


def _parse_response_payload(response: Any) -> dict[str, Any]:
    """Parse the shared JSON envelope without interpreting the task payload."""
    content = _response_content(response)
    fence_match = _JSON_FENCE_RE.fullmatch(content)
    if fence_match is not None:
        content = fence_match.group("body").strip()

    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        raise RuntimeError("L2 model response content is not valid JSON") from None
    if not isinstance(payload, dict):
        raise RuntimeError("L2 model response JSON must be an object")
    return payload


def _parse_explanation(payload: Mapping[str, Any]) -> str:
    explanation = payload.get("explanation", "")
    if not isinstance(explanation, str):
        raise RuntimeError("L2 model response explanation must be a string")
    if "OPENQASM 2.0;" in explanation or "```" in explanation:
        raise RuntimeError("L2 model response explanation must not contain code")
    return explanation.strip()


def _parse_candidate_payload(payload: Mapping[str, Any]) -> _CandidateResponse:
    """Parse QASM fields without treating broken QASM as broken JSON."""
    task_type = payload.get("task_type")
    if task_type not in ("generate_qasm", "repair_qasm"):
        raise RuntimeError(
            "L2 model response task_type must be 'generate_qasm', 'repair_qasm', or 'select_backend'"
        )

    qasm_text = payload.get("qasm")
    if not isinstance(qasm_text, str) or not qasm_text.strip():
        raise RuntimeError("L2 model response qasm must be a non-empty string")
    return _CandidateResponse(
        task_type=task_type,
        qasm=qasm_text,
        explanation=_parse_explanation(payload),
    )


def _parse_candidate_response(response: Any) -> _CandidateResponse:
    return _parse_candidate_payload(_parse_response_payload(response))


def _parse_backend_constraints(payload: Mapping[str, Any]) -> BackendConstraints:
    if payload.get("task_type") != "select_backend":
        raise RuntimeError("L2 model response task_type must be 'select_backend'")
    if "qasm" not in payload or payload["qasm"] is not None:
        raise RuntimeError("L2 backend-selection response qasm must be null")
    raw_constraints = payload.get("backend_constraints")
    if not isinstance(raw_constraints, Mapping):
        raise RuntimeError(
            "L2 backend-selection response backend_constraints must be an object"
        )
    required_fields = {
        "min_qubits",
        "require_qpu",
        "require_no_queue",
        "cost_policy",
        "allow_account_required",
    }
    missing = sorted(required_fields.difference(raw_constraints))
    if missing:
        raise RuntimeError(
            "L2 backend-selection constraints are missing field(s): %s"
            % ", ".join(missing)
        )
    try:
        return BackendConstraints(
            min_qubits=raw_constraints["min_qubits"],
            require_qpu=raw_constraints["require_qpu"],
            require_no_queue=raw_constraints["require_no_queue"],
            cost_policy=raw_constraints["cost_policy"],
            allow_account_required=raw_constraints["allow_account_required"],
        )
    except ValueError as exc:
        raise RuntimeError(
            "L2 backend-selection response has invalid constraints: %s" % exc
        ) from None


def _validate_candidate(
    candidate: _CandidateResponse, *, require_measurement: bool = False
) -> GenerationResponse:
    qasm = extract_qasm(candidate.qasm)
    if qasm is None:
        raise QASMValidationError(
            "QASMExtractionError: response does not contain one unambiguous OpenQASM 2.0 program"
        )
    validate_qasm(qasm, require_measurement=require_measurement)
    return GenerationResponse(
        task_type=candidate.task_type,
        qasm=qasm,
        explanation=candidate.explanation,
    )


def parse_generation_response(
    response: Any, *, require_measurement: bool = False
) -> GenerationResponse:
    """Parse the structured protocol and validate its QASM candidate."""
    return _validate_candidate(
        _parse_candidate_response(response),
        require_measurement=require_measurement,
    )


def _parse_target_judge_response(response: Any) -> TargetSpecification:
    payload = _parse_response_payload(response)
    try:
        return parse_target_specification(payload)
    except RuntimeError as exc:
        raise RuntimeError("L2 target judge returned an invalid specification") from None


def _verify_candidate(
    candidate: _CandidateResponse,
    target: TargetSpecification,
    *,
    require_measurement: bool,
    trace_sink: TraceRecorder | None = None,
) -> GenerationResponse:
    try:
        generated = _validate_candidate(
            candidate,
            require_measurement=require_measurement,
        )
    except QASMValidationError as exc:
        _trace(
            trace_sink,
            stage="parser_validation",
            executor="local",
            status="error",
            summary="候选 QASM 未通过本地语法校验。",
            data={"diagnostic": exc.diagnostic},
        )
        raise _CandidateVerificationError(exc.diagnostic) from None

    _trace(
        trace_sink,
        stage="parser_validation",
        executor="local",
        status="ok",
        summary="候选 QASM 已通过语法和 L2 结构校验。",
        data={"require_measurement": require_measurement},
    )

    circuit = parse_qasm(generated.qasm)
    try:
        verification = verify_semantics(circuit, target)
    except SemanticVerificationError:
        _trace(
            trace_sink,
            stage="semantic_verification",
            executor="local",
            status="error",
            summary="本地 statevector 语义验证未能完成。",
            data={"diagnostic": "local statevector verification failed"},
        )
        raise _CandidateVerificationError(
            "SemanticSimulationError: local statevector verification failed"
        ) from None
    if not verification.passed:
        fidelity = verification.fidelity
        if fidelity is None:
            diagnostic = "SemanticVerificationError: candidate does not match target"
        else:
            diagnostic = "SemanticFidelityError: fidelity %.6f is below 0.970000" % fidelity
        _trace(
            trace_sink,
            stage="semantic_verification",
            executor="local",
            status="error",
            summary="候选 QASM 与独立目标态不一致。",
            data={
                "mode": verification.mode,
                "fidelity": fidelity,
                "threshold": DEFAULT_FIDELITY_THRESHOLD,
                "passed": False,
                "diagnostic": diagnostic,
            },
        )
        raise _CandidateVerificationError(diagnostic, fidelity=fidelity) from None
    _trace(
        trace_sink,
        stage="semantic_verification",
        executor="local",
        status="ok",
        summary="候选 QASM 已通过本地确定性语义验证。",
        data={
            "mode": verification.mode,
            "fidelity": verification.fidelity,
            "threshold": DEFAULT_FIDELITY_THRESHOLD,
            "passed": True,
        },
    )
    return generated


def _format_backend_reply(
    constraints: BackendConstraints, matches: tuple[Backend, ...] | None = None
) -> str:
    """Select and format only IDs originating from the official local table."""
    if matches is None:
        matches = select_backends(constraints)
    if matches:
        backend_ids = "、".join("`%s`" % backend.id for backend in matches)
        reasons = []
        if constraints.min_qubits is not None:
            reasons.append("支持至少 %d 比特" % constraints.min_qubits)
        if constraints.require_qpu is True:
            reasons.append("类型为真实量子硬件")
        if constraints.require_no_queue:
            reasons.append("能力表标记为零排队")
        if constraints.cost_policy == "free_only":
            reasons.append("能力表标记为完全免费")
        elif constraints.cost_policy == "free_or_quota":
            reasons.append("费用为免费或免费额度")
        if constraints.allow_account_required is False:
            reasons.append("无需账号")
        reason = "，".join(reasons) or "满足已提取的全部约束"
        return "满足条件的后端：%s。\n理由：%s；结果按官方能力表顺序列出。" % (
            backend_ids,
            reason,
        )

    relaxations = []
    if constraints.min_qubits is not None:
        relaxations.append("比特数")
    if constraints.require_qpu is True:
        relaxations.append("真机")
    if constraints.require_no_queue:
        relaxations.append("零排队")
    if constraints.cost_policy in ("free_only", "free_or_quota"):
        relaxations.append("费用")
    if constraints.allow_account_required is False:
        relaxations.append("账号")
    categories = "、".join(relaxations) or "当前约束"
    return (
        "当前官方能力表中没有满足全部条件的后端。"
        "可考虑放宽的约束类别：%s。" % categories
    )


def _remaining_case_time(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0.0:
        raise RuntimeError("L2 case deadline exhausted")
    return remaining


def _call_model(messages: list[dict[str, str]], *, deadline: float) -> Any:
    # deadline 耗尽时在 transport 前停止，不能产生额外模型调用。
    remaining = _remaining_case_time(deadline)
    try:
        return llm_client.chat_completion(
            messages,
            request_timeout_seconds=remaining,
        )
    except Exception:
        # 传输层或测试替身的异常可能包含凭证，因此统一改写并断开异常链。
        raise RuntimeError("L2 model request failed") from None


def _requires_measurement(prompt: str) -> bool:
    """Conservatively detect an explicit measurement request, including QASM."""
    # 先移除明确的否定表达，再识别剩余的测量、采样或 counts/shots 要求。
    without_negations = _NEGATED_MEASUREMENT_RE.sub("", prompt)
    return _MEASUREMENT_REQUEST_RE.search(without_negations) is not None


def requires_statevector_verification(prompt: str) -> bool:
    """Return whether the original request clearly names a pure-state target."""
    if not isinstance(prompt, str):
        return False
    # 这里只决定是否禁止降级，不在本地推导目标振幅或生成电路。
    return any(
        pattern.search(prompt) is not None
        for pattern in (
            _NAMED_PURE_STATE_RE,
            _KET_STATE_RE,
            _EXPLICIT_PURE_STATE_RE,
        )
    )


def _repair_prompt(
    prompt: str,
    candidate: str,
    diagnostic: str,
    target: TargetSpecification,
    *,
    require_measurement: bool,
    fidelity: float | None,
) -> str:
    """Build a bounded, explicit repair request with the original goal intact."""
    if require_measurement:
        measurement_instruction = (
            "原始请求明确要求测量，因此必须包含 creg 和对应测量语句。"
        )
    else:
        measurement_instruction = (
            "原始请求未明确要求测量，不要仅因缺少 creg 或测量语句而改变目标态制备。"
        )
    payload = {
        "instruction": (
            "修复候选 QASM。返回完整、可独立运行的 OpenQASM 2.0，包含 include、"
            "qreg。%s必须保持原始用户请求中的目标态、目标功能和测量语义。"
            "独立 target spec 是固定裁判，不得修改。只返回约定 JSON，"
            "task_type 使用 repair_qasm。" % measurement_instruction
        ),
        "original_user_request": prompt,
        "candidate_qasm": candidate,
        "target_spec": target.as_prompt_payload(),
        "validation_error": diagnostic,
        "require_measurement": require_measurement,
        "response_schema": {
            "task_type": "repair_qasm",
            "qasm": "OPENQASM 2.0; ...",
            "explanation": "简短说明",
        },
    }
    if fidelity is not None:
        payload["fidelity"] = round(fidelity, 12)
    return json.dumps(payload, ensure_ascii=False)


def _run_agent(prompt: str, trace_sink: TraceRecorder | None = None) -> str:
    """运行 Agent；仅在最终失败时落盘已解析的安全诊断。"""
    failure_debug = _FailureDebugTrace(
        user_request=prompt if isinstance(prompt, str) else "[NON_STRING REQUEST]"
    )
    try:
        return _run_agent_impl(prompt, trace_sink, failure_debug)
    except Exception:
        _write_failure_debug_trace(failure_debug)
        raise


def _run_agent_impl(
    prompt: str,
    trace_sink: TraceRecorder | None,
    failure_debug: _FailureDebugTrace,
) -> str:
    """Run the production L2 path with an optional additive trace observer."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise RuntimeError("L2 prompt must be a non-empty string")
    started = time.monotonic()
    deadline = started + CASE_DEADLINE_SECONDS
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    raw_response = _call_model(messages, deadline=deadline)
    payload = _parse_response_payload(raw_response)
    task_type = payload.get("task_type")
    _trace(
        trace_sink,
        stage="intent",
        executor="llm",
        status="ok",
        summary="模型已识别用户请求的任务类型。",
        data={"task_type": task_type, "llm_call": 1},
    )
    if payload.get("task_type") == "select_backend":
        constraints = _parse_backend_constraints(payload)
        _parse_explanation(payload)
        constraint_data = {
            "min_qubits": constraints.min_qubits,
            "require_qpu": constraints.require_qpu,
            "require_no_queue": constraints.require_no_queue,
            "cost_policy": constraints.cost_policy,
            "allow_account_required": constraints.allow_account_required,
        }
        _trace(
            trace_sink,
            stage="backend_constraints",
            executor="llm",
            status="ok",
            summary="模型已提取后端约束，尚未选择具体后端。",
            data={**constraint_data, "llm_call": 1},
        )
        matches = select_backends(constraints)
        backend_ids = [backend.id for backend in matches]
        _trace(
            trace_sink,
            stage="backend_selected",
            executor="local",
            status="ok" if matches else "warning",
            summary=(
                "本地能力表已筛选出符合条件的标准后端 ID。"
                if matches
                else "本地能力表中没有同时满足全部约束的后端。"
            ),
            data={"backend_ids": backend_ids, "no_match": not bool(matches)},
        )
        reply = _format_backend_reply(constraints, matches)
        _remaining_case_time(deadline)
        _trace(
            trace_sink,
            stage="agent_result",
            executor="local",
            status="ok",
            summary="后端选择已完成。",
            data={"task_type": "select_backend", "backend_ids": backend_ids},
        )
        return reply

    require_measurement = _requires_measurement(prompt)
    candidate = _parse_candidate_payload(payload)
    failure_debug.first_candidate_qasm = candidate.qasm
    failure_debug.failure_stage = "target_specification"
    pure_state_guard = requires_statevector_verification(prompt)
    _trace(
        trace_sink,
        stage="qasm_candidate",
        executor="llm",
        status="ok",
        summary="模型已生成候选 OpenQASM 程序。",
        data={
            "task_type": candidate.task_type,
            "qasm": candidate.qasm,
            "require_measurement": require_measurement,
            "pure_state_guard": pure_state_guard,
            "llm_call": 1,
        },
    )
    judge_messages = [
        {"role": "system", "content": TARGET_JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    target = _parse_target_judge_response(
        _call_model(judge_messages, deadline=deadline)
    )
    failure_debug.target_spec = target.as_prompt_payload()
    failure_debug.failure_stage = "first_verification"
    target_trace_data = target.as_prompt_payload()
    # 模型 explanation 不参与裁判，也不进入安全调试协议。
    target_trace_data.pop("explanation", None)
    _trace(
        trace_sink,
        stage="target_spec",
        executor="llm",
        status="ok",
        summary="独立目标裁判已提取待验证的目标态。",
        data={**target_trace_data, "llm_call": 2},
    )
    if pure_state_guard and target.verification_mode == "unsupported":
        raise RuntimeError(
            "L2 target judge cannot downgrade an explicit pure-state request"
        )
    repair_triggered = False
    try:
        generated = _verify_candidate(
            candidate,
            target,
            require_measurement=require_measurement,
            trace_sink=trace_sink,
        )
    except _CandidateVerificationError as first_error:
        failure_debug.first_diagnostic = first_error.diagnostic
        failure_debug.first_fidelity = first_error.fidelity
        failure_debug.failure_stage = "repair_generation"
        repair_triggered = True
        _trace(
            trace_sink,
            stage="repair_started",
            executor="llm",
            status="running",
            summary="候选未通过验证，开始唯一一次模型修复。",
            data={
                "llm_call": 3,
                "diagnostic": first_error.diagnostic,
                "fidelity": first_error.fidelity,
            },
        )
        repair_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _repair_prompt(
                    prompt,
                    candidate.qasm,
                    first_error.diagnostic,
                    target,
                    require_measurement=require_measurement,
                    fidelity=first_error.fidelity,
                ),
            },
        ]
        repair_response = _call_model(repair_messages, deadline=deadline)
        repaired_candidate = _parse_candidate_response(repair_response)
        failure_debug.repair_candidate_qasm = repaired_candidate.qasm
        failure_debug.failure_stage = "second_verification"
        _trace(
            trace_sink,
            stage="repair_candidate",
            executor="llm",
            status="ok",
            summary="模型已返回修复后的候选 QASM。",
            data={
                "task_type": repaired_candidate.task_type,
                "qasm": repaired_candidate.qasm,
                "llm_call": 3,
            },
        )
        try:
            generated = _verify_candidate(
                repaired_candidate,
                target,
                require_measurement=require_measurement,
                trace_sink=trace_sink,
            )
        except _CandidateVerificationError as second_error:
            failure_debug.second_diagnostic = second_error.diagnostic
            failure_debug.second_fidelity = second_error.fidelity
            raise RuntimeError(
                "model repair failed QASM semantic verification; repair limit reached"
            ) from None

    # 本地验证也属于同一个 case；超时后不能再返回看似成功的结果。
    _remaining_case_time(deadline)
    explanation = generated.explanation or "已生成并通过 OpenQASM 2.0 校验。"
    reply = "%s\n\n```qasm\n%s\n```" % (explanation, generated.qasm)
    _trace(
        trace_sink,
        stage="agent_result",
        executor="local",
        status="ok",
        summary="最终 OpenQASM 已通过验证，可以使用。",
        data={
            "task_type": generated.task_type,
            "qasm": generated.qasm,
            "repaired": repair_triggered,
        },
    )
    return reply


def agent_chat(prompt: str) -> str:
    """Preserve the official production signature with tracing disabled."""
    return _run_agent(prompt, trace_sink=None)


__all__ = [
    "CASE_DEADLINE_SECONDS",
    "GenerationResponse",
    "_run_agent",
    "agent_chat",
    "parse_generation_response",
    "requires_statevector_verification",
]
