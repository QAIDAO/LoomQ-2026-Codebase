"""L2 natural-language agent: LLM call + local verify + bounded retry.

Uses the official LOOMQ_LLM_* OpenAI-compatible contract via ``llm_client``.
Does not hardcode answers for specific prompt strings; hidden variants must be
handled by the model. Local verification only rejects unparseable / impossible
artifacts and feeds errors back for another attempt
(``LOOMQ_LLM_MAX_CALLS``, default 3). After the budget is exhausted, returns an
explicit failure message instead of unverified QASM / backend text.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .circuit import MeasureOp
from .parse_qasm import parse_qasm
from .reference_sim import ideal_distribution

WHITELIST_GATES = "h, x, s, sdg, t, tdg, rz(θ), ry(θ), cx, cu1(θ), swap, ccx"


def _max_calls() -> int:
    """Respect official LOOMQ_LLM_MAX_CALLS injection (default 3)."""
    raw = (os.environ.get("LOOMQ_LLM_MAX_CALLS") or "3").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 3


# Back-compat for importers/tests that still read the module attribute.
MAX_CALLS = _max_calls()


_SYSTEM = f"""You are LoomQ's quantum accessibility agent.
Follow the user request carefully. Prompts may be paraphrased; obey the stated intent.

Rules for OpenQASM tasks:
- Emit OpenQASM 2.0 only, starting with: OPENQASM 2.0;
- Always include: include "qelib1.inc";
- Use only these gates: {WHITELIST_GATES}
- Use lowercase gate names (h, cx, …), never H/CX
- Declare qreg/creg before gates
- When measurement is requested, measure into classical bits
- Put the full program in a fenced ```qasm or ``` block, or as raw OPENQASM text

Rules for backend selection tasks:
- Choose exactly one backend id from the provided capability table
- Prefer simulators with queue "none" when the user wants zero wait / no queue
- Respect max_qubits vs requested qubit count
- Prefer cost "free" over "paid" / "free_quota" when the user wants no account / free local
- Prefer requires_account=false when the user wants no registration
- Reply with the exact backend id string (example: braket_local_simulator)

Rules for repair tasks:
- Preserve the user's declared target state / intent
- Return a corrected full OpenQASM 2.0 program, not a diff
"""

_BACKEND_ID_RE = re.compile(
    r"\b(spinq_taurus_simulator|spinq_cloud_qpu|originq_local_simulator|"
    r"originq_wukong|braket_local_simulator|braket_cloud)\b"
)
_QASM_FENCE_RE = re.compile(
    r"```(?:qasm|openqasm|qasm2)?\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
_QASM_BODY_RE = re.compile(
    r"(OPENQASM\s+2\.0;.*?)(?=^\s*```|\Z)",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)
_QUBIT_COUNT_RE = re.compile(
    r"(\d+)\s*(?:qubit|qubits|比特|位元)",
    re.IGNORECASE,
)


def _kit_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_capabilities() -> Dict[str, Any]:
    path = _kit_root() / "backend_capabilities.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _capabilities_prompt_block() -> str:
    data = _load_capabilities()
    lines = ["Official backend capability table (ids are exact):"]
    for backend in data.get("backends", []):
        lines.append(
            "- {id}: kind={kind}, max_qubits={max_qubits}, queue={queue}, "
            "cost={cost}, requires_account={requires_account}".format(**backend)
        )
    return "\n".join(lines)


def extract_qasm(text: str) -> Optional[str]:
    """Pull an OpenQASM 2.0 program only if it parses under the L1 whitelist."""
    if not isinstance(text, str) or not text.strip():
        return None
    candidate: Optional[str] = None
    fenced = _QASM_FENCE_RE.search(text)
    if fenced:
        body = fenced.group(1).strip()
        if re.search(r"OPENQASM\s+2\.0", body, re.IGNORECASE):
            candidate = body
        elif "qreg" in body:
            candidate = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n' + body
    if candidate is None:
        match = _QASM_BODY_RE.search(text)
        if match:
            candidate = match.group(1).strip()
    if candidate is None:
        return None
    try:
        parse_qasm(candidate)
    except Exception:
        return None
    return candidate


def extract_backend_id(text: str) -> Optional[str]:
    if not isinstance(text, str):
        return None
    match = _BACKEND_ID_RE.search(text)
    return match.group(1) if match else None


def _wants_measure(prompt: str) -> bool:
    return bool(
        re.search(r"测量|量測|measure|measurement|全测量|测一下", prompt, re.IGNORECASE)
    )


def _looks_like_backend_task(prompt: str) -> bool:
    backendish = bool(
        re.search(
            r"后端|平台|backend|simulator|选哪个|哪一个|哪家|queue|排队|等待",
            prompt,
            re.IGNORECASE,
        )
    )
    circuitish = bool(
        re.search(
            r"生成|修好|修复|报错|OPENQASM|qreg|这段代码|帮我写",
            prompt,
            re.IGNORECASE,
        )
    )
    return backendish and not circuitish


def _looks_like_qasm_task(prompt: str) -> bool:
    return bool(
        re.search(
            r"生成|修复|修好|贝尔|bell|GHZ|纠缠|OPENQASM|qasm|电路|报错",
            prompt,
            re.IGNORECASE,
        )
    )


def _backend_constraints(prompt: str) -> Dict[str, Any]:
    """Soft filters inferred from the prompt for verification only."""
    constraints: Dict[str, Any] = {}
    match = _QUBIT_COUNT_RE.search(prompt)
    if match:
        constraints["min_qubits"] = int(match.group(1))
    if re.search(r"零排队|不等待|no\s*queue|queue\s*none|立即|马上|本地", prompt, re.I):
        constraints["queue"] = "none"
    if re.search(r"模拟器|simulator|本地", prompt, re.I):
        constraints["kind"] = "simulator"
    if re.search(r"真机|qpu|硬件|芯片", prompt, re.I):
        constraints["kind"] = "qpu"
    if re.search(r"免费|不花钱|零费用|free|无账号|不用注册|无需账号", prompt, re.I):
        constraints["prefer_free_local"] = True
    return constraints


def _valid_backend_ids() -> Set[str]:
    return {str(item["id"]) for item in _load_capabilities().get("backends", [])}


def _backend_ok(backend_id: str, prompt: str) -> Tuple[bool, str]:
    table = {str(item["id"]): item for item in _load_capabilities().get("backends", [])}
    if backend_id not in table:
        return False, f"unknown backend id {backend_id!r}"
    backend = table[backend_id]
    constraints = _backend_constraints(prompt)
    min_qubits = constraints.get("min_qubits")
    if min_qubits is not None and int(backend["max_qubits"]) < int(min_qubits):
        return False, (
            f"{backend_id} max_qubits={backend['max_qubits']} < required {min_qubits}"
        )
    if constraints.get("queue") == "none" and backend.get("queue") != "none":
        return False, f"{backend_id} has queue={backend.get('queue')}, need queue=none"
    kind = constraints.get("kind")
    if kind == "simulator" and backend.get("kind") != "simulator":
        return False, f"{backend_id} is kind={backend.get('kind')}, need simulator"
    if kind == "qpu" and backend.get("kind") != "qpu":
        return False, f"{backend_id} is kind={backend.get('kind')}, need qpu"
    if constraints.get("prefer_free_local"):
        if backend.get("requires_account"):
            return False, f"{backend_id} requires_account=true"
        if backend.get("cost") not in {"free"}:
            return False, f"{backend_id} cost={backend.get('cost')}, prefer free local"
    return True, "ok"


def _message_text(response: Dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("LLM response missing choices[0].message.content") from exc
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        content = "".join(parts)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM returned empty content")
    return content


def _verify_qasm(qasm: str, prompt: str) -> Tuple[bool, str]:
    try:
        circuit = parse_qasm(qasm)
    except Exception as exc:  # noqa: BLE001 — feed any parse failure back to the model
        return False, f"parse error: {type(exc).__name__}: {exc}"
    if circuit.n_qubits() < 1:
        return False, "circuit has no qubits"
    try:
        ideal_distribution(qasm)
    except Exception as exc:  # noqa: BLE001
        return False, f"semantic/sim error: {type(exc).__name__}: {exc}"
    has_measure = any(isinstance(op, MeasureOp) for op in circuit.ops)
    if _wants_measure(prompt) and not has_measure:
        return False, "measurement requested but circuit has no measure ops"
    return True, "ok"


def _chat(messages: Sequence[Dict[str, str]]) -> str:
    # Import inside the call so non-L2 imports of loomq stay light-weight.
    import llm_client

    return _message_text(llm_client.chat_completion(list(messages)))


def agent_chat(prompt: str) -> str:
    """L2 entry: at least one LLM call, optional verify/retry within budget."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    user_prompt = prompt.strip()
    system = _SYSTEM + "\n\n" + _capabilities_prompt_block()
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]

    budget = _max_calls()
    last_text = ""
    calls = 0
    while calls < budget:
        last_text = _chat(messages)
        calls += 1

        qasm = extract_qasm(last_text)
        backend_id = extract_backend_id(last_text)
        backend_task = _looks_like_backend_task(user_prompt)
        qasm_task = _looks_like_qasm_task(user_prompt)

        if backend_id and (backend_task or not qasm):
            ok, reason = _backend_ok(backend_id, user_prompt)
            if ok:
                return last_text
            if calls >= budget:
                allowed = ", ".join(sorted(_valid_backend_ids()))
                return (
                    f"[LoomQ Agent] 已达到 {budget} 次调用上限，"
                    f"无法获得有效后端 ID（最后一次原因：{reason}）。"
                    f"可用后端：{allowed}"
                )
            allowed = ", ".join(sorted(_valid_backend_ids()))
            messages.append({"role": "assistant", "content": last_text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Backend id rejected by capability checks ({reason}). "
                        f"Choose another exact id from: {allowed}. "
                        "State the id clearly in your reply."
                    ),
                }
            )
            continue

        if qasm:
            ok, reason = _verify_qasm(qasm, user_prompt)
            if ok:
                return last_text
            if calls >= budget:
                return (
                    f"[LoomQ Agent] 已达到 {budget} 次调用上限，"
                    f"无法生成合法的 OpenQASM 2.0 电路（最后一次原因：{reason}）。"
                )
            messages.append({"role": "assistant", "content": last_text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous OpenQASM failed local verification "
                        f"({reason}). Return a corrected full OpenQASM 2.0 "
                        "program that satisfies the original intent. Use only "
                        f"whitelist gates: {WHITELIST_GATES}."
                    ),
                }
            )
            continue

        if backend_task and calls < budget:
            messages.append({"role": "assistant", "content": last_text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Reply again and include exactly one backend id from "
                        "the capability table (e.g. braket_local_simulator)."
                    ),
                }
            )
            continue

        if qasm_task and calls < budget:
            messages.append({"role": "assistant", "content": last_text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "No valid OpenQASM 2.0 program was found. Return a "
                        "complete OPENQASM 2.0 circuit in a fenced code block."
                    ),
                }
            )
            continue

        if qasm_task:
            return (
                f"[LoomQ Agent] 已达到 {budget} 次调用上限，"
                "未找到合法的 OpenQASM 2.0 电路。"
            )
        if backend_task:
            return (
                f"[LoomQ Agent] 已达到 {budget} 次调用上限，"
                "未能给出有效后端 ID。"
            )
        return last_text

    return f"[LoomQ Agent] 已达到 {budget} 次调用上限，未能完成请求。"
