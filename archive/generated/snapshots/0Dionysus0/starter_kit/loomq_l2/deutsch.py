"""Deutsch algorithm helpers (1-bit Deutsch–Jozsa), matching the video riddle.

Video: Looking Glass Universe — “What can my homemade quantum computer do?”
https://www.youtube.com/watch?v=tHfGucHtLqo

Classical story:
  Secret f:{0,1}->{0,1} is one of four functions.
  Ask only: is f CONSTANT or BALANCED?
  A normal computer needs TWO queries; the stranger allows only ONE.

Quantum story (Deutsch):
  Prepare both inputs at once (|+> on data, |-> on ancilla),
  apply the secret oracle once, then measure the data qubit.
  Measure 0 => constant; measure 1 => balanced.
"""

from __future__ import annotations

import secrets
from typing import Any, Dict, List, Literal, Optional

from loomq_l2.sessions import SessionStore

FunctionId = Literal["f1", "f2", "f3", "f4"]
Kind = Literal["balanced", "constant"]

# Names aligned with the video's F1–F4.
FUNCTIONS: Dict[FunctionId, Dict[str, Any]] = {
    "f1": {
        "id": "f1",
        "name": "F1 · 原样通过",
        "rule": "0→0，1→1",
        "kind": "balanced",
        "table": {0: 0, 1: 1},
        "plain": "输入什么就输出什么（一半 0、一半 1 → 平衡）",
    },
    "f2": {
        "id": "f2",
        "name": "F2 · 对调",
        "rule": "0→1，1→0",
        "kind": "balanced",
        "table": {0: 1, 1: 0},
        "plain": "输入反过来（一半 0、一半 1 → 平衡）",
    },
    "f3": {
        "id": "f3",
        "name": "F3 · 永远 0",
        "rule": "0→0，1→0",
        "kind": "constant",
        "table": {0: 0, 1: 0},
        "plain": "不管输入，总是吐出 0（恒定）",
    },
    "f4": {
        "id": "f4",
        "name": "F4 · 永远 1",
        "rule": "0→1，1→1",
        "kind": "constant",
        "table": {0: 1, 1: 1},
        "plain": "不管输入，总是吐出 1（恒定）",
    },
}


def classical_query(function_id: FunctionId, bit: int) -> int:
    if bit not in (0, 1):
        raise ValueError("bit must be 0 or 1")
    return int(FUNCTIONS[function_id]["table"][bit])


def _oracle_qasm_lines(function_id: FunctionId) -> List[str]:
    """Two-qubit oracle U|x>|y> = |x>|y⊕f(x)> on q[0]=data, q[1]=ancilla."""
    if function_id == "f1":  # f(x)=x
        return ["cx q[0],q[1];"]
    if function_id == "f2":  # f(x)=1-x
        return ["x q[1];", "cx q[0],q[1];"]
    if function_id == "f3":  # f(x)=0
        return ["// constant-0 oracle: do nothing"]
    if function_id == "f4":  # f(x)=1
        return ["x q[1];"]
    raise KeyError(function_id)


_PREFIX_LINES: List[str] = [
    "OPENQASM 2.0;",
    'include "qelib1.inc";',
    "qreg q[2];",
    "creg c[1];",
    "// 辅助位先翻到 |1>，再用 H 变成 |->，黑盒的答案就会被写进「相位」里",
    "x q[1];",
    "h q[0];",
    "h q[1];",
    "// 下面这一段就是黑盒，整个电路只用它一次",
]

_SUFFIX_LINES: List[str] = [
    "// 再来一次 H，把藏在相位里的答案变成可以直接读出的 0 / 1",
    "h q[0];",
    "measure q[0] -> c[0];",
]

HIDDEN_ORACLE_LINE = "// ██████  藏起来的黑盒，揭晓后这里会显示它真正的门  ██████"


def circuit_parts(function_id: FunctionId) -> Dict[str, List[str]]:
    """Deutsch circuit split into the fixed scaffold and the swappable oracle.

    The UI puts the calibration run and the secret run side by side, so it has
    to be able to point at exactly which lines differ between them.
    """
    return {
        "prefix": list(_PREFIX_LINES),
        "oracle": _oracle_qasm_lines(function_id),
        "suffix": list(_SUFFIX_LINES),
    }


def deutsch_qasm(function_id: FunctionId) -> str:
    """Full Deutsch circuit; measure data qubit into c[0]."""
    parts = circuit_parts(function_id)
    return "\n".join(parts["prefix"] + parts["oracle"] + parts["suffix"]) + "\n"


def masked_qasm(function_id: FunctionId) -> str:
    """Display-only circuit with the oracle blanked out.

    Shown while the box is still secret: the real gates would give the answer
    away before the user has had a chance to work it out.
    """
    parts = circuit_parts(function_id)
    return "\n".join(parts["prefix"] + [HIDDEN_ORACLE_LINE] + parts["suffix"]) + "\n"


def ideal_distribution(function_id: FunctionId) -> Dict[str, float]:
    """Noiseless Deutsch reading: constant lands on "0", balanced on "1"."""
    kind = FUNCTIONS[function_id]["kind"]
    return {"0": 1.0} if kind == "constant" else {"1": 1.0}


def interpret_counts(counts: Dict[str, int]) -> Dict[str, Any]:
    """Map measurement histogram to constant/balanced (Deutsch)."""
    # little-endian single bit keys: "0" / "1"
    zero = int(counts.get("0", 0))
    one = int(counts.get("1", 0))
    # also accept padded keys just in case
    for key, value in counts.items():
        if key.endswith("0") and key != "0":
            zero += int(value)
        if key.endswith("1") and key != "1":
            one += int(value)
    total = zero + one
    if total <= 0:
        return {
            "verdict": None,
            "confidence": 0.0,
            "zero": 0,
            "one": 0,
            "plain": "没有测到结果。",
        }
    # Ideal Deutsch: constant -> mostly 0; balanced -> mostly 1
    if zero >= one:
        verdict: Optional[Kind] = "constant"
        conf = zero / total
    else:
        verdict = "balanced"
        conf = one / total
    plain = (
        "收据偏「0」→ 判断为【恒定】（constant）。"
        if verdict == "constant"
        else "收据偏「1」→ 判断为【平衡】（balanced）。"
    )
    return {
        "verdict": verdict,
        "confidence": conf,
        "zero": zero,
        "one": one,
        "total": total,
        "plain": plain,
    }


def run_deutsch(function_id: FunctionId, shots: int = 1024, target: str = "braket") -> Dict[str, Any]:
    """Execute Deutsch on the shared L1 adapter (IR → backend)."""
    import adapter

    if target not in adapter.SUPPORTED_TARGETS:
        raise ValueError(f"unknown target {target!r}")
    qasm = deutsch_qasm(function_id)
    result = adapter.run(qasm, target, shots)
    counts = result.get("counts") or {}
    reading = interpret_counts(counts)
    meta = FUNCTIONS[function_id]
    correct = reading["verdict"] == meta["kind"]
    return {
        "function_id": function_id,
        "secret_kind": meta["kind"],
        "secret_name": meta["name"],
        "secret_rule": meta["rule"],
        "qasm": qasm,
        "counts": counts,
        "run_backend": result.get("backend"),
        "shots": shots,
        "reading": reading,
        "correct": correct,
        "so_what": (
            "量子这边厉害的地方：一次调用黑盒，却问到了「恒定还是平衡」。"
            "普通电脑最少要问两次。这不是因为量子「什么都更快」，"
            "而是这个问题可以被改写成：先两个输入一起送进去，再用干涉把答案挤到一次测量里。"
            if correct
            else "这次读数不够干净。理想 Deutsch 下恒定应几乎全是 0，平衡应几乎全是 1；可以再跑一次。"
        ),
    }


# ---------------------------------------------------------------------------
# Secret-box sessions.
#
# The puzzle only works if the box is genuinely unknown, so the chosen function
# lives on the server and is never sent to the browser until the user asks to
# see it.  That also keeps the model out of it: the assistant is asked to build
# an interrogation method for a box whose answer the user already knows, and the
# same method is then pointed at the secret one.
# ---------------------------------------------------------------------------

_STORE = SessionStore()


def new_session() -> Dict[str, Any]:
    """Hide one of the four functions and hand back only an opaque id."""
    session_id = _STORE.create(
        {
            "secret": secrets.choice(list(FUNCTIONS.keys())),
            "classical_queries": 0,
            "quantum_queries": 0,
            "revealed": False,
        }
    )
    return {"session_id": session_id, "classical_queries": 0, "quantum_queries": 0}


def _session(session_id: str) -> Dict[str, Any]:
    return _STORE.get(session_id)


def session_classical_query(session_id: str, bit: int) -> Dict[str, Any]:
    """One ordinary query. Reveals the output only, never the kind."""
    if bit not in (0, 1):
        raise ValueError("bit must be 0 or 1")
    state = _session(session_id)
    with _STORE.lock:
        state["classical_queries"] += 1
        used = int(state["classical_queries"])
    output = classical_query(state["secret"], bit)  # type: ignore[arg-type]
    return {
        "bit": bit,
        "output": output,
        "classical_queries": used,
        "plain": f"你把 {bit} 丢进黑盒，它吐出了 {output}。",
    }


def session_quantum_run(
    session_id: str, shots: int = 1024, target: str = "braket"
) -> Dict[str, Any]:
    """Run Deutsch against the secret box: one oracle call, one verdict."""
    state = _session(session_id)
    secret: FunctionId = state["secret"]
    with _STORE.lock:
        state["quantum_queries"] += 1
        used = int(state["quantum_queries"])
    result = run_deutsch(secret, shots=shots, target=target)
    # Everything that would give the answer away stays on the server until the
    # user asks to see it.
    for leak in ("secret_kind", "secret_name", "secret_rule", "correct", "so_what"):
        result.pop(leak, None)
    result["function_id"] = None
    result["qasm"] = masked_qasm(secret)
    result["oracle_calls"] = 1
    result["quantum_queries"] = used
    result["classical_queries"] = int(state["classical_queries"])
    return result


def session_reveal(session_id: str) -> Dict[str, Any]:
    """Open the box: show what it was and the gates that were hidden."""
    state = _session(session_id)
    secret: FunctionId = state["secret"]
    with _STORE.lock:
        state["revealed"] = True
    meta = FUNCTIONS[secret]
    return {
        "function_id": secret,
        "name": meta["name"],
        "rule": meta["rule"],
        "kind": meta["kind"],
        "plain": meta["plain"],
        "qasm": deutsch_qasm(secret),
        "oracle": circuit_parts(secret)["oracle"],
        "classical_queries": int(state["classical_queries"]),
        "quantum_queries": int(state["quantum_queries"]),
    }


def check_against_ideal(
    counts: Dict[str, int], function_id: FunctionId, threshold: float = 0.9
) -> Dict[str, Any]:
    """Did a candidate circuit really behave like Deutsch on a known box?

    Only c[0] matters, so wider readouts are marginalised down to their last
    classical bit before the comparison.
    """
    from loomq_l2.agent import hellinger_fidelity

    total = sum(int(v) for v in counts.values()) if counts else 0
    if total <= 0:
        return {
            "passed": False,
            "fidelity": 0.0,
            "reason": "这个电路没有产生任何测量结果，没法判断它对不对。",
        }

    observed: Dict[str, float] = {}
    for key, value in counts.items():
        bit = str(key)[-1:]
        observed[bit] = observed.get(bit, 0.0) + int(value) / total

    ideal = ideal_distribution(function_id)
    fidelity = hellinger_fidelity(observed, ideal)
    expected_bit = next(iter(ideal))
    kind_label = "恒定" if FUNCTIONS[function_id]["kind"] == "constant" else "平衡"
    passed = fidelity >= threshold
    if passed:
        reason = (
            f"这个盒子是「{kind_label}」的，理想情况下读数应该几乎全是 {expected_bit}，"
            f"实测吻合度 {fidelity:.2f}——方法管用。"
        )
    else:
        reason = (
            f"这个盒子是「{kind_label}」的，读数本该几乎全是 {expected_bit}，"
            f"但实测吻合度只有 {fidelity:.2f}，说明这个电路还不是正确的审问方法。"
        )
    return {
        "passed": passed,
        "fidelity": fidelity,
        "threshold": threshold,
        "expected_bit": expected_bit,
        "kind": FUNCTIONS[function_id]["kind"],
        "observed": observed,
        "reason": reason,
    }


def calibration_payload(function_id: FunctionId) -> Dict[str, Any]:
    """A box whose answer the user already knows, used to prove the method."""
    meta = FUNCTIONS[function_id]
    return {
        "function_id": function_id,
        "name": meta["name"],
        "rule": meta["rule"],
        "kind": meta["kind"],
        "plain": meta["plain"],
        "ideal": ideal_distribution(function_id),
        "qasm": deutsch_qasm(function_id),
        "parts": circuit_parts(function_id),
    }


def lesson_payload() -> Dict[str, Any]:
    """Static copy for the web explorable (video-aligned)."""
    return {
        "id": "deutsch",
        "video": {
            "title": "What can my homemade quantum computer do?",
            "url": "https://www.youtube.com/watch?v=tHfGucHtLqo",
            "credit": "Looking Glass Universe（自制光学量子计算机演示 Deutsch 算法）",
        },
        "title": "黑盒谜题：一次机会，分出恒定还是平衡",
        "card_blurb": "视频同款：神秘函数只让你问一次——普通电脑不够，量子有一招。",
        "duration": "约 5–8 分钟",
        "why": {
            "q1_label": "我为什么要做这个实验？",
            "q1": (
                "媒体常说量子电脑是超级电脑。视频作者想纠正："
                "大多数时候它并不更快，只是有少数题型，经典算法会很慢，"
                "而量子有一招特殊算法。这个谜题就是用来感受那一招的。"
            ),
            "q2_label": "这个谜题和我有什么关系？",
            "q2": (
                "一个陌生人有黑盒函数：你丢进 0 或 1，它吐出 0 或 1。"
                "共有四种可能函数。他不让你猜是哪一种，只问："
                "它是「恒定」（永远同一种输出）还是「平衡」（两种输出各一半）？"
                "普通办法要问两次；他只准问一次——这才变成谜题。"
            ),
            "q3_label": "为什么要关心恒定 / 平衡？",
            "q3": (
                "不是因为人生需要猜黑盒，而是因为它是最短的例子："
                "展示量子可以『两个输入一起送进去』，再用测量取出你真正想要的那一比特信息。"
                "视频里说：这恰恰是量子擅长、又很难再找到很多类似算法的地方。"
            ),
            "what_driving_means": (
                "「驱动」= 选好秘密函数（或让网页替你藏一个）→ "
                "经典演示问两次 → 量子电路只调用黑盒一次 → 条形图读出恒定/平衡。"
            ),
        },
        "functions": list(FUNCTIONS.values()),
        "steps": [
            {"id": "story", "label": "听谜题"},
            {"id": "classical", "label": "经典：要两次"},
            {"id": "quantum", "label": "量子：一次"},
            {"id": "challenge", "label": "挑战"},
            {"id": "result", "label": "收据"},
        ],
    }
