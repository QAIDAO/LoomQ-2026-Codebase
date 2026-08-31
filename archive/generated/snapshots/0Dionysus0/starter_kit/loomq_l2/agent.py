"""L2 agent: natural language -> OpenQASM / backend choice, with L1 self-check.

Flow:
  1. Classify the request (generate / fix / select backend).
  2. Circuit tasks: ask for QASM plus the model's own statement of the target
     distribution -> run L1 -> Hellinger-check against that statement -> feed
     both distributions back and retry on mismatch.
  3. Backend selection: one model turn extracts the constraints, Python filters
     the official backend_capabilities.json, and a second model turn explains
     the result in plain language. Canonical ids are inserted deterministically,
     so the answer stays correct even if both turns fail.

Formal scoring only counts a case when at least one model call succeeded, and
every path above can fall back to local logic. Calls are therefore retried and
tallied in a ledger; `agent_chat` labels the answer when nothing reached the
model, instead of passing off local output as model work.

No API URL / key / model name is hardcoded. Formal scoring injects LOOMQ_LLM_*
(and uses deepseek-v4-flash per l2_policy.json); your code must only read env vars.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import llm_client

_VERIFY_SHOTS = 2048
_MAX_ROUNDS = 3
_VERIFY_TARGET = "braket"
_FIDELITY_THRESHOLD = 0.97
_DECLARED_SUM_TOLERANCE = 0.02

# A case only scores when at least one model call actually succeeded, so a
# transient network blip must not be allowed to quietly skip the model.
_CHAT_ATTEMPTS = 3
_CHAT_BACKOFF_SECONDS = (0.6, 1.8)

_GATE_HINT = (
    "Only use these OpenQASM 2.0 / qelib1 gates: "
    "h, x, s, sdg, t, tdg, rz(theta), ry(theta), cx, cu1(theta), swap, ccx. "
    "Do not use rx, cz, cnot, u3, or non-qelib1 names."
)

_SYSTEM_CLASSIFY = """You classify LoomQ user requests into exactly one label.
Return ONLY JSON: {"label":"GENERATE"} or {"label":"FIX"} or {"label":"SELECT"}

Definitions:
- SELECT: user asks which backend/platform/simulator/QPU to use under constraints
  (qubits, queue, cost, local, paid, AWS, SpinQ, OriginQ). No need to output a circuit.
- FIX: user provides broken/incorrect circuit text (or clear repair verbs) and wants it fixed
  while keeping a declared intent (Bell/GHZ/etc.).
- GENERATE: user wants a new circuit from natural language, and is NOT mainly choosing a backend.

Priority when mixed: SELECT > FIX > GENERATE.
Examples:
- "15比特零排队选哪个平台？" -> SELECT
- "真实硬件5比特不想花钱推荐哪个" -> SELECT
- "Which canonical backend is Braket local with no AWS account?" -> SELECT
- "贝尔态代码报错了帮我修好：H q[0]; CX q[0] q[1]" -> FIX
- "生成3比特GHZ并全测量" -> GENERATE
- "Write a Bell pair in OpenQASM 2.0" -> GENERATE
"""

_SYSTEM_CIRCUIT = f"""You are a LoomQ circuit assistant.
Answer in exactly two blocks, in this order.

BLOCK 1 - the target you understood, as a json code block:
```json
{{"expected_counts": {{"01": 0.5, "10": 0.5}}}}
```
`expected_counts` is the ideal noiseless measurement distribution the user is
asking for. Keys are classical bit strings whose RIGHTMOST character is c[0]
(Qiskit convention); values are probabilities that sum to 1; list only outcomes
with non-zero probability. Derive it from the user's stated intent, NOT from the
circuit you are about to write - it is an independent statement of the goal.
If the intent genuinely does not pin down one distribution, write
{{"expected_counts": null}} instead of guessing.

BLOCK 2 - the circuit, as a code block starting with OPENQASM 2.0;

Hard rules for the circuit:
- Start with: OPENQASM 2.0;
- Include: include "qelib1.inc";
- Declare qreg / creg; for full-register measure use matching widths
- {_GATE_HINT}
- Prefer `measure q -> c;` for full-register measurement
- GHZ-n: h on q[0], then cx q[i],q[i+1] (or star cx from q[0]), then measure all
- Bell |00>+|11>: h q[0]; cx q[0],q[1]; measure both
- |+> on 1 qubit: h q[0]; measure

Never put anything after the closing fence of the circuit block. Keep prose short.
"""

_SYSTEM_CONSTRAINTS = """Extract backend-selection constraints from the user request.
Return ONLY a JSON object with these keys (use null when not specified):
{
  "min_qubits": int|null,
  "require_no_queue": bool,
  "require_free": bool,
  "require_qpu": bool,
  "prefer_platform": "spinq"|"originq"|"braket"|null,
  "require_local": bool,
  "allow_paid": bool
}
Rules:
- "零排队/no queue/no waiting" => require_no_queue true
- "不想花钱/免费/free" => require_free true
- "可以付费/paid/budget ok" => allow_paid true
- "真机/真实硬件/QPU/real hardware" => require_qpu true
- "本地/local/no cloud account" => require_local true
- qubit counts like 15比特 / 15-qubit => min_qubits 15
No markdown fences."""


def _kit_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_capabilities() -> Dict[str, Any]:
    path = _kit_root() / "backend_capabilities.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _backend_ids() -> List[str]:
    return [entry["id"] for entry in _load_capabilities()["backends"]]


# --------------------------------------------------------------------------
# Model-call ledger
#
# Formal scoring only counts a case when the program completed at least one
# real model call, so every answer has to know whether it was actually backed
# by the model or produced by local fallbacks.  Thread-local because the web
# entry point serves requests concurrently.
# --------------------------------------------------------------------------

_call_state = threading.local()


def reset_call_ledger() -> None:
    _call_state.successes = 0
    _call_state.failures = []
    _call_state.verification = None


def model_calls_made() -> int:
    return getattr(_call_state, "successes", 0)


def model_call_failures() -> List[str]:
    return list(getattr(_call_state, "failures", []))


def last_verification() -> Optional[Dict[str, Any]]:
    """What the local self-check concluded about the circuit just returned.

    `status` is "passed", "failed" or "unverified"; callers use it to show the
    user where an answer came from instead of presenting every reply as fact.
    """
    return getattr(_call_state, "verification", None)


def _record_verification(
    status: str, fidelity: Optional[float], detail: str
) -> None:
    _call_state.verification = {
        "status": status,
        "fidelity": fidelity,
        "threshold": _FIDELITY_THRESHOLD,
        "detail": detail,
    }


def _record_success() -> None:
    _call_state.successes = getattr(_call_state, "successes", 0) + 1


def _record_failure(reason: str) -> None:
    failures = getattr(_call_state, "failures", None)
    if failures is None:
        failures = []
        _call_state.failures = failures
    failures.append(reason)


def _chat(messages: List[Dict[str, str]], attempts: int = _CHAT_ATTEMPTS) -> str:
    """One model turn, retried over transient transport failures.

    Raises only after every attempt failed; callers that can degrade should
    check `model_calls_made()` rather than assume a local fallback is free.
    """
    last_error: Optional[str] = None
    for attempt in range(attempts):
        try:
            payload = llm_client.chat_completion(messages)
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("LLM returned empty content")
        except (KeyError, IndexError, TypeError) as exc:
            last_error = f"unexpected LLM response shape: {type(exc).__name__}"
        except Exception as exc:  # noqa: BLE001 - transport errors vary by provider
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            _record_success()
            return content

        _record_failure(last_error or "unknown failure")
        if attempt + 1 < attempts:
            delay = _CHAT_BACKOFF_SECONDS[min(attempt, len(_CHAT_BACKOFF_SECONDS) - 1)]
            time.sleep(delay)

    raise RuntimeError(f"model call failed after {attempts} attempt(s): {last_error}")


def extract_qasm(text: str) -> Optional[str]:
    if not isinstance(text, str):
        return None
    match = re.search(
        r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)",
        text,
        flags=re.DOTALL | re.MULTILINE | re.IGNORECASE,
    )
    return match.group(0).strip() if match else None


def _balanced_json_objects(text: str) -> List[str]:
    """Yield every top-level {...} substring, ignoring braces inside strings."""
    found: List[str] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                found.append(text[start : index + 1])
                start = -1
    return found


def _validate_distribution(counts: Any) -> Tuple[Optional[Dict[str, float]], str]:
    """Accept a declared distribution only when it is well formed."""
    if not isinstance(counts, dict) or not counts:
        return None, "expected_counts is not a non-empty object"
    cleaned: Dict[str, float] = {}
    widths = set()
    for key, value in counts.items():
        if not isinstance(key, str) or not re.fullmatch(r"[01]+", key):
            return None, f"key {key!r} is not a bit string"
        try:
            probability = float(value)
        except (TypeError, ValueError):
            return None, f"probability for {key!r} is not numeric"
        if probability < 0:
            return None, f"negative probability for {key!r}"
        widths.add(len(key))
        cleaned[key] = probability
    if len(widths) != 1:
        return None, f"mixed bit-string widths {sorted(widths)}"
    total = sum(cleaned.values())
    if total <= 0:
        return None, "probabilities sum to zero"
    if abs(total - 1.0) > _DECLARED_SUM_TOLERANCE:
        return None, f"probabilities sum to {total:.3f}, not 1"
    return {key: value / total for key, value in cleaned.items()}, "ok"


def parse_declared_distribution(reply: str) -> Tuple[Optional[Dict[str, float]], str]:
    """Read the model's own statement of the distribution it was aiming for.

    This replaces keyword-guessing the target: it works for any state the user
    asks for, and it fails loudly instead of silently verifying nothing.
    """
    if not isinstance(reply, str):
        return None, "reply is not text"
    seen_declaration = False
    for candidate in _balanced_json_objects(reply):
        try:
            data = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict) or "expected_counts" not in data:
            continue
        seen_declaration = True
        counts = data["expected_counts"]
        if counts is None:
            return None, "model declined to pin down a distribution"
        distribution, note = _validate_distribution(counts)
        if distribution is not None:
            return distribution, note
        return None, note
    return None, "no expected_counts declaration found" if not seen_declaration else "unusable declaration"


def strip_declaration(reply: str) -> str:
    """Remove the internal target declaration from the user-facing answer.

    The official extractor reads from `OPENQASM 2.0;` to the next fence, so the
    declaration must never sit after the circuit; stripping it also keeps the
    reply readable for the judges testing the interactive entry point.
    """
    if not isinstance(reply, str):
        return reply
    cleaned = re.sub(
        r"```json\s*\{[^`]*?\"expected_counts\"[^`]*?\}\s*```\s*",
        "",
        reply,
        flags=re.DOTALL,
    )
    cleaned = re.sub(
        r"^\s*\{[^{}]*\"expected_counts\".*?\}\s*$",
        "",
        cleaned,
        flags=re.DOTALL | re.MULTILINE,
    )
    return cleaned.strip()


def extract_backend_id(text: str, valid_ids: Optional[List[str]] = None) -> Optional[str]:
    ids = valid_ids if valid_ids is not None else _backend_ids()
    for backend_id in sorted(ids, key=len, reverse=True):
        if backend_id in text:
            return backend_id
    return None


def hellinger_fidelity(p: Dict[str, float], q: Dict[str, float]) -> float:
    keys = set(p) | set(q)
    dist = math.sqrt(
        sum((math.sqrt(p.get(k, 0.0)) - math.sqrt(q.get(k, 0.0))) ** 2 for k in keys)
    )
    return 1.0 - dist / math.sqrt(2.0)


def _counts_to_prob(counts: Dict[str, int]) -> Dict[str, float]:
    total = float(sum(counts.values())) or 1.0
    return {k: v / total for k, v in counts.items()}


def infer_ideal_distribution(prompt: str) -> Optional[Dict[str, float]]:
    """Best-effort ideal distribution from common contest intents."""
    text = prompt.lower()
    # Bell
    if any(tok in prompt for tok in ("贝尔", "貝爾")) or "bell" in text:
        return {"00": 0.5, "11": 0.5}
    # |+> / plus / 均匀叠加 single qubit
    if any(tok in prompt for tok in ("|+", "|＋", "＋态", "+态")) or (
        "plus" in text and "bell" not in text
    ):
        if not any(tok in prompt for tok in ("GHZ", "ghz", "纠缠", "贝尔", "Bell")):
            return {"0": 0.5, "1": 0.5}
    if ("叠加" in prompt or "superposition" in text) and not any(
        tok in prompt for tok in ("GHZ", "ghz", "纠缠", "贝尔", "Bell", "比特")
    ):
        return {"0": 0.5, "1": 0.5}
    if "单比特" in prompt and ("叠加" in prompt or "h " in text or "hadamard" in text):
        return {"0": 0.5, "1": 0.5}

    # GHZ-n
    n: Optional[int] = None
    if "ghz" in text or "GHZ" in prompt or "最大纠缠" in prompt or "全部纠缠" in prompt:
        match = re.search(r"(\d+)\s*(?:比特|qubit|qubits|-?\s*qubit)", prompt, re.I)
        if not match:
            match = re.search(r"(?:ghz[-\s]?|GHZ[-\s]?)(\d+)", prompt)
        if not match:
            cn = {"两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "八": 8}
            for word, val in cn.items():
                if word + "比特" in prompt or word + "个量子比特" in prompt:
                    n = val
                    break
        else:
            n = int(match.group(1))
        if n is None and ("最大纠缠" in prompt or "ghz" in text):
            n = 3
        if n is not None and 1 < n <= 16:
            return {"0" * n: 0.5, "1" * n: 0.5}
    return None


def _looks_like_code_fragment(prompt: str) -> bool:
    """True when the user pasted circuit-like text worth repairing."""
    if "OPENQASM" in prompt.upper():
        return True
    if re.search(r"\bq\[\d+\]", prompt):
        return True
    if re.search(r"\b(creg|qreg)\b", prompt, re.I):
        return True
    # Bare broken gates from the problem-statement example style.
    if re.search(r"\b(H|X|CX|CNOT|Hadamard)\s+q", prompt):
        return True
    if "`" in prompt and re.search(r"[;{}]", prompt):
        return True
    return False


def _score_task_labels(prompt: str) -> Dict[str, int]:
    """Weighted rule scores. Higher = more confident."""
    text = prompt.lower()
    scores = {"SELECT": 0, "FIX": 0, "GENERATE": 0}

    # --- SELECT signals (platform choice; must beat casual 选/推荐) ---
    select_strong = (
        "哪个平台",
        "哪个后端",
        "哪一个平台",
        "哪一个后端",
        "选哪个平台",
        "选哪个后端",
        "推荐哪个",
        "推荐后端",
        "规范后端",
        "canonical backend",
        "which backend",
        "which platform",
        "which canonical",
        "零排队",
        "无排队",
        "no queue",
        "no waiting",
    )
    select_medium = (
        "后端",
        "平台",
        "backend",
        "platform",
        "simulator",
        "模拟器",
        "真机",
        "qpu",
        "排队",
        "queue",
        "不想花钱",
        "免费额度",
        "付费",
        "braket",
        "spinq",
        "originq",
        "aws",
        "量旋",
        "本源",
        "悟空",
    )
    for tok in select_strong:
        if tok in prompt or tok in text:
            scores["SELECT"] += 6
    for tok in select_medium:
        if tok in prompt or tok in text:
            scores["SELECT"] += 2
    # "选哪个 / 推荐一下" only counts toward SELECT with infra context.
    if re.search(r"(选哪个|选哪一个|推荐一下|recommend)", prompt, re.I):
        if scores["SELECT"] > 0 or any(
            t in text for t in ("比特", "qubit", "排队", "queue", "免费", "付费", "local")
        ):
            scores["SELECT"] += 5

    # --- FIX signals ---
    fix_strong = (
        "报错",
        "修好",
        "修复",
        "改错",
        "帮我改",
        "帮我修",
        "debug",
        "fix this",
        "fix it",
        "doesn't work",
        "does not work",
        "跑不了",
        "无法运行",
    )
    fix_medium = ("修", "错误", "error", "bug", "改正", "改一下")
    for tok in fix_strong:
        if tok in prompt or tok in text:
            scores["FIX"] += 6
    for tok in fix_medium:
        if tok in prompt or tok in text:
            scores["FIX"] += 2
    if _looks_like_code_fragment(prompt):
        scores["FIX"] += 4
        # Pasted code + any repair verb => very likely FIX.
        if scores["FIX"] >= 6:
            scores["FIX"] += 3

    # --- GENERATE signals ---
    gen_strong = (
        "生成",
        "制备",
        "写一段",
        "写一个",
        "写出",
        "给我电路",
        "给我一段",
        "write a",
        "write an",
        "create a",
        "generate a",
        "openqasm",
    )
    gen_medium = ("电路", "circuit", "qasm", "ghz", "bell", "贝尔", "纠缠", "测量")
    for tok in gen_strong:
        if tok in prompt or tok in text:
            scores["GENERATE"] += 4
    for tok in gen_medium:
        if tok in prompt or tok in text:
            scores["GENERATE"] += 1

    # If it clearly asks for a platform and never mentions writing a circuit, suppress GENERATE.
    if scores["SELECT"] >= 6 and not _looks_like_code_fragment(prompt):
        if not any(t in prompt for t in ("生成", "制备", "写一段", "写一个", "OpenQASM", "openqasm")):
            scores["GENERATE"] = max(0, scores["GENERATE"] - 4)

    # Pasted broken gates without "generate" verbs → prefer FIX over GENERATE.
    if _looks_like_code_fragment(prompt) and scores["FIX"] >= scores["GENERATE"]:
        scores["GENERATE"] = max(0, scores["GENERATE"] - 2)

    return scores


def _heuristic_kind(prompt: str) -> str:
    scores = _score_task_labels(prompt)
    return max(scores.items(), key=lambda item: (item[1], item[0] == "SELECT"))[0]


def _heuristic_kind_confident(prompt: str) -> Optional[str]:
    """Return a label only when rules are clearly decisive."""
    scores = _score_task_labels(prompt)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_label, best = ranked[0]
    second = ranked[1][1]
    # Strong SELECT/FIX should not wait on the LLM (stable + saves latency).
    if best_label == "SELECT" and best >= 8 and best >= second + 3:
        return "SELECT"
    if best_label == "FIX" and best >= 8 and best >= second + 2:
        return "FIX"
    if best_label == "GENERATE" and best >= 6 and best >= second + 3 and scores["SELECT"] < 6:
        return "GENERATE"
    return None


def _parse_classify_label(reply: str) -> Optional[str]:
    text = reply.strip()
    try:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            label = str(data.get("label", "")).strip().upper()
            if label in ("GENERATE", "FIX", "SELECT"):
                return label
    except Exception:
        pass
    upper = text.upper()
    for label in ("SELECT", "FIX", "GENERATE"):  # SELECT first if multiple words appear
        if re.search(rf"\b{label}\b", upper):
            return label
    return None


def classify(prompt: str) -> str:
    """Stable classifier: decisive rules first, LLM only on ambiguous prompts.

    If the model disagrees with a strong SELECT/FIX rule score, keep the rule.
    """
    scores = _score_task_labels(prompt)
    confident = _heuristic_kind_confident(prompt)
    if confident is not None:
        return confident

    llm_label: Optional[str] = None
    try:
        reply = _chat(
            [
                {"role": "system", "content": _SYSTEM_CLASSIFY},
                {"role": "user", "content": prompt},
            ]
        )
        llm_label = _parse_classify_label(reply)
    except Exception:
        llm_label = None

    if llm_label is None:
        return _heuristic_kind(prompt)

    # Guardrails: do not let the model override clear infra / repair cues.
    if scores["SELECT"] >= 8 and llm_label != "SELECT":
        return "SELECT"
    if scores["FIX"] >= 8 and llm_label == "GENERATE":
        return "FIX"
    return llm_label


def _verify_qasm(
    qasm: str, ideal: Optional[Dict[str, float]]
) -> Tuple[bool, str, Optional[float], Optional[Dict[str, float]]]:
    """Run the circuit through L1 and score it against `ideal`.

    Returns (passed, human-readable detail, fidelity, observed distribution).
    Fidelity is None when there was no target to compare against.
    """
    import adapter

    try:
        result = adapter.run(qasm, _VERIFY_TARGET, _VERIFY_SHOTS)
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}", None, None
    counts = result.get("counts") or {}
    if not counts:
        return False, "L1 run returned empty counts", None, None
    if sum(counts.values()) != _VERIFY_SHOTS:
        return False, "L1 run shot total mismatch", None, None
    observed = _counts_to_prob(counts)
    if ideal is None:
        return True, "structural ok (no target to compare against)", None, observed

    ideal_width = len(next(iter(ideal)))
    observed_width = len(next(iter(observed)))
    if ideal_width != observed_width:
        return (
            False,
            f"target uses {ideal_width}-bit outcomes but the circuit measures "
            f"{observed_width} classical bits",
            0.0,
            observed,
        )

    fid = hellinger_fidelity(observed, ideal)
    if fid < _FIDELITY_THRESHOLD:
        return False, f"fidelity {fid:.4f} < {_FIDELITY_THRESHOLD}", fid, observed
    return True, f"fidelity {fid:.4f}", fid, observed


def _format_distribution(dist: Dict[str, float], limit: int = 8) -> str:
    items = sorted(dist.items(), key=lambda item: -item[1])[:limit]
    body = ", ".join(f"{key}:{value:.3f}" for key, value in items)
    return body + (", ..." if len(dist) > limit else "")


def _honest_failure_notice(status: str, fidelity: Optional[float]) -> str:
    """Said out loud when self-check did not clear the circuit.

    Kept ahead of the program text so the official extractor still reads the
    QASM, and worded so a beginner understands the answer is not trustworthy.
    """
    if status == "failed" and fidelity is not None:
        return (
            "⚠️ 这道题我没做对。我把电路真的跑了一遍，再和你要的结果对比，"
            f"吻合度只有 {fidelity:.2f}，而通过线是 {_FIDELITY_THRESHOLD:.2f}。"
            "下面是我试过的几版里最接近的一版，请不要当成正确答案直接用。"
        )
    return (
        "⚠️ 这道题我没能验证。电路本身跑得通，但我无法确认它的结果就是你想要的，"
        "所以我不能说它是对的。下面是我目前最好的一版，请你自己核对。"
    )


def _circuit_loop(prompt: str, kind: str) -> str:
    """Generate a circuit, verify it against a target, and retry on mismatch.

    The target is whatever the model itself declared it was aiming for, which
    generalises to any requested state. The keyword-derived guess is only a
    fallback for replies that carry no usable declaration.
    """
    inferred = infer_ideal_distribution(prompt)
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_CIRCUIT},
        {
            "role": "user",
            "content": (
                f"Task type: {kind}\n"
                f"User request:\n{prompt}\n\n"
                "Declare the target distribution first, then the circuit."
            ),
        },
    ]

    # (fidelity, round index, user-facing reply, qasm, status); best fidelity wins.
    attempts: List[Tuple[float, int, str, str, str]] = []
    fallback_reply = ""

    for round_idx in range(_MAX_ROUNDS):
        raw_reply = _chat(messages)
        reply = strip_declaration(raw_reply)
        fallback_reply = fallback_reply or reply
        qasm = extract_qasm(raw_reply)
        if qasm is None:
            messages.append({"role": "assistant", "content": raw_reply})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous reply had no valid OpenQASM 2.0 program "
                        "(must contain OPENQASM 2.0;). Output the json target "
                        "block and then a full program now."
                    ),
                }
            )
            continue

        declared, declared_note = parse_declared_distribution(raw_reply)
        if declared is not None:
            target, source = declared, "your declared target"
        elif inferred is not None:
            target, source = inferred, "the target inferred from the request"
        else:
            target, source = None, "no target"

        ok, detail, fidelity, observed = _verify_qasm(qasm, target)
        if ok and target is not None:
            _record_verification("passed", fidelity, detail)
            return reply if "OPENQASM" in reply else qasm
        if ok:
            # Ran cleanly but nothing was actually verified; keep looking for a
            # round that declares a target, and fall back to this one.
            attempts.append((-1.0, round_idx, reply, qasm, "unverified"))
            messages.append({"role": "assistant", "content": raw_reply})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"The circuit runs, but self-check could not verify it: "
                        f"{declared_note}. Restate the reply with a valid "
                        '```json {"expected_counts": ...} ``` block describing the '
                        "distribution the user asked for, then the same or a "
                        "corrected circuit."
                    ),
                }
            )
            continue

        attempts.append(
            (
                fidelity if fidelity is not None else -1.0,
                round_idx,
                reply,
                qasm,
                "failed" if fidelity is not None else "unverified",
            )
        )
        feedback = [
            f"Round {round_idx + 1}: local verification failed.",
            f"Checked against {source}.",
            f"Detail: {detail}",
        ]
        if target is not None:
            feedback.append(f"Target distribution: {_format_distribution(target)}")
        if observed:
            feedback.append(
                f"Your circuit actually produced: {_format_distribution(observed)}"
            )
        feedback.append(
            "Decide which side is wrong. If the circuit is wrong, fix the gates. "
            "If the declared target misread the request, restate it. "
            "Return both blocks again."
        )
        messages.append({"role": "assistant", "content": raw_reply})
        messages.append({"role": "user", "content": "\n".join(feedback)})

    if not attempts:
        _record_verification("unverified", None, "no runnable circuit was produced")
        return fallback_reply

    attempts.sort(key=lambda item: (-item[0], item[1]))
    best_fidelity, _, best_reply, best_qasm, best_status = attempts[0]
    fidelity = best_fidelity if best_fidelity >= 0.0 else None
    _record_verification(
        best_status,
        fidelity,
        f"best of {len(attempts)} attempt(s) after {_MAX_ROUNDS} round(s)",
    )
    body = best_reply if "OPENQASM" in best_reply else best_qasm
    return _honest_failure_notice(best_status, fidelity) + "\n\n" + body


def _heuristic_constraints(prompt: str) -> Dict[str, Any]:
    text = prompt.lower()
    min_qubits = None
    match = re.search(r"(\d+)\s*(?:比特|qubit|qubits)", prompt, re.I)
    if match:
        min_qubits = int(match.group(1))
    return {
        "min_qubits": min_qubits,
        "require_no_queue": any(t in prompt for t in ("零排队", "无排队"))
        or "no queue" in text
        or "no waiting" in text,
        "require_free": any(t in prompt for t in ("不想花钱", "免费", "零费用"))
        or ("free" in text and "free_quota" not in text),
        "require_qpu": any(t in prompt for t in ("真机", "真实", "硬件", "QPU"))
        or "real hardware" in text
        or "quantum hardware" in text,
        "prefer_platform": (
            "braket"
            if "braket" in text or "aws" in text
            else "spinq"
            if "spinq" in text or "量旋" in prompt
            else "originq"
            if "origin" in text or "本源" in prompt or "悟空" in prompt
            else None
        ),
        "require_local": "本地" in prompt or "local" in text or "no cloud account" in text
        or "no aws" in text,
        "allow_paid": any(t in prompt for t in ("付费", "可以花钱", "预算允许"))
        or "paid" in text,
    }


def _extract_constraints(prompt: str) -> Dict[str, Any]:
    """Model reads the constraints; local rules only patch what it omitted.

    The model call is retried inside `_chat`. A failure here is recorded in the
    ledger rather than silently swallowed, because an answer produced without
    any model call scores zero no matter how correct it is.
    """
    base = _heuristic_constraints(prompt)
    try:
        raw = _chat(
            [
                {"role": "system", "content": _SYSTEM_CONSTRAINTS},
                {"role": "user", "content": prompt},
            ]
        )
    except RuntimeError:
        return base

    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return base
    try:
        data = json.loads(match.group(0))
    except (ValueError, TypeError):
        return base
    if not isinstance(data, dict):
        return base
    for key in base:
        if key in data and data[key] is not None:
            base[key] = data[key]
    return base


def _explain_selection(
    prompt: str,
    constraints: Dict[str, Any],
    chosen: List[Dict[str, Any]],
    solved: bool,
    primary: str,
) -> Optional[str]:
    """Ask the model to justify the choice in plain language for a beginner.

    This is a second, independent model turn on the selection path. It earns
    its keep twice over: a zero-background user gets a readable reason instead
    of a bare identifier, and one flaky call no longer leaves the whole case
    without any model involvement. Correctness never depends on it - the
    canonical ids are inserted by `_select_backend` either way.
    """
    if not chosen:
        return None
    facts = [
        {
            "id": entry["id"],
            "platform": entry.get("platform"),
            "kind": entry.get("kind"),
            "max_qubits": entry.get("max_qubits"),
            "queue": entry.get("queue"),
            "cost": entry.get("cost"),
        }
        for entry in chosen[:3]
    ]
    system = (
        "You explain an already-made quantum backend choice to someone with no "
        "physics or cloud background. Two or three short sentences, no jargon, "
        "no lists, no code. Justify THE CHOSEN BACKEND you are given - never "
        "recommend a different one, and never contradict the choice. If nothing "
        "satisfied every requirement, say which requirement had to give way. "
        "Reply in the language the user wrote in. Do not invent backends or "
        "numbers beyond the facts given."
    )
    user = (
        f"User asked:\n{prompt}\n\n"
        f"Constraints understood: {json.dumps(constraints, ensure_ascii=False)}\n"
        f"All requirements satisfied: {solved}\n"
        f"CHOSEN BACKEND (explain this one): {primary}\n"
        f"Backend facts: {json.dumps(facts, ensure_ascii=False)}"
    )
    try:
        return _chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}]
        ).strip()
    except RuntimeError:
        return None


def _filter_backends(constraints: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    backends = list(_load_capabilities()["backends"])
    matched: List[Dict[str, Any]] = []
    for entry in backends:
        if constraints.get("min_qubits") is not None:
            if int(entry["max_qubits"]) < int(constraints["min_qubits"]):
                continue
        if constraints.get("require_no_queue") and entry.get("queue") != "none":
            continue
        if constraints.get("require_free") and entry.get("cost") == "paid":
            continue
        if constraints.get("require_qpu") and entry.get("kind") != "qpu":
            # braket_cloud is kind=cloud but can host QPUs; only count pure qpu ids here
            continue
        if constraints.get("require_local") and entry.get("queue") != "none":
            continue
        if constraints.get("prefer_platform") and entry.get("platform") != constraints["prefer_platform"]:
            # soft preference applied later if multiple remain
            pass
        if constraints.get("allow_paid") is False and entry.get("cost") == "paid":
            continue
        matched.append(entry)

    # Soft prefer_platform: if any match on platform, narrow to them.
    pref = constraints.get("prefer_platform")
    if pref:
        preferred = [e for e in matched if e.get("platform") == pref]
        if preferred:
            matched = preferred

    # If require_qpu found nothing and user also said free, keep empty (honest miss).
    # Closest alternatives: ignore the failing hard filter one at a time.
    if matched:
        return matched, []

    # Build closest: sort by how many constraints they satisfy.
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for entry in backends:
        score = 0
        if constraints.get("min_qubits") is not None and int(entry["max_qubits"]) >= int(
            constraints["min_qubits"]
        ):
            score += 1
        if constraints.get("require_no_queue") and entry.get("queue") == "none":
            score += 1
        if constraints.get("require_free") and entry.get("cost") != "paid":
            score += 1
        if constraints.get("require_qpu") and entry.get("kind") == "qpu":
            score += 1
        if constraints.get("require_local") and entry.get("queue") == "none":
            score += 1
        if pref and entry.get("platform") == pref:
            score += 1
        scored.append((score, entry))
    scored.sort(key=lambda item: (-item[0], -int(item[1]["max_qubits"])))
    closest = [entry for _, entry in scored[:3]]
    return [], closest


def _select_backend(prompt: str) -> str:
    """Model reads the constraints and explains the outcome; Python decides.

    The canonical identifiers come from filtering the official capability
    table, so the answer stays correct even when both model turns fail.
    """
    constraints = _extract_constraints(prompt)
    matched, closest = _filter_backends(constraints)
    solved = bool(matched)
    chosen = matched if matched else closest
    if not chosen:
        chosen = _load_capabilities()["backends"][:1]

    ids = [entry["id"] for entry in chosen]
    primary = ids[0]
    explanation = _explain_selection(prompt, constraints, chosen, solved, primary)

    if solved:
        lines = [
            "根据官方 backend_capabilities 表，满足全部约束的规范后端：",
            ", ".join(f"`{i}`" for i in ids),
            f"推荐使用：{primary}",
        ]
    else:
        lines = [
            "没有后端同时满足全部约束（无解）。",
            f"最接近的替代规范后端：{', '.join(f'`{i}`' for i in ids)}",
            f"可考虑：{primary}",
        ]
    if explanation:
        lines.append("")
        lines.append(explanation)
    lines.append("")
    lines.append(f"（约束解析：{json.dumps(constraints, ensure_ascii=False)}）")
    return "\n".join(lines)


_DEGRADED_NOTICE = (
    "⚠️ 模型服务这次没有连上，以下结果由本地规则和官方后端能力表直接算出，"
    "没有经过模型推理。网络恢复后建议重问一次。"
)


_SYSTEM_EXPLAIN = """You are LoomQ's patient explainer for a reader with zero
physics background. Reply in Simplified Chinese.

Rules:
- No formulas, no bra-ket notation, no matrices. Plain words only.
- Introduce an English or technical term only if you explain it in the same
  sentence in everyday language.
- At most four short paragraphs.
- Analogies are welcome, but never let an analogy claim something the physics
  does not actually support. In particular, never say a quantum computer
  "tries every answer at once" or "is just a faster computer".
- If the question cannot be answered honestly at this level, or you are simply
  not sure, say so plainly. "这个我不确定" is always a better answer than a
  confident guess.
"""


_EXPLAIN_HINTS = (
    "是什么",
    "什么是",
    "为什么",
    "为啥",
    "怎么理解",
    "看不懂",
    "不明白",
    "解释",
    "什么意思",
    "有什么用",
    "讲讲",
    "讲一下",
    "what is",
    "why ",
    "how does",
    "explain",
)


def looks_like_task(prompt: str) -> Optional[str]:
    """Cheap local read of whether this is one of the three scored task types.

    Routes a free-form question to either the circuit agent or the explainer
    without spending a model call just to decide.  Deliberately looser than
    `_heuristic_kind_confident`, which guards a shortcut around the classifier
    and therefore has to stay conservative; here the cost of being wrong is
    only that the reader gets prose instead of a circuit.
    """
    if _looks_like_code_fragment(prompt):
        return _heuristic_kind(prompt)

    scores = _score_task_labels(prompt)
    best_label, best = max(scores.items(), key=lambda item: item[1])
    if best < 4:
        return None

    # "为什么贝尔态要用 H 和 CX" asks about a circuit rather than for one, so a
    # weak task score plus a question word means the explainer should take it.
    text = prompt.lower()
    if best < 6 and any(h in prompt or h in text for h in _EXPLAIN_HINTS):
        return None
    return best_label


def explain(question: str, context: str = "") -> str:
    """Teaching answer for questions that are not one of the three task types."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")

    missing = [name for name in llm_client.REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "missing required LoomQ L2 environment variable(s): " + ", ".join(missing)
        )

    reset_call_ledger()
    user = question.strip()
    if context.strip():
        user = f"读者正在看的内容：\n{context.strip()}\n\n读者的问题：\n{user}"
    return _chat(
        [
            {"role": "system", "content": _SYSTEM_EXPLAIN},
            {"role": "user", "content": user},
        ]
    )


def agent_chat(prompt: str) -> str:
    """Public L2 entry used by the evaluator, the CLI and the web app."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    missing = [name for name in llm_client.REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "missing required LoomQ L2 environment variable(s): " + ", ".join(missing)
        )

    reset_call_ledger()
    kind = classify(prompt)
    answer = _select_backend(prompt) if kind == "SELECT" else _circuit_loop(prompt, kind)

    if model_calls_made() == 0:
        # Every path here can fall back to local logic, which reads as a normal
        # answer while being worth nothing under the formal rules. Say so.
        return _DEGRADED_NOTICE + "\n\n" + answer
    return answer
