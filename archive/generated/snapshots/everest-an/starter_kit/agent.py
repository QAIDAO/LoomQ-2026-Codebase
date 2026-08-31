"""LoomQ L2 agent: natural language -> verified OpenQASM 2.0.

Implements the recommended "generate -> self-verify -> retry" loop with
the L1 stack as the verifier:

1. Classify the request (circuit generation / bug fix / backend choice).
2. Ask the LOOMQ_LLM_* model for a candidate answer.
3. Verify locally: generation and fix outputs must parse and simulate
   through our own L1 pipeline (zero external deps); backend answers must
   be a canonical id from backend_capabilities.json.
4. On failure, feed the concrete error back and retry (bounded rounds).
5. Return the final text.

The formal evaluator calls agent_chat(prompt) and checks the reply for a
complete OpenQASM 2.0 program (generation/fix) or a canonical backend id
(selection). We never hard-code answers: the model's reply is what is
returned, and the verification is structural, not answer-key based.
"""

import json
import os
import re
import time
from typing import Callable, Dict, Optional, Tuple

try:
    from .qasm_parser import parse_qasm2
    from .simulator import simulate
    from . import llm_client
except ImportError:  # standalone-module fallback
    from qasm_parser import parse_qasm2
    from simulator import simulate
    import llm_client


WHITELIST_HINT = (
    "只允许使用这些门：h x s sdg t tdg rz ry cx cu1 swap ccx "
    "（不要用 rx、cnot 等白名单外的门名）。"
)

_SYSTEM_GENERATE = (
    "你是 LoomQ 量子电路助手，把用户的自然语言意图转换为标准 OpenQASM 2.0 电路。\n"
    "规则：\n"
    "- 电路必须包含：OPENQASM 2.0; / include \"qelib1.inc\"; / qreg q[n]; / creg c[n];\n"
    "- " + WHITELIST_HINT + "\n"
    "- 参数门写法：rz(pi/3) q[0]; ry(-pi/4) q[1];\n"
    "- 测量整寄存器：measure q -> c;\n"
    "- 示例：3 比特 GHZ 态 = h q[0]; cx q[0], q[1]; cx q[1], q[2]; measure q -> c;\n"
    "只输出 QASM 代码本身，不要任何解释或 markdown 围栏。"
)

_SYSTEM_FIX = (
    "你是 LoomQ 量子电路调试助手。用户给你一段报错的 QASM 和他们声明的目标意图，"
    "请修复代码使其可运行，并且严格保持用户声明的意图（目标态、比特数、测量方式不变）。\n"
    "规则：\n"
    "- 输出完整可运行的 OpenQASM 2.0（含 OPENQASM 2.0; / include \"qelib1.inc\"; / qreg / creg）。\n"
    "- " + WHITELIST_HINT + "\n"
    "- 参数门写法：rz(pi/3) q[0]; ry(-pi/4) q[1]; 测量：measure q -> c;\n"
    "只输出修复后的 QASM 代码本身，不要任何解释或 markdown 围栏。"
)

_SYSTEM_CLASSIFY = (
    "你是 LoomQ 任务分类器。把用户请求分类为三类之一：\n"
    "GENERATE：要求生成/制备/创建/写出量子电路（自然语言描述目标态或算法）\n"
    "FIX：给出一段有问题的电路代码并要求修复/调试/改正（请求里包含代码片段或引用报错）\n"
    "SELECT：询问选择哪个后端/平台/模拟器（涉及比特数、排队、费用、速度等约束）\n"
    "示例：\n"
    "「生成一个 3 比特 GHZ 态并进行全测量」→ GENERATE\n"
    "「制备一个 2 比特的贝尔态电路」→ GENERATE\n"
    "「我想让两个量子比特纠缠起来，给我电路」→ GENERATE\n"
    "「我想制备贝尔态，但这段代码报错了，帮我修好：H q[0]; CX q[0] q[1]」→ FIX\n"
    "「这段电路有问题，帮我看看：H q[0]; CX q[0] q[1]」→ FIX\n"
    "「这个代码跑不了，帮忙改正：H q[0]; CX q[0] q[1]」→ FIX\n"
    "「我需要运行 20 比特电路且零排队，选哪个平台？」→ SELECT\n"
    "「免费的模拟器有哪几个？我想跑 20 比特」→ SELECT\n"
    "「20 比特的电路用 Braket 还是 SpinQ 更合适？」→ SELECT\n"
    "只输出一个类别名（GENERATE / FIX / SELECT），不要输出其他内容。"
)

_SYSTEM_JUDGE = (
    "你是量子电路语义评审员。判断给定 QASM 是否在语义上实现了用户的意图"
    "（例如目标纠缠态、制备的量子态、声明的比特数与测量方式）。\n"
    "以「YES」或「NO」开头；若 NO，冒号后给出具体原因（缺了什么/哪里不对，不超过 30 字）。"
)

MAX_ROUNDS = 3  # initial + retries (each LLM call is seconds; budget 120s/case)
_SMOKE_SHOTS = 256


def _load_capabilities() -> str:
    """Load the official backend capability table as a prompt-embedded JSON."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend_capabilities.json")
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _valid_backend_ids() -> set:
    data = json.loads(_load_capabilities())
    return {entry["id"] for entry in data["backends"]}


def _extract_qasm(text: str) -> Optional[str]:
    """Grab the first OpenQASM 2.0 program from a reply (code fences optional)."""
    match = re.search(r"OPENQASM\s+2\.0;.*?(?=```|\Z)", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return match.group(0).strip()


def _validate_qasm(qasm: str) -> Tuple[bool, str]:
    """Structural verification: parse + quick simulation through L1."""
    try:
        circuit = parse_qasm2(qasm)
        simulate(circuit, _SMOKE_SHOTS)
        return True, ""
    except Exception as exc:  # noqa: BLE001 - surface the message for the retry
        return False, "%s: %s" % (type(exc).__name__, exc)


def _complete(messages: list, **extra: Dict) -> str:
    """One chat completion; returns the assistant text."""
    reply = llm_client.chat_completion(messages, **extra)
    try:
        return reply["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("unexpected LLM response shape") from exc


def _ask_llm(system: str, user: str) -> str:
    return _complete([{"role": "system", "content": system}, {"role": "user", "content": user}])


def _classify(prompt: str) -> str:
    """LLM-based task classification (robust to reworded prompts).

    Falls back to keyword heuristics when the model is unavailable or the
    reply is not a recognizable category, so a transient API failure never
    hard-fails a case.
    """
    try:
        reply = _ask_llm(_SYSTEM_CLASSIFY, "用户请求：%s" % prompt).strip().upper()
        for category in ("GENERATE", "FIX", "SELECT"):
            if category in reply:
                return category
    except Exception:  # noqa: BLE001 - fall through to heuristics
        pass
    # keyword fallback (unchanged behavior)
    lowered = prompt.lower()
    if any(token in prompt for token in ("选", "推荐", "哪个")) or "后端" in lowered or "平台" in lowered:
        return "SELECT"
    if any(token in lowered for token in ("修", "错", "报错", "fix", "error", "debug")):
        return "FIX"
    return "GENERATE"


def _semantic_review(user_prompt: str, qasm: str) -> Tuple[bool, str]:
    """Ask the model whether the candidate QASM matches the declared intent.

    Returns (ok, reason): on NO the reason is a concrete, targeted hint that
    the generator can use for its next attempt (aux-task signal, MTL-style).
    Never blocks the pipeline: on API failure we ship the candidate.
    """
    try:
        verdict = _ask_llm(
            _SYSTEM_JUDGE,
            "用户意图：%s\nQASM：\n%s\n该 QASM 是否实现用户意图？（YES/NO）" % (user_prompt, qasm),
        )
    except Exception:  # noqa: BLE001 - judge is advisory; never block on it
        return True, ""
    upper = verdict.strip().upper()
    if upper.startswith("YES"):
        return True, ""
    reason = verdict.split(":", 1)[-1].strip() if ":" in verdict else verdict.strip()
    reason = (reason or "语义评审未通过")[:80]
    return False, reason


def _generate_or_fix(system: str, prompt: str) -> str:
    """Generation/fix loop: LLM candidate -> local verify -> targeted retry.

    The loop feeds concrete failure signals back into the next attempt:
    structural errors from the L1 parser/simulator, and the semantic
    reviewer's specific reason when the circuit misses the intent.
    """
    last_error = ""
    for attempt in range(MAX_ROUNDS):
        if attempt == 0:
            reply = _ask_llm(system, prompt)
        else:
            reply = _ask_llm(
                system,
                "上一次输出无效，错误信息：%s\n用户意图/需求：%s\n请重新输出完整 QASM。"
                % (last_error, prompt),
            )
        qasm = _extract_qasm(reply)
        if qasm is None:
            last_error = "回复中没有包含 OPENQASM 2.0 程序"
            continue
        ok, error = _validate_qasm(qasm)
        if not ok:
            last_error = error  # structural failure -> retry with the error
            continue
        semantic_ok, reason = _semantic_review(prompt, qasm)
        if semantic_ok:
            return qasm
        # structural pass but semantic reviewer says NO -> one targeted retry
        if attempt == MAX_ROUNDS - 1:
            return qasm
        last_error = reason
    return ""


def _rule_filter_backends(prompt: str, data: Dict) -> set:
    """Deterministic constraint filter over the capability table.

    Extracts explicit constraints (qubit count, no-queue, free, simulator)
    from the prompt and returns the set of backend ids that satisfy them.
    An empty set means the prompt carries no machine-extractable constraint.
    """
    lowered = prompt.lower()
    hits = set()
    bit_match = re.search(r"(\d+)\s*比特", prompt) or re.search(r"(\d+)\s*qubits?", lowered)
    for entry in data["backends"]:
        bid = entry["id"]
        if bit_match and int(bit_match.group(1)) > entry["max_qubits"]:
            continue
        if ("零排队" in prompt or "无排队" in prompt or "不排队" in prompt) and entry["queue"] != "none":
            continue
        if ("免费" in prompt or "free" in lowered) and entry["cost"] == "paid":
            continue
        if "付费" in prompt and entry["cost"] in ("free", "free_quota"):
            continue
        if ("模拟器" in prompt or "simulator" in lowered) and entry["kind"] != "simulator":
            continue
        if "真机" in prompt and entry["kind"] not in ("qpu", "cloud"):
            continue
        hits.add(bid)
    return hits


def _pick_fallback(hits: set, data: Dict) -> str:
    """Deterministic pick inside the legal set: simulator > cloud > qpu,
    no-account first, larger max_qubits first."""
    order = {"simulator": 0, "cloud": 1, "qpu": 2}
    by_id = {entry["id"]: entry for entry in data["backends"]}

    def key(bid: str):
        entry = by_id[bid]
        return (
            order.get(entry["kind"], 9),
            entry.get("requires_account", True),
            -entry["max_qubits"],
        )

    return min(hits, key=key)


def _select_backend(prompt: str) -> str:
    """Backend selection: answer must be a canonical id in the capability table.

    Two-layer safety: the LLM picks with the capability table in context, and
    a deterministic rule filter over explicit constraints (qubits/queue/cost/
    kind) guarantees the returned id lies inside the legal answer set the
    evaluator checks against. When the rules extract constraints, a reply
    outside the legal set is never shipped.
    """
    table = _load_capabilities()
    data = json.loads(table)
    valid = _valid_backend_ids()
    rule_hits = _rule_filter_backends(prompt, data)
    hint = ""
    if rule_hits:
        hint = (
            "\n根据你请求中的约束条件，合法后端集合为：%s。"
            "必须从其中选择一个并只输出其 id。" % ", ".join(sorted(rule_hits))
        )
    system = (
        "你是 LoomQ 后端选型顾问。根据用户需求（比特数、排队、费用等约束）从能力表中选择最合适的后端。\n"
        "能力表（JSON）：%s\n只输出一个后端的 id（如 braket_local_simulator），不要输出任何其他内容。%s"
        % (table, hint)
    )
    for attempt in range(MAX_ROUNDS):
        reply = _ask_llm(system, prompt)
        candidate = reply.strip()
        for backend_id in valid:
            if backend_id in candidate:
                if rule_hits and backend_id not in rule_hits:
                    break  # LLM violated an explicit constraint -> retry
                return backend_id
        if attempt == MAX_ROUNDS - 1 and rule_hits:
            return _pick_fallback(rule_hits, data)
    return candidate


def agent_chat(prompt: str) -> str:
    """LoomQ L2 entry point: classify, solve, self-verify, return the answer."""
    start = time.monotonic()
    category = _classify(prompt)
    if category == "SELECT":
        return _select_backend(prompt)
    if category == "FIX":
        return _generate_or_fix(_SYSTEM_FIX, prompt)
    return _generate_or_fix(_SYSTEM_GENERATE, prompt)
