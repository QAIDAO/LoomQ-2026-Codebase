#!/usr/bin/env python3
"""Web-only agent orchestration layer for QuantumHelper.

The competition core lives in ``adapter.py``: deterministic, contract-bound and
untouched by this module.  Everything the *web page* needs on top of it lives
here - intent routing, slot extraction, beginner defaults and general quantum
Q&A.

Contract (see QuantumHelper_WebAgent_系统修复任务书.md):

* the LLM only ever produces *structured* data - an intent label and slots;
* backend ids, QASM validation and run results always come from ``adapter``;
* ``unknown`` is never silently promoted to ``generate_circuit``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

APP_DIR = Path(__file__).resolve().parent
if (APP_DIR.parent / "adapter.py").is_file():
    STARTER_KIT_ROOT = APP_DIR.parent
elif (APP_DIR / "starter_kit" / "adapter.py").is_file():
    STARTER_KIT_ROOT = APP_DIR / "starter_kit"
elif (APP_DIR.parent / "starter_kit" / "adapter.py").is_file():
    STARTER_KIT_ROOT = APP_DIR.parent / "starter_kit"
else:  # pragma: no cover - mirrors server.py bootstrap
    raise RuntimeError("Cannot locate the LoomQ starter_kit adapter")
for _root in (str(STARTER_KIT_ROOT.parent), str(STARTER_KIT_ROOT)):
    if _root not in sys.path:
        sys.path.insert(0, _root)

try:
    from starter_kit import adapter  # type: ignore  # noqa: E402
except ModuleNotFoundError as exc:  # extracted submission root has no outer package
    if exc.name != "starter_kit":
        raise
    import adapter  # type: ignore  # noqa: E402

try:  # Wave 3: QASM extraction and runtime config live in their own modules.
    from . import qasm_extract, runtime_config  # type: ignore  # noqa: E402
except ImportError:  # web_agent.py executed directly as a script
    import qasm_extract, runtime_config  # type: ignore  # noqa: E402


# --------------------------------------------------------------------------
# Taxonomy (任务书 §4 / §26)
# --------------------------------------------------------------------------

INTENTS = (
    "generate_circuit",
    "modify_current_task",
    "diagnose_circuit",
    "repair_circuit",
    "edit_current_qasm",
    "validate_circuit",
    "select_backend",
    "explain_current_circuit",
    "explain_result",
    "quantum_qa",
    "scenario_help",
    "run_circuit",
    "unknown",
)

#: Intents the LLM classifier is allowed to return.  ``unknown`` stays legal so
#: the model can admit defeat instead of guessing ``generate_circuit``.
LLM_INTENTS = frozenset(INTENTS)

ERROR_CODES = (
    "INTENT_UNCLEAR",
    "MISSING_REQUIRED_INFO",
    "QASM_PARSE_ERROR",
    "QASM_UNSUPPORTED_GATE",
    "QASM_VALIDATION_ERROR",
    "SEMANTIC_MISMATCH",
    "BACKEND_NO_EXACT_MATCH",
    "LLM_NOT_CONFIGURED",
    "LLM_REQUEST_FAILED",
    "RUN_FAILED",
)

#: Target states ``adapter`` can actually build.  Anything outside this set must
#: not be promised to the user (任务书 §40.13).
SUPPORTED_GOALS = frozenset(adapter.L2_NAMED_OPERATIONS) | {"superposition"}

#: 第二轮/第三轮 §9/§11：由 LLM 输出的语义字段合法取值（规则层不硬编码）。
QUESTION_TYPES = (
    "gate_definition",
    "gate_role_in_current_circuit",
    "state_explanation",
    "result_pattern",
    "measurement_explanation",
    "shots_explanation",
    "backend_explanation",
    "current_result_explanation",
    "current_step_explanation",
    "general_quantum_question",
    "unknown",
)
SCOPES = (
    "continue_current_task",
    "new_task",
    "inspect_external_code",
    "general_question",
)


# --------------------------------------------------------------------------
# Gate vocabulary - reused from adapter, never re-hardcoded (任务书 §16).
# QASM extraction itself now lives in qasm_extract (Wave 3); the word list below
# is only used by _mentioned_gate to answer "which gate are they asking about".
# --------------------------------------------------------------------------

_GATE_ALIASES: dict[str, str] = dict(getattr(adapter, "_REPAIR_GATE_ALIASES", {}))
_GATE_WORDS = sorted(
    set(adapter.L2_ALLOWED_GATES) | set(_GATE_ALIASES),
    key=len,
    reverse=True,
)


# --------------------------------------------------------------------------
# Rule vocabulary
# --------------------------------------------------------------------------

#: 修复类（任务书 §5.1 明确列出的确定性 fast-path：QASM + 报错/修复/fix/error）。
#: 其余语义细分（诊断/校验/编辑/问什么类型）一律交给 LLM，不在这里枚举短语。
_REPAIR_WORDS = re.compile(
    r"报错|修复|修好|修一下|帮我修|纠错|改正|"
    r"\bfix\b|\brepair\b|\berror\b|\bdebug\b|\bbroken\b",
    re.IGNORECASE,
)
_BACKEND_WORDS = re.compile(
    r"后端|平台|真机|实机|硬件|模拟器|仿真器|排队|队列|免费|收费|付费|账号|账户|"
    r"注册|运行环境|执行环境|设备|\bbackend\b|\bqpu\b|\bsimulator\b|\bhardware\b|\bqueue\b",
    re.IGNORECASE,
)
#: "我要真机" / "帮我选后端" - asking for a choice, not asking what it means.
_BACKEND_REQUEST_WORDS = re.compile(
    r"我要|我想要|需要|选(?:择|一个|个)?|推荐|帮我|换成|换到|用哪|哪个|哪家|跑在|运行在|"
    r"\bselect\b|\bchoose\b|\brecommend\b",
    re.IGNORECASE,
)
_QUESTION_WORDS = re.compile(
    r"是什么|什么意思|啥意思|干嘛|干什么|干啥|作用|用来|为什么|为啥|怎么理解|如何理解|"
    r"解释|讲讲|说说|介绍|区别|差别|不一样|原理|懂|通俗|小白|外行|\?|？|"
    r"\bwhat\b|\bwhy\b|\bhow\b|\bexplain\b|\bdifference\b",
    re.IGNORECASE,
)
_GENERATE_WORDS = re.compile(
    r"生成|做(?:一)?个|做一条|弄(?:一)?个|来(?:一)?个|给我(?:一|做|弄|来)|制备|构建|创建|"
    r"搭(?:一)?个|写(?:一)?个|画(?:一)?个|演示|示例|例子|\bgenerate\b|\bcreate\b|\bbuild\b|\bmake\b",
    re.IGNORECASE,
)
_CIRCUIT_WORDS = re.compile(
    r"线路|电路|circuit|量子门|态\b|贝尔|bell|ghz|qft|纠缠|叠加|entangle|superposition",
    re.IGNORECASE,
)
_RUN_WORDS = re.compile(
    r"运行|执行|跑(?:一下|一次|起来)?|开始跑|\brun\b|\bexecute\b",
    re.IGNORECASE,
)
_RESULT_WORDS = re.compile(
    r"结果|分布|counts|柱状|直方|概率|这些数|测量出来",
    re.IGNORECASE,
)
_SHOTS_WORDS = re.compile(
    r"\bshots?\b|运行次数|执行次数|重复(?:运行|执行|测量)|跑(?:多少|几|一)次",
    re.IGNORECASE,
)
_STATE_WORDS = re.compile(r"\bbell\b|贝尔态|\bghz\b|纠缠态|叠加态|量子态", re.IGNORECASE)
_RESULT_PATTERN_WORDS = re.compile(
    r"(?:看到|出现|得到|测到|输出).*(?:[01]{2,}|结果)|"
    r"(?:[01]{2,}).*(?:看到|出现|得到|测到|输出|为什么)|"
    r"通常|总是|主要得到|概率分布",
    re.IGNORECASE,
)
_CURRENT_RESULT_WORDS = re.compile(
    r"这个结果|这次结果|当前结果|为什么这次|这些结果|刚好\s*50\s*(?:/|：|比)\s*50|50\s*%",
    re.IGNORECASE,
)
_GATE_ROLE_WORDS = re.compile(
    r"为什么.*(?:用|需要|放|先)|(?:这里|当前|这个|这一步|线路中|电路中).*(?:作用|用|门)|"
    r"(?:作用|角色).*(?:这里|当前|线路|电路)",
    re.IGNORECASE,
)
_DEFINITION_WORDS = re.compile(
    r"是什么|什么意思|干嘛|干什么|干啥|作用是什么|用来做什么|介绍一下|讲讲",
    re.IGNORECASE,
)
_MODIFY_WORDS = re.compile(
    r"改成|改为|换成|变成|调整为|增加到|减少到|改到",
    re.IGNORECASE,
)
_NO_FORMULA_WORDS = re.compile(
    r"别给我公式|不要公式|别讲公式|不用公式|别用数学|不要矩阵|别给我矩阵|"
    r"通俗|大白话|说人话|别太专业|不要太专业",
    re.IGNORECASE,
)
_SIMPLE_WORDS = re.compile(
    r"最简单|简单|入门|新手|小白|初学|第一次|看得懂|看懂|不要太复杂|别太复杂|基础",
    re.IGNORECASE,
)

_SCENARIO_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("search", re.compile(r"查找|搜索|候选|找到它|找出|从.*中找|\bsearch\b|\bgrover\b", re.IGNORECASE)),
    ("optimization", re.compile(r"优化|排程|排班|调度|冲突更少|路线|资源分配|方案.*选|\boptimi[sz]|\bqaoa\b", re.IGNORECASE)),
    ("measurement", re.compile(r"重复运行|不同(?:的)?(?:测量)?结果|出现的次数|测量分布|多次测量", re.IGNORECASE)),
    ("correlation", re.compile(r"关联|纠缠|bell|贝尔|两个量子比特.*(?:关联|一致)", re.IGNORECASE)),
)

#: A scenario *card* reads like "做一个实验/演示，看看会发生什么".  This
#: disambiguates it from a bare circuit request ("生成一个 4 比特 GHZ 态").
_SCENARIO_SIGNAL = re.compile(
    r"实验|演示|看看|观察|对比|从中选|试一下|试一试|会(?:怎样|发生什么|出现)",
    re.IGNORECASE,
)

_CHINESE_NUMERALS = {
    "一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


# --------------------------------------------------------------------------
# Route
# --------------------------------------------------------------------------


@dataclass
class Route:
    """The result of routing one user turn.

    ``source`` records *how* the intent was decided so the debug panel and the
    server log can tell a deterministic hit from an LLM guess (任务书 §33).
    """

    intent: str
    confidence: float
    source: str  # "rule" | "llm" | "fallback"
    reason: str
    requires_clarification: bool = False
    slots: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    scenario_id: str | None = None
    # 第二轮 §5/§7/§13：更细的语义标注，让 QA 不再答非所问、让多轮不再串任务。
    question_type: str | None = None      # gate_definition / result_pattern / shots_explanation / ...
    conversation_scope: str | None = None  # continue_current_task / new_task / general_question
    contains_qasm: bool = False

    def __post_init__(self) -> None:
        if self.intent not in INTENTS:
            raise ValueError(f"unknown intent: {self.intent!r}")

    def to_debug(self) -> dict[str, Any]:
        """Payload for ``?debug=1`` - never contains credentials."""
        return {
            "intent": self.intent,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "reason": self.reason,
            "requires_clarification": self.requires_clarification,
            "slots": dict(self.slots),
            "assumptions": list(self.assumptions),
            "scenario_id": self.scenario_id,
            "question_type": self.question_type,
            "conversation_scope": self.conversation_scope,
            "contains_qasm": self.contains_qasm,
        }


# --------------------------------------------------------------------------
# QASM extraction (任务书 §15)
# --------------------------------------------------------------------------


def looks_like_qasm(text: str) -> bool:
    """True when *text* carries QASM statements rather than prose alone."""
    return qasm_extract.looks_like_qasm(text)


def extract_qasm_from_prompt(prompt: str) -> str | None:
    """Pull the code out of a mixed prose+code prompt (任务书 §15)."""
    return qasm_extract.extract_qasm_from_prompt(prompt)


def extract_goal(prompt: str) -> str | None:
    """Best-effort named target state, restricted to what adapter can build."""
    return qasm_extract.extract_goal(prompt)


def extract_qubits(prompt: str) -> int | None:
    """Explicit qubit count, e.g. "3 比特" / "三个量子比特"."""
    digits = re.search(r"(\d+)\s*(?:个)?\s*(?:量子)?(?:比特|位|qubits?)", prompt, re.IGNORECASE)
    if digits:
        return int(digits.group(1))
    chinese = re.search(
        r"([一两二三四五六七八九十])\s*(?:个)?\s*(?:量子)?(?:比特|位)", prompt
    )
    if chinese:
        return _CHINESE_NUMERALS[chinese.group(1)]
    return None


# --------------------------------------------------------------------------
# Deterministic fast path (任务书 §5.1)
# --------------------------------------------------------------------------


def _has_current_circuit(context: dict | None) -> bool:
    return bool(context and context.get("current_qasm"))


def _has_result(context: dict | None) -> bool:
    return bool(context and context.get("result"))


def classify_by_rules(prompt: str, context: dict | None = None) -> Route | None:
    """Return a Route for *structurally* unambiguous input, else ``None``.

    只负责确定性/结构信号（§5.1）；语义细分（诊断/校验/编辑、question_type、
    conversation_scope）一律交给 LLM，不在这里枚举短语硬编码。
    """
    text = prompt.strip()

    # 1. QASM 优先（§7/§8）：输入带了 QASM 结构，只有明确「修复」走规则 fast-path；
    #    诊断/校验/编辑是语义判断 → 返回 None 交给 LLM 分类。
    if looks_like_qasm(text):
        if _REPAIR_WORDS.search(text):
            return Route(
                intent="repair_circuit",
                confidence=0.96,
                source="rule",
                reason="输入同时包含 QASM 语句和报错/修复关键词",
                contains_qasm=True,
                conversation_scope="inspect_external_code",
                slots={
                    "source_qasm": extract_qasm_from_prompt(text),
                    "goal": extract_goal(text),
                },
            )
        return None

    # 2. Backend - asking to *pick* an execution environment (structural keywords).
    if _BACKEND_WORDS.search(text) and _BACKEND_REQUEST_WORDS.search(text) and not _is_conceptual_question(text):
        return Route(
            intent="select_backend",
            confidence=0.93,
            source="rule",
            reason="输入在挑选执行环境（后端关键词 + 请求语气）",
        )

    # 3. Questions: classify the user's explicit subject before consulting
    # current circuit/result context. Context may select a handler, but it may
    # never turn an unrelated question into a gate explanation.
    if _QUESTION_WORDS.search(text) and not _GENERATE_WORDS.search(text):
        question_type, explicit_subject = classify_qa_question(text, context)
        common_slots = {
            "explicit_subject": explicit_subject,
            "no_formula": bool(_NO_FORMULA_WORDS.search(text)),
        }
        if question_type == "current_result_explanation" and _has_result(context):
            return Route(
                intent="explain_result",
                confidence=0.9,
                source="rule",
                reason="用户明确询问当前运行结果",
                question_type=question_type,
                conversation_scope="continue_current_task",
                slots=common_slots,
            )
        if question_type == "gate_role_in_current_circuit" and _has_current_circuit(context):
            return Route(
                intent="explain_current_circuit",
                confidence=0.88,
                source="rule",
                reason="用户明确询问某个门在当前线路中的作用",
                question_type=question_type,
                conversation_scope="continue_current_task",
                slots={
                    **common_slots,
                    "gate": _mentioned_gate(text),
                },
            )
        return Route(
            intent="quantum_qa",
            confidence=0.88,
            source="rule",
            reason="根据用户问题本身识别量子问答类型",
            question_type=question_type,
            conversation_scope="general_question",
            slots={**common_slots, "topic": _qa_topic(text)},
        )

    # 4. Measurement-scope follow-up (纯结构：只改测量范围)。
    if _has_current_circuit(context) and re.fullmatch(
        r"\s*(?:请)?(?:改成)?(?:只?测量|不要测量|不测量|全部测量|全测量).*?[。.!！]?\s*",
        text,
        re.IGNORECASE,
    ):
        return Route(
            intent="modify_current_task",
            confidence=0.95,
            source="rule",
            reason="已有当前线路，且用户只要求修改测量范围",
            conversation_scope="continue_current_task",
            slots={"measurement_only": True},
        )

    # 5. Modify the current task - "改成 N 比特"（结构：已有线路 + 修改动词）。
    if _has_current_circuit(context) and _MODIFY_WORDS.search(text):
        return Route(
            intent="modify_current_task",
            confidence=0.9,
            source="rule",
            reason="已有当前线路，且用户要求修改参数",
            conversation_scope="continue_current_task",
            slots={"qubits": extract_qubits(text)},
        )

    # 6. Run the current circuit.
    if _has_current_circuit(context) and _RUN_WORDS.search(text) and not _GENERATE_WORDS.search(text):
        return Route(
            intent="run_circuit",
            confidence=0.87,
            source="rule",
            reason="已有当前线路，且用户要求执行",
            conversation_scope="continue_current_task",
        )

    # 7. Scenario prose from the home page cards (§8).
    scenario = detect_scenario(text)
    if scenario and _SCENARIO_SIGNAL.search(text):
        return Route(
            intent="scenario_help",
            confidence=0.82,
            source="rule",
            reason=f"输入匹配 {scenario} 场景描述",
            scenario_id=scenario,
            conversation_scope="new_task",
        )

    # 8. Generation - an explicit ask for a circuit.
    if _GENERATE_WORDS.search(text) and (_CIRCUIT_WORDS.search(text) or _SIMPLE_WORDS.search(text)):
        return _generation_route(text)

    # 9. Concept Q&A fallback for less explicit question wording (§7).
    if _is_conceptual_question(text):
        question_type, explicit_subject = classify_qa_question(text, context)
        return Route(
            intent="quantum_qa",
            confidence=0.85,
            source="rule",
            reason="用户在询问概念，不是在请求生成线路",
            question_type=question_type,
            conversation_scope="general_question",
            slots={
                "topic": _qa_topic(text),
                "explicit_subject": explicit_subject,
                "no_formula": bool(_NO_FORMULA_WORDS.search(text)),
            },
        )

    # 10. Scenario fallback (weaker match).
    if scenario:
        return Route(
            intent="scenario_help",
            confidence=0.7,
            source="rule",
            reason=f"输入匹配 {scenario} 场景描述",
            scenario_id=scenario,
            conversation_scope="new_task",
        )

    return None


def _is_conceptual_question(text: str) -> bool:
    """A question about meaning, with no request to build anything."""
    if not _QUESTION_WORDS.search(text):
        return False
    if _GENERATE_WORDS.search(text) and _CIRCUIT_WORDS.search(text):
        return False
    return True


def explicit_qa_subject(text: str) -> str | None:
    """Extract a subject from the user message only, never from context."""
    gate = _mentioned_gate(text)
    if gate:
        return f"{gate}_gate"
    if _SHOTS_WORDS.search(text):
        return "shots"
    if re.search(r"\bbell\b|贝尔态", text, re.IGNORECASE):
        return "bell_state"
    if re.search(r"\bghz\b", text, re.IGNORECASE):
        return "ghz_state"
    if re.search(r"模拟器|仿真器|真机|实机|量子硬件", text, re.IGNORECASE):
        return "backend"
    if re.search(r"测量|坍缩", text, re.IGNORECASE):
        return "measurement"
    if _CURRENT_RESULT_WORDS.search(text):
        return "current_result"
    return None


def classify_qa_question(text: str, context: dict | None = None) -> tuple[str, str | None]:
    """Classify QA semantics with user text taking priority over context."""
    subject = explicit_qa_subject(text)
    gate = _mentioned_gate(text)
    if gate and _GATE_ROLE_WORDS.search(text):
        return "gate_role_in_current_circuit", subject
    if gate and _DEFINITION_WORDS.search(text):
        return "gate_definition", subject
    if _SHOTS_WORDS.search(text):
        return "shots_explanation", "shots"
    if re.search(r"模拟器|仿真器|真机|实机|量子硬件", text, re.IGNORECASE):
        return "backend_explanation", "backend"
    if _STATE_WORDS.search(text) and _RESULT_PATTERN_WORDS.search(text):
        return "result_pattern", subject
    if _has_result(context) and (_CURRENT_RESULT_WORDS.search(text) or _RESULT_WORDS.search(text)):
        return "current_result_explanation", subject or "current_result"
    if re.search(r"测量|坍缩", text, re.IGNORECASE):
        return "measurement_explanation", subject or "measurement"
    if _STATE_WORDS.search(text):
        return "state_explanation", subject
    return "general_quantum_question", subject


def _infer_scope(intent: str) -> str:
    """从 intent 推断会话范围（§11）。仅用于规则命中的结构场景；语义 scope 由 LLM 提供。"""
    if intent in {"generate_circuit", "scenario_help", "select_backend"}:
        return "new_task"
    if intent in {"modify_current_task", "edit_current_qasm", "explain_current_circuit", "explain_result", "run_circuit"}:
        return "continue_current_task"
    if intent in {"diagnose_circuit", "repair_circuit", "validate_circuit"}:
        return "inspect_external_code"
    return "general_question"


def _mentioned_gate(text: str) -> str | None:
    for name in _GATE_WORDS:
        if re.search(rf"(?<![a-z0-9_]){re.escape(name)}(?![a-z0-9_])", text, re.IGNORECASE):
            return _GATE_ALIASES.get(name.lower(), name.lower())
    return None


def detect_scenario(text: str) -> str | None:
    for scenario_id, pattern in _SCENARIO_PATTERNS:
        if pattern.search(text):
            return scenario_id
    return None


# --------------------------------------------------------------------------
# Generation slots and beginner defaults (任务书 §6 / §30)
# --------------------------------------------------------------------------


def _generation_route(text: str) -> Route:
    """Decide whether we can build something, or must ask one question."""
    goal = extract_goal(text)
    qubits = extract_qubits(text)
    assumptions: list[str] = []

    # 6.2 - an optimization circuit with no problem class is genuinely
    # under-specified.  Ask exactly one question instead of guessing.
    if goal is None and re.search(r"优化|optimi[sz]", text, re.IGNORECASE):
        return Route(
            intent="generate_circuit",
            confidence=0.7,
            source="rule",
            reason="用户要优化线路，但没有说优化对象",
            requires_clarification=True,
            slots={
                "goal": None,
                "clarification": "可以。你想优化的是哪一类问题？例如路线、排程还是资源分配？",
            },
        )

    if goal == "bell":
        qubits = 2
        if _SIMPLE_WORDS.search(text) or extract_qubits(text) is None:
            assumptions.append("使用 2 个量子比特")
            assumptions.append("默认测量全部量子比特")
    elif goal is None and _SIMPLE_WORDS.search(text):
        # 30 - "给我弄个新手能看懂的量子线路" must not demand a qubit count.
        goal = "superposition"
        qubits = 1
        assumptions.append("使用 1 个量子比特的叠加与测量作为第一条线路")
        assumptions.append("默认测量全部量子比特")
    elif goal in {"ghz", "qft"} and qubits is None:
        return Route(
            intent="generate_circuit",
            confidence=0.75,
            source="rule",
            reason=f"目标是 {goal}，但没有给出量子比特数",
            requires_clarification=True,
            slots={
                "goal": goal,
                "clarification": f"好的，做一个 {goal.upper()} 态。你想用几个量子比特？",
            },
        )

    if goal is None:
        return Route(
            intent="generate_circuit",
            confidence=0.6,
            source="rule",
            reason="用户要生成线路，但没有可识别的目标态",
            requires_clarification=True,
            slots={
                "goal": None,
                "clarification": "你想先看哪一种线路？例如叠加与测量、两比特纠缠（Bell），或多比特 GHZ。",
            },
        )

    return Route(
        intent="generate_circuit",
        confidence=0.92,
        source="rule",
        reason=f"用户请求生成 {goal} 线路",
        # ``measurement`` is only asserted when *we* defaulted it.  When the
        # user spelled out a partial scope ("只测量前两个"), we leave it None so
        # the server's explicit measurement parser stays the single source of
        # truth instead of two places disagreeing.
        slots={
            "goal": goal,
            "qubits": qubits,
            "measurement": "all" if assumptions else _measurement_hint(text),
        },
        assumptions=assumptions,
    )


def _measurement_hint(text: str) -> str | None:
    """Coarse measurement scope, or None when the server must work it out."""
    if re.search(r"不(?:要|进行)?测量|no\s+measure", text, re.IGNORECASE):
        return "none"
    if re.search(r"全部测量|全测量|测量全部|measure\s+all", text, re.IGNORECASE):
        return "all"
    if re.search(r"只测量|仅测量", text):
        return None  # partial - the server parses the exact pairs
    return None


# --------------------------------------------------------------------------
# LLM classification (任务书 §5.2 / §31)
# --------------------------------------------------------------------------

_CLASSIFIER_SYSTEM = """你是量子计算网页助手的意图分类器。只输出一个 JSON 对象，不要输出任何解释文字或 Markdown 代码块。

字段：
  intent: 必须是以下之一 %s
  confidence: 0 到 1 的小数
  requires_clarification: 布尔值
  reason: 一句中文，说明判断依据
  question_type: 仅当 intent 是 quantum_qa / explain_current_circuit / explain_result 时填，取值之一：
      gate_definition / gate_role_in_current_circuit / state_explanation / result_pattern /
      measurement_explanation / shots_explanation / backend_explanation /
      current_result_explanation / current_step_explanation / general_quantum_question / unknown；
      其它 intent 填 null
  explicit_subject: 用户原话明确询问的对象，例如 h_gate / bell_state / shots / backend；
      不得从当前线路中的第一个门推断。没有明确对象时填 null
  conversation_scope: 取值之一 continue_current_task / new_task / inspect_external_code / general_question

判断要点：
- 用户贴了 OpenQASM 代码（含 qreg/creg/h q[..]/cx 等）：
    * 明确说"修复/帮我修/报错了" → repair_circuit
    * 问"为什么不行/哪里错/怎么回事"（只想知道原因）→ diagnose_circuit
    * 问"这能运行吗/这对吗/正确吗"（只判断对错）→ validate_circuit
    * 要求直接改代码里的具体记号（把 q[1] 改成 q[0]、删掉分号、把某行改成…）→ edit_current_qasm
- 用户要生成一条新线路 → generate_circuit
- 用户要改当前任务的参数（改成 N 比特、只测量…）→ modify_current_task
- 用户在挑选运行环境 → select_backend
- 用户在问概念或当前线路/结果 → quantum_qa / explain_current_circuit / explain_result
- 用户描述的是一类现实问题（查找/优化/测量/关联）→ scenario_help
- question_type：只问"X 是什么"→ gate_definition；问"为什么这里用 X/为什么结果这样"→ gate_role_in_current_circuit 或 result_pattern；不要因为线路里有 X 就答 X 的定义。
- shots/运行次数问题 → shots_explanation；模拟器与真机概念 → backend_explanation；
  "这个结果/这次为什么不是 50/50" → current_result_explanation。
- conversation_scope：改/解释当前线路 → continue_current_task；重新来一个例子/新生成 → new_task；检查用户刚粘贴的外部代码 → inspect_external_code；纯概念提问 → general_question。
- 你无法判断 → unknown，不要因为拿不准就选 generate_circuit。
""" % (", ".join(INTENTS),)


class LLMNotConfigured(RuntimeError):
    """Raised when no model service is reachable for classification."""


def _chat_completion() -> Callable[..., dict]:
    """The organizer's OpenAI-compatible transport, under either layout."""
    try:
        from starter_kit.llm_client import chat_completion  # noqa: PLC0415
    except ModuleNotFoundError:  # extracted submission root has no outer package
        from llm_client import chat_completion  # type: ignore  # noqa: PLC0415
    return chat_completion


def _runtime_completion() -> Callable[..., dict] | None:
    """Return a completion callable honouring runtime config, or None.

    ``llm_client.chat_completion`` normally reads ``LOOMQ_LLM_*`` from the
    environment. A web-saved runtime value uses a request-local ContextVar
    override, never process-global environment mutation.
    Returns None when no runtime config is set (so the caller falls back to the
    plain environment-backed transport).
    """
    cfg = runtime_config.get_runtime_config()
    resolved = cfg.resolve()
    if resolved is None:
        return None
    if cfg.effective()["source"] != runtime_config.SOURCE_RUNTIME:
        return None  # env-backed; no injection needed

    return runtime_config.completion_for_config(cfg)


def llm_enabled() -> bool:
    """Whether the web user or deployer explicitly enabled model access."""
    effective = runtime_config.get_runtime_config().effective()
    # Saving a runtime config in the local configuration page is itself an
    # explicit opt-in. Environment/deployment credentials retain the separate
    # quota-protection switch.
    return (
        effective["source"] == runtime_config.SOURCE_RUNTIME
        or os.getenv("QUANTUMHELPER_ENABLE_LLM") == "1"
    )


def llm_available() -> bool:
    """True when a model service is configured for the web layer.

    Priority runtime config -> environment variables (任务书 §19).  The
    ``QUANTUMHELPER_ENABLE_LLM`` gate must still be on.
    """
    if not llm_enabled():
        return False
    return runtime_config.get_runtime_config().resolve() is not None


def classify_by_llm(
    prompt: str,
    context: dict | None = None,
    *,
    completion: Callable[..., dict] | None = None,
) -> Route:
    """Ask the model for a structured intent label.

    The model never returns free text we then regex - it returns JSON we
    validate against the taxonomy, and anything malformed becomes ``unknown``.
    """
    if completion is None:
        if not llm_available():
            raise LLMNotConfigured("模型服务尚未配置")
        completion = _runtime_completion() or _chat_completion()

    hints = []
    if _has_current_circuit(context):
        hints.append("当前已有一条已验证线路")
    if _has_result(context):
        hints.append("当前已有一次运行结果")
    user_content = prompt if not hints else f"[上下文：{'；'.join(hints)}]\n{prompt}"

    response = completion([
        {"role": "system", "content": _CLASSIFIER_SYSTEM},
        {"role": "user", "content": user_content},
    ])
    return _route_from_llm_payload(response)


def _route_from_llm_payload(response: Any) -> Route:
    """Validate the model reply; never let malformed JSON reach the adapter."""
    try:
        content = response["choices"][0]["message"]["content"]
    except (TypeError, KeyError, IndexError):
        return _unknown_route("模型返回结构无法解析", source="llm")

    data = _loads_json_object(content)
    if data is None:
        return _unknown_route("模型没有返回合法 JSON", source="llm")

    intent = data.get("intent")
    if not isinstance(intent, str) or intent not in LLM_INTENTS:
        return _unknown_route(f"模型返回了未知 intent: {intent!r}", source="llm")

    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        confidence = 0.5
    confidence = max(0.0, min(1.0, float(confidence)))

    reason = data.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = "模型未给出判断理由"

    question_type = data.get("question_type")
    if not isinstance(question_type, str) or question_type not in QUESTION_TYPES:
        question_type = None

    explicit_subject = data.get("explicit_subject")
    if not isinstance(explicit_subject, str) or not explicit_subject.strip():
        explicit_subject = None
    elif len(explicit_subject) > 80:
        explicit_subject = explicit_subject[:80]

    scope = data.get("conversation_scope")
    if not isinstance(scope, str) or scope not in SCOPES:
        scope = None

    return Route(
        intent=intent,
        confidence=confidence,
        source="llm",
        reason=reason.strip()[:200],
        requires_clarification=bool(data.get("requires_clarification")),
        question_type=question_type,
        conversation_scope=scope,
        slots={"explicit_subject": explicit_subject},
    )


def _loads_json_object(content: Any) -> dict | None:
    if not isinstance(content, str):
        return None
    text = content.strip()
    # 剥掉 ```json / ``` 围栏（LLM 常会把结构化输出包进代码块）。
    fenced = re.search(r"```(?:json|JSON)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        text = text[start:end + 1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _unknown_route(reason: str, *, source: str = "fallback") -> Route:
    return Route(
        intent="unknown",
        confidence=0.0,
        source=source,
        reason=reason,
        requires_clarification=True,
    )


# --------------------------------------------------------------------------
# Public routing entry point
# --------------------------------------------------------------------------


def route(
    prompt: str,
    context: dict | None = None,
    *,
    scenario_id: str | None = None,
    completion: Callable[..., dict] | None = None,
    allow_llm: bool = True,
) -> Route:
    """Route one user turn to exactly one intent.

    Rules first, model second, ``unknown`` last.  ``unknown`` is a terminal
    answer - it is never rewritten into ``generate_circuit`` (任务书 §4/§40.2).
    """
    if scenario_id:
        return Route(
            intent="scenario_help",
            confidence=1.0,
            source="rule",
            reason="前端明确指定了场景卡",
            scenario_id=scenario_id,
            conversation_scope="new_task",
        )

    decided = classify_by_rules(prompt, context)
    if decided is not None:
        if decided.conversation_scope is None:
            decided.conversation_scope = _infer_scope(decided.intent)
        return decided

    if allow_llm:
        try:
            return classify_by_llm(prompt, context, completion=completion)
        except LLMNotConfigured:
            # 含 QASM 但无模型分类时，退化为确定性校验（不猜诊断/编辑/修复）。
            if looks_like_qasm(prompt):
                return Route(
                    intent="validate_circuit",
                    confidence=0.5,
                    source="fallback",
                    reason="输入含 QASM，但无模型分类，退化为确定性校验",
                    contains_qasm=True,
                    conversation_scope="inspect_external_code",
                    slots={"source_qasm": extract_qasm_from_prompt(prompt)},
                )
            return _unknown_route("规则无法判断，且模型服务尚未配置")
        except Exception as exc:  # transport failure must not become a circuit
            return _unknown_route(f"规则无法判断，且模型调用失败：{type(exc).__name__}")

    return _unknown_route("规则无法判断，且当前禁用了模型分类")


# --------------------------------------------------------------------------
# Curated beginner Q&A (任务书 §7)
# --------------------------------------------------------------------------

#: Deterministic answers for the handful of concepts a beginner hits first.
#: Used when no model is configured, so the page degrades to something useful
#: instead of demanding a qubit count.
_CURATED_QA: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "h_gate",
        re.compile(r"(?<![a-z])h(?:\s*门|adamard)|阿达马|哈达玛", re.IGNORECASE),
        "H 门（Hadamard）把一个量子比特从确定的 0 变成「一半可能是 0、一半可能是 1」的叠加状态。\n\n"
        "可以这样理解：测量之前它没有确定答案，测量之后才随机落到 0 或 1；"
        "重复运行很多次，你会看到大约各占一半。\n\n"
        "它几乎是每条量子线路的第一步——先制造可能性，后面的门再在这些可能性上做文章。",
    ),
    (
        "cx_gate",
        re.compile(r"(?<![a-z])(?:cx|cnot)(?![a-z])|受控非|控制非", re.IGNORECASE),
        "CX 门（也叫 CNOT）有一个控制比特和一个目标比特：控制比特是 1 时，翻转目标比特；是 0 时什么都不做。\n\n"
        "它的价值在于把两个量子比特绑在一起。如果控制比特处于叠加状态，"
        "CX 之后两个比特的结果就会互相关联——这正是纠缠的来源。",
    ),
    (
        "x_gate",
        re.compile(r"(?<![a-z])x\s*门(?![a-z])|泡利\s*x", re.IGNORECASE),
        "X 门（Pauli-X）会把量子比特的 0 和 1 对调：输入是 0 就变成 1，输入是 1 就变成 0。\n\n"
        "它很像经典计算里的 NOT 操作，常用来准备确定的 1 状态或翻转某个计算基状态。",
    ),
    (
        "entanglement",
        re.compile(r"纠缠|entangle|贝尔态|bell\s*state", re.IGNORECASE),
        "纠缠是指两个量子比特的测量结果绑定在一起：单看每一个都是随机的，但它们之间总是保持某种固定关系。\n\n"
        "最常见的例子是 Bell 态：两个比特要么同时是 00，要么同时是 11，几乎不会出现 01 或 10。"
        "你测量第一个得到 0，就能立刻知道第二个也是 0——哪怕你还没测它。",
    ),
    (
        "superposition",
        re.compile(r"叠加|superposition", re.IGNORECASE),
        "叠加是指一个量子比特在被测量之前，同时保留「是 0」和「是 1」两种可能。\n\n"
        "注意它不是「其实是 0 或 1，只是我们不知道」，而是两种可能确实同时存在，"
        "直到测量时才随机坍缩成其中一个。这是量子和经典比特最根本的差别。",
    ),
    (
        "shots",
        re.compile(r"\bshots?\b|重复运行|运行次数|跑多少次", re.IGNORECASE),
        "shots 就是同一条线路重复运行的次数。\n\n"
        "因为量子测量本身是随机的，跑一次只能拿到一个结果，看不出规律。"
        "跑 1024 次再统计每种结果出现多少回，才能看到真正的概率分布。\n\n"
        "shots 越大，统计越稳定，耗时也越长。",
    ),
    (
        "hardware_vs_simulator",
        re.compile(r"真机.*模拟器|模拟器.*真机|真机和|硬件.*模拟", re.IGNORECASE),
        "模拟器是用普通计算机算出量子线路「应该」得到什么结果：快、免费、随时可用，结果干净没有噪声。\n\n"
        "真机是真正的量子硬件：结果会带有真实噪声和误差，通常需要注册账号、排队等待，"
        "可用比特数也有限。\n\n"
        "学习和调试用模拟器，验证真实器件表现才需要真机。",
    ),
    (
        "measurement",
        re.compile(r"测量.*(?:是什么|什么意思|干嘛|作用)|什么是测量|坍缩", re.IGNORECASE),
        "测量就是读取量子比特，把它从叠加状态逼成一个确定的 0 或 1，这个过程叫坍缩。\n\n"
        "关键点是测量不可逆：一旦测了，原来的叠加就没了。所以测量通常放在线路最后。\n\n"
        "同一条线路重复测量很多次，统计出来的分布才是你真正要看的东西。",
    ),
    (
        "qubit",
        re.compile(r"量子比特|qubit|什么是比特", re.IGNORECASE),
        "量子比特是量子计算的基本单位。经典比特只能是 0 或 1，"
        "量子比特可以处于 0 和 1 的叠加中。\n\n"
        "更重要的是多个量子比特可以纠缠，产生经典比特无法表达的关联。"
        "n 个量子比特能同时表示 2ⁿ 种可能的组合，这是量子计算潜力的来源。",
    ),
    (
        "ghz",
        re.compile(r"\bghz\b", re.IGNORECASE),
        "GHZ 态是 Bell 态的多比特版本：三个或更多量子比特全部绑定在一起，"
        "测量结果要么全是 0，要么全是 1。\n\n"
        "做法也很直接：先用 H 门让第一个比特进入叠加，再用一串 CX 把这个叠加"
        "依次传递给其余比特。",
    ),
)


def _qa_topic(text: str) -> str | None:
    for topic, pattern, _answer in _CURATED_QA:
        if pattern.search(text):
            return topic
    return None


def curated_answer(text: str) -> tuple[str, str] | None:
    """Return ``(topic, answer)`` when the question hits the curated set."""
    for topic, pattern, answer in _CURATED_QA:
        if pattern.search(text):
            return topic, answer
    return None


_QA_SYSTEM = """你是量子计算网页助手，面向完全没有基础的新手。

要求：
- 用日常语言解释，先说"它有什么用"，再说"它怎么做到的"。
- 回答控制在 4 段以内，不要长篇大论。
- 只讲量子计算相关内容；与量子无关的问题，直接说明你只能回答量子计算问题。
- 不要编造这个项目不具备的能力。

绝对不要做的事：
- 不要要求用户先提供量子比特数量或测量范围，这是概念问答，不是生成线路。
"""

_QA_NO_FORMULA = "\n用户明确不想看公式：不要出现任何数学公式、矩阵、狄拉克符号或 LaTeX。"


@dataclass
class QAAnswer:
    text: str
    source: str  # "curated" | "llm"
    topic: str | None = None
    question_type: str = "general_quantum_question"
    explicit_subject: str | None = None
    selected_handler: str = "contextual_qa"
    used_glossary: bool = False
    used_llm: bool = False
    fallback_reason: str | None = None


_GATE_GLOSSARY_TOPICS = frozenset({"h_gate", "x_gate", "cx_gate"})


def _gate_glossary_answer(subject: str | None) -> tuple[str, str] | None:
    """Look up one explicit gate subject; circuit context is never consulted."""
    if subject not in _GATE_GLOSSARY_TOPICS:
        return None
    for topic, _pattern, answer in _CURATED_QA:
        if topic == subject:
            return topic, answer
    return None


def _qa_context_payload(
    prompt: str,
    question_type: str,
    explicit_subject: str | None,
    context: dict | None,
) -> dict[str, Any]:
    context = context or {}
    result = context.get("result") if isinstance(context.get("result"), dict) else None
    return {
        "user_question": prompt,
        "question_type": question_type,
        "explicit_subject": explicit_subject,
        "current_task_summary": context.get("task"),
        "current_circuit_summary": context.get("summary"),
        "current_result_summary": result,
    }


def answer_quantum_qa(
    prompt: str,
    context: dict | None = None,
    *,
    no_formula: bool = False,
    question_type: str | None = None,
    explicit_subject: str | None = None,
    completion: Callable[..., dict] | None = None,
) -> QAAnswer:
    """Answer a beginner concept question.

    Curated answers win for genuine "X 是什么" definitions: they are
    deterministic, reviewed, and keep the page useful when no model is
    configured.  Anything the router has already flagged as needing the
    current circuit (``question_type`` other than ``gate_definition``) must
    go to the model with context, never the keyword dictionary.
    """
    inferred_type, inferred_subject = classify_qa_question(prompt, context)
    resolved_type = question_type if question_type in QUESTION_TYPES else inferred_type
    resolved_subject = explicit_subject or inferred_subject

    # Fixed prose is legal only for a precise gate-definition question whose
    # subject appears in the user's message. None/unknown and contextual QA can
    # never fall back to the current circuit's first gate.
    if resolved_type == "gate_definition":
        hit = _gate_glossary_answer(resolved_subject)
        if hit is not None:
            topic, text = hit
            return QAAnswer(
                text=text,
                source="curated",
                topic=topic,
                question_type=resolved_type,
                explicit_subject=resolved_subject,
                selected_handler="deterministic_gate_glossary",
                used_glossary=True,
            )

    if completion is None:
        if not llm_available():
            raise LLMNotConfigured("模型服务尚未配置")
        completion = _runtime_completion() or _chat_completion()

    system = _QA_SYSTEM + """

回答优先级：用户当前问题 > 与问题相关的当前上下文 > 其它背景。
- 第一段必须直接回答 user_question。
- current context 只能补充回答，不能把线路中的 H/X/CX 当成默认问题对象。
- 如果 user_question 与当前任务无关，独立回答，不要强行关联线路。
- question_type 为 unknown 时按一般量子问题回答；无法判断时简短澄清，绝不能解释当前第一个门。
- shots_explanation 必须说明：shots 是重复执行/测量次数，单次只有一个具体结果，多次才能估计概率分布。
- result_pattern 必须先解释结果之间的关联；若涉及 Bell，可把 H 创建叠加、CX 建立关联作为解释链，不能只讲 H。
""" + (_QA_NO_FORMULA if no_formula else "")
    user_content = json.dumps(
        _qa_context_payload(prompt, resolved_type, resolved_subject, context),
        ensure_ascii=False,
        separators=(",", ":"),
    )

    response = completion([
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ])
    try:
        text = response["choices"][0]["message"]["content"]
    except (TypeError, KeyError, IndexError) as exc:
        raise RuntimeError("模型返回结构无法解析") from exc
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("模型没有返回可展示的内容")
    return QAAnswer(
        text=text.strip(),
        source="llm",
        question_type=resolved_type,
        explicit_subject=resolved_subject,
        selected_handler="contextual_qa",
        used_llm=True,
        fallback_reason=("classifier question_type unknown; used general QA"
                         if resolved_type == "unknown" else None),
    )


# --------------------------------------------------------------------------
# Logging (任务书 §33) - never emits credentials
# --------------------------------------------------------------------------


def log_route(route_result: Route, handler: str, *, stream=None) -> None:
    stream = stream if stream is not None else sys.stderr
    stream.write(
        f"[agent] intent={route_result.intent} "
        f"confidence={route_result.confidence:.2f} source={route_result.source}\n"
    )
    stream.write(f"[agent] handler={handler}\n")


def log_qa_debug(record: dict[str, Any], *, stream=None) -> None:
    """Emit one credential-free QA decision record in developer mode."""
    stream = stream if stream is not None else sys.stderr
    stream.write("[agent.qa] " + json.dumps(record, ensure_ascii=False) + "\n")
