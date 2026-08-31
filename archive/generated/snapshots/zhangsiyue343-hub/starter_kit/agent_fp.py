#!/usr/bin/env python3
"""L2 agent as a functional pipeline of pure stages.

Design: data flows through frozen records; behaviour lives in functions that
are composed with small higher-order combinators (`pipe`, `retry`, `rescue`).
The LLM transport is an injected dependency — nothing here reads os.environ
directly (config arrives via the DI container) and no state mutates between
stages, which makes every stage trivially testable in isolation.

Pipeline (generate / fix share one shape):

    prompt ─▶ extract_intent ─▶ [LLM draft ⇄ verify ⇄ repair]ⁿ ─▶ format

Verification runs each candidate circuit on the built-in simulator and
compares against the analytically-known ideal distribution, closing the
loop required by the rules. Backend selection is solved deterministically
over the live plugin capability table; the LLM only phrases the reasoning.
"""

from __future__ import annotations

import functools
import itertools
import math
import re
import time
from dataclasses import dataclass, field, replace
from typing import Callable, Mapping, Optional

try:
    from .config import LoomqConfig
    from .gates import prompt_whitelist
    from .ir import Circuit
    from .parser import ParseError, parse_source
    from .simulator import run_circuit
except ImportError:
    from config import LoomqConfig
    from gates import prompt_whitelist
    from ir import Circuit
    from parser import ParseError, parse_source
    from simulator import run_circuit


class AgentError(RuntimeError):
    pass


# ==========================================================================
# higher-order combinators
# ==========================================================================

def pipe(*functions: Callable) -> Callable:
    """Left-to-right function composition."""
    def routed(value):
        for fn in functions:
            value = fn(value)
        return value
    return routed


def retry(max_attempts: int = 2, exceptions: tuple = (Exception,),
          delay: float = 0.0, budget_until: Optional[float] = None) -> Callable:
    """Retry combinator: returns a wrapped callable, transparently."""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            last = None
            for attempt_index in range(max_attempts):
                if budget_until is not None and time.monotonic() > budget_until:
                    break
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last = exc
                    if delay and attempt_index < max_attempts - 1:
                        time.sleep(delay)
            raise last
        return wrapped
    return decorator


def rescue(fallback_value: Callable) -> Callable:
    """Turn a raising function into one that yields `fallback_value()`."""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                return fallback_value()
        return wrapped
    return decorator


# ==========================================================================
# immutable domain records
# ==========================================================================

@dataclass(frozen=True)
class Intent:
    task: str                       # generate | fix | select
    family: Optional[str] = None    # ghz | bell | w | uniform | None
    n_qubits: Optional[int] = None
    source_qasm: Optional[str] = None
    constraints: tuple = ()         # selection constraint tags
    raw_prompt: str = ""


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str = ""
    fidelity: float = 1.0
    observed_counts: Mapping[str, int] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.observed_counts is None:
            object.__setattr__(self, "observed_counts", {})


@dataclass(frozen=True)
class Draft:
    qasm: str
    origin: str                     # llm | template | repair
    verdict: Verdict = Verdict(False, "not verified")


# ==========================================================================
# pure intent extraction
# ==========================================================================

_ZH_NUMERALS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
                "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

_QUBIT_PATTERNS = (
    re.compile(r"(\d+)\s*(?:个)?\s*(?:量子)?比特", re.IGNORECASE),
    re.compile(r"(\d+)\s*(?:个)?\s*qubits?", re.IGNORECASE),
    re.compile(r"(\d+)\s*(?:位|qb)\b", re.IGNORECASE),
)
_FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ghz": ("ghz", "cat state", "猫态"),
    "bell": ("bell", "贝尔", "epr", "bell pair"),
    "w": ("w态", "w 态", "w-state", "w state"),
    "uniform": ("均匀叠加", "等叠加", "等幅叠加", "等幅",
                "uniform superposition", "all superposition"),
}

_SELECT_KEYWORDS = ("选哪个", "选后端", "选平台", "推荐", "后端", "平台",
                    "排队", "queue", "backend", "跑在哪", "提交到")
_FIX_KEYWORDS = ("报错", "修复", "修好", "纠错", "帮我修", "错误",
                 "error", "fix", "repair", "broken", "debug", "bug",
                 "跑不出来", "跑不通", "哪里错了", "运行失败")


def _detect_family(text: str) -> Optional[str]:
    lowered = text.lower()
    for family, keywords in _FAMILY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return family
    if "最大纠缠" in lowered and re.search(r"(两比特|2\s*比特)", lowered):
        return "bell"                     # two-qubit maximally entangled == Bell
    if "纠缠" in lowered:
        return "ghz"
    return None
def _detect_n(text: str) -> Optional[int]:
    for pattern in _QUBIT_PATTERNS:
        match = pattern.search(text)
        if match:
            n = int(match.group(1))
            if 1 <= n <= 64:
                return n
    for char in text:
        if char in _ZH_NUMERALS:
            after = text[text.index(char):text.index(char) + 6]
            if re.search(r"[比特位]", after):
                return _ZH_NUMERALS[char]
    return None


def extract_qasm_text(text: str) -> Optional[str]:
    """Pull a complete OpenQASM program out of arbitrary prose/model output."""
    if not isinstance(text, str):
        return None
    match = re.search(r"OPENQASM\s*2\.0\s*;.*", text,
                      re.DOTALL | re.IGNORECASE)
    if match:
        snippet = match.group(0)
        stop = re.search(r"```|\Z", snippet)
        program = snippet[:stop.start()].strip() if stop else snippet.strip()
        return _ensure_header(program)
    fence = re.search(r"```(?:qasm|openqasm)?\s*\n(.*?)```", text,
                      re.DOTALL | re.IGNORECASE)
    body = fence.group(1).strip() if fence else ""
    if not body:
        body = extract_bare_snippet(text) or ""
    if "qreg" not in body.lower():
        return None
    return _ensure_header(body)


def _ensure_header(program: str) -> str:
    if re.match(r"\s*OPENQASM", program, re.IGNORECASE):
        return program
    header = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
    return header + program


_BARE_GATE_TOKEN = re.compile(
    r"\b(?:sdg|tdg|rz|ry|cu1|swap|ccx|h|x|s|t|cx|qreg|creg|measure)\b",
    re.IGNORECASE)


def extract_bare_snippet(text: str) -> Optional[str]:
    """Best-effort extraction of gate-level QASM fragments from prose."""
    if not isinstance(text, str):
        return None
    lines = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if _BARE_GATE_TOKEN.search(stripped):
            lines.append(stripped)
    if not lines:
        return None
    joined = "\n".join(lines)
    first = _BARE_GATE_TOKEN.search(joined)
    last_semi = joined.rfind(";")
    fragment = joined[first.start():last_semi + 1] if last_semi > first.start() \
        else joined[first.start():]
    return fragment.strip() or None


def extract_intent(prompt: str) -> Intent:
    lowered = prompt.lower()
    if any(k in lowered for k in _SELECT_KEYWORDS):
        return Intent("select", constraints=_constraint_keywords(lowered),
                      raw_prompt=prompt)
    source = extract_qasm_text(prompt)
    if any(k in lowered for k in _FIX_KEYWORDS) or source is not None:
        family = _detect_family(prompt)
        return Intent("fix",
                      family=family,
                      n_qubits=_detect_n(prompt) or _default_n(family),
                      source_qasm=source or extract_bare_snippet(prompt),
                      raw_prompt=prompt)
    family = _detect_family(prompt)
    return Intent("generate",
                  family=family,
                  n_qubits=_detect_n(prompt) or _default_n(family),
                  raw_prompt=prompt)


def _default_n(family: Optional[str]) -> int:
    return 2 if family == "bell" else 3


def _constraint_keywords(lowered: str) -> tuple:
    found = []
    table = (("zero_queue", ("零排队", "无排队", "不排队", "零等待", "no queue", "zero queue")),
             ("simulator", ("模拟器", "仿真", "simulator")),
             ("real_device", ("真机", "真实机", "实机", "qpu", "real device")),
             ("free", ("免费", "零成本", "不花钱", "free")),
             ("no_account", ("无需账号", "不用注册", "no account", "without account")))
    for tag, keywords in table:
        if any(k in lowered for k in keywords):
            found.append(tag)
    return tuple(found)


# ==========================================================================
# pure circuit synthesizers (template layer, no LLM involved)
# ==========================================================================

def _render_qasm(body_lines: list[str], n: int) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";',
             "qreg q[%d];" % n, "creg c[%d];" % n]
    lines.extend(body_lines)
    lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"


def synthesize_ghz(n: int) -> str:
    lines = ["h q[0];"]
    lines.extend("cx q[%d], q[%d];" % (i, i + 1) for i in range(n - 1))
    return _render_qasm(lines, n)


def synthesize_bell(_n: int) -> str:
    return _render_qasm(["h q[0];", "cx q[0], q[1];"], 2)


def synthesize_uniform(n: int) -> str:
    return _render_qasm(["h q[%d];" % i for i in range(n)], n)


def _fmt_angle(value: float) -> str:
    try:
        from .targets import format_pi_expression
    except ImportError:
        from targets import format_pi_expression
    return format_pi_expression(value)


def _cry(theta: float, control: int, target: int,
         open_control: bool = False) -> list[str]:
    """Controlled-RY decomposed into whitelisted gates."""
    half = theta / 2.0
    lines: list[str] = []
    if open_control:
        lines.append("x q[%d];" % control)
    lines.extend([
        "ry(%s) q[%d];" % (_fmt_angle(half), target),
        "cx q[%d], q[%d];" % (control, target),
        "ry(%s) q[%d];" % (_fmt_angle(-half), target),
        "cx q[%d], q[%d];" % (control, target),
    ])
    if open_control:
        lines.append("x q[%d];" % control)
    return lines


def synthesize_w(n: int) -> Optional[str]:
    """Exact W-state circuits for n <= 3 (hand-verified); None otherwise.

    W2 = Bell followed by X on q0.  W3 = RY split (1/3) + open-controlled
    RY split (1/2 of the remainder) + open-controlled Toffoli exciting q2
    on the all-zero branch.  Larger n deliberately yields None so the
    pipeline degrades gracefully instead of emitting wrong physics.
    """
    if n == 1:
        return _render_qasm(["x q[0];"], 1)
    if n == 2:
        return _render_qasm(["h q[0];", "cx q[0], q[1];", "x q[0];"], 2)
    if n != 3:
        return None
    alpha0 = 2.0 * math.asin(math.sqrt(1.0 / 3.0))
    lines = ["ry(%s) q[0];" % _fmt_angle(alpha0)]
    lines.extend(_cry(math.pi / 2.0, control=0, target=1, open_control=True))
    lines.extend(["x q[0];", "x q[1];",
                  "ccx q[0], q[1], q[2];",
                  "x q[1];", "x q[0];"])
    return _render_qasm(lines, 3)


SYNTHESIZERS: Mapping[str, Callable[[int], Optional[str]]] = {
    "ghz": synthesize_ghz,
    "bell": synthesize_bell,
    "uniform": synthesize_uniform,
    "w": synthesize_w,
}


def synthesize(intent: Intent) -> Optional[str]:
    builder = SYNTHESIZERS.get(intent.family or "")
    if builder is None or intent.n_qubits is None:
        return None
    try:
        return builder(intent.n_qubits)
    except (ValueError, KeyError):
        return None


def ideal_distribution(family: Optional[str], n: Optional[int]) -> Optional[dict]:
    if family in ("ghz", "bell") and n:
        return {"0" * n: 0.5, "1" * n: 0.5}
    if family == "w" and n:
        keys = itertools.product("10", repeat=n)
        return {"".join(k): 1.0 / n for k in keys if k.count("1") == 1}
    if family == "uniform" and n:
        return {format(i, "0%db" % n): 1.0 / (1 << n) for i in range(1 << n)}
    return None


# ==========================================================================
# verification (simulation-in-the-loop)
# ==========================================================================

def hellinger_fidelity(observed: Mapping[str, float],
                       expected: Mapping[str, float]) -> float:
    states = set(observed) | set(expected)
    distance = sum(
        (observed.get(s, 0.0) ** 0.5 - expected.get(s, 0.0) ** 0.5) ** 2
        for s in states) ** 0.5 / (2 ** 0.5)
    return max(0.0, min(1.0, 1.0 - distance))


def _adaptive_verification_shots(base_shots: int, n_qubits: int) -> int:
    """Wide distributions need more samples for a stable Hellinger verdict.

    Multinomial noise gives E[Hellinger distance] ~= sqrt(K/(8N)); holding
    fidelity >= ~0.98 requires N >= ~256*K. Cheap because the simulator
    samples from one computed distribution.
    """
    k = 1 << n_qubits
    return max(base_shots, min(256 * k, 262144))


def verify_qasm(qasm: str, intent: Intent, shots: int = 2048) -> Verdict:
    """Structural + distributional verification of a candidate program."""
    try:
        program = parse_source(qasm, _GATE_TABLE())
    except ValueError as exc:                    # ParseError subclasses ValueError
        return Verdict(False, "parse: %s" % exc)
    try:
        from .ir import lower as _lower
    except ImportError:
        from ir import lower as _lower
    try:
        circuit = _lower(program)
    except ValueError as exc:
        return Verdict(False, "lower: %s" % exc)
    if intent.n_qubits and circuit.n_qubits != intent.n_qubits:
        return Verdict(False,
                       "expected %d qubits, circuit has %d"
                       % (intent.n_qubits, circuit.n_qubits))
    measured_clbits = {c for _q, c in circuit.measures}
    if circuit.measures and len(measured_clbits) < circuit.n_clbits:
        return Verdict(False, "not all classical bits are measured")
    ideal = ideal_distribution(intent.family, intent.n_qubits)
    eff_shots = _adaptive_verification_shots(shots, circuit.n_qubits)
    try:
        counts = run_circuit(circuit, eff_shots)
    except Exception as exc:
        return Verdict(False, "simulation failed: %s" % exc)
    if ideal is not None:
        observed = {key: value / eff_shots for key, value in counts.items()}
        fidelity = hellinger_fidelity(observed, ideal)
        k_states = 1 << circuit.n_qubits
        threshold = 0.97 if k_states <= 1024 else 0.95
        if fidelity < threshold:
            top = sorted(counts.items(), key=lambda kv: -kv[1])[:4]
            return Verdict(False,
                           "fidelity %.3f < %.2f; sampled top states %r "
                           "but ideal is %r" % (fidelity, threshold, top,
                                                sorted(ideal.items())[:4]),
                           fidelity, dict(counts))
        return Verdict(True, "distribution matches ideal (%s)" % intent.family,
                       fidelity, dict(counts))
    return Verdict(True, "structure valid (no analytic ideal for this request)",
                   1.0, dict(counts))


def _GATE_TABLE():
    try:
        from .gates import GATES
    except ImportError:
        from gates import GATES
    return GATES


# ==========================================================================
# LLM interaction (transport injected)
# ==========================================================================

def _system_prompt_generation() -> str:
    return (
        "You translate natural-language quantum computing requests into "
        "OpenQASM 2.0 programs. Output ONLY one complete program inside a "
        "```qasm fenced block. Rules:\n"
        "1. Allowed gates: %s.\n"
        "2. Declare registers exactly as qreg q[N]; creg c[N]; and measure "
        "every qubit with 'measure q -> c;'.\n"
        "3. Build entangled states with h on qubit 0 followed by a cx chain.\n"
        "4. No commentary outside the fence."
    ) % prompt_whitelist()


def _system_prompt_repair() -> str:
    return (
        "You repair OpenQASM 2.0 programs while preserving the user's stated "
        "intent (target state and qubit count). Fix undeclared registers, "
        "gate-name case, arity errors, and syntax problems. Allowed gates: %s. "
        "Always declare qreg q[N]; creg c[N]; and measure every qubit. "
        "Output ONLY the corrected program inside a ```qasm fence."
    ) % prompt_whitelist()


def _call_llm(transport: Callable, system: str, user: str) -> str:
    reply = transport([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])
    try:
        content = reply["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AgentError("malformed model response envelope") from exc
    if not isinstance(content, str) or not content.strip():
        raise AgentError("empty model response")
    return content


def _repair_user_message(prompt: str, broken: str, diagnosis: str) -> str:
    return ("User request:\n%s\n\nCurrent program:\n%s\n\n"
            "Verification diagnostic:\n%s\n\nReturn the corrected full program."
            % (prompt, broken, diagnosis))


# ==========================================================================
# pipelines
# ==========================================================================

def _llm_draft_pipeline(transport: Callable, config: LoomqConfig,
                        system: str) -> Callable[[str], str]:
    guarded = retry(max_attempts=2, exceptions=(AgentError,))
    fetch = guarded(lambda user: _call_llm(transport, system, user))

    def run(user_prompt: str) -> str:
        reply = fetch(user_prompt)
        qasm = extract_qasm_text(reply)
        if not qasm:
            raise AgentError("model output contained no QASM program")
        return qasm
    return run


def generate_pipeline(transport: Callable, config: LoomqConfig,
                      deadline: Optional[float] = None) -> Callable[[Intent], Draft]:
    draft_llm = _llm_draft_pipeline(transport, config, _system_prompt_generation())

    def run(intent: Intent) -> Draft:
        attempts: list[tuple[str, Verdict]] = []

        def consider(qasm: str, origin: str) -> Optional[Draft]:
            verdict = verify_qasm(qasm, intent,
                                  shots=config.llm.verification_shots)
            attempts.append((origin, verdict))
            if verdict.ok:
                return Draft(qasm, origin, verdict)
            return None

        produced = None
        if transport is not None:
            request_text = intent.raw_prompt or _reconstruct_request(intent)
            try:
                qasm = draft_llm(request_text)
                produced = consider(qasm, "llm")
            except Exception:
                produced = None
            rounds_left = config.llm.repair_rounds
            while produced is None and rounds_left > 0:
                if deadline is not None and time.monotonic() > deadline:
                    break
                rounds_left -= 1
                broken_qasm, diagnosis = _last_failure(attempts)
                if broken_qasm is None:
                    break
                try:
                    fixed = _call_llm(
                        transport, _system_prompt_repair(),
                        _repair_user_message(request_text,
                                             broken_qasm, diagnosis))
                    candidate = extract_qasm_text(fixed)
                    produced = consider(candidate, "repair") if candidate else None
                except Exception:
                    break
        if produced is None:
            template = synthesize(intent)
            if template is not None:
                verdict = verify_qasm(template, intent,
                                      shots=config.llm.verification_shots)
                produced = Draft(template, "template", verdict)
        if produced is None or not produced.verdict.ok:
            reason = attempts[-1][1].reason if attempts else "no candidate produced"
            raise AgentError("generation failed: %s" % reason)
        return produced
    return run


def fix_pipeline(transport: Callable, config: LoomqConfig,
                 deadline: Optional[float] = None) -> Callable[[Intent], Draft]:
    def run(intent: Intent) -> Draft:
        if not intent.source_qasm and transport is None:
            raise AgentError("no QASM found in the request to repair")
        attempts: list[tuple[str, Verdict]] = []

        def consider(qasm: str, origin: str) -> Optional[Draft]:
            verdict = verify_qasm(qasm, intent,
                                  shots=config.llm.verification_shots)
            attempts.append((qasm, verdict))
            if verdict.ok:
                return Draft(qasm, origin, verdict)
            return None

        current = intent.source_qasm or ""
        produced = None
        verdict = Verdict(False, "no parseable program in request")
        if current:
            verdict = verify_qasm(current, intent,
                                  shots=config.llm.verification_shots)
            if verdict.ok:
                produced = Draft(current, "as-given", verdict)
        rounds_left = config.llm.repair_rounds + 1
        while produced is None and transport is not None and rounds_left > 0:
            if deadline is not None and time.monotonic() > deadline:
                break
            rounds_left -= 1
            try:
                fixed_reply = _call_llm(
                    transport, _system_prompt_repair(),
                    _repair_user_message(
                        "User request (contains the broken program):\n%s"
                        % (intent.raw_prompt or current),
                        current, verdict.reason))
                candidate = extract_qasm_text(fixed_reply) or \
                    extract_bare_snippet(fixed_reply)
                if candidate:
                    produced = consider(_ensure_header(candidate), "llm-repair")
                    if produced is None:
                        current = candidate
                        verdict = attempts[-1][1]
            except Exception:
                break
        if produced is None:
            template = synthesize(replace(intent, source_qasm=None))
            if template is not None:
                tverdict = verify_qasm(template, intent,
                                       shots=config.llm.verification_shots)
                if tverdict.ok:
                    produced = Draft(template, "intent-template", tverdict)
        if produced is None:
            raise AgentError("repair failed: %s"
                             % (attempts[-1][1].reason if attempts else "unknown"))
        return produced
    return run


def _last_failure(attempts):
    for qasm, verdict in reversed(attempts):
        if not verdict.ok:
            return qasm, verdict.reason
    return None, ""


def _reconstruct_request(intent: Intent) -> str:
    names = {"ghz": "GHZ (maximally entangled)", "bell": "Bell pair",
             "w": "W state", "uniform": "uniform superposition"}
    if intent.family:
        head = "Prepare a %s state" % names.get(intent.family, intent.family)
    else:
        head = "Prepare the requested quantum state"
    parts = [head]
    if intent.n_qubits:
        parts.append("on %d qubits" % intent.n_qubits)
    return ", ".join(parts) + ", with full measurement, in OpenQASM 2.0."


# ==========================================================================
# backend selection (deterministic solver over the live capability table)
# ==========================================================================

_QUEUE_RANK = {"none": 0, "minutes": 1, "minutes_to_hours": 2, "hours": 3}
_COST_RANK = {"free": 0, "free_quota": 1, "paid": 2}


def solve_backend(intent: Intent, table: list[dict]) -> dict:
    n = intent.n_qubits or 1
    tags = intent.constraints
    scored = []
    for row in table:
        if row.get("max_qubits", 0) < n:
            continue
        if "zero_queue" in tags and row.get("queue") != "none":
            continue
        if "simulator" in tags and row.get("kind") != "simulator":
            continue
        if "real_device" in tags and row.get("kind") != "qpu":
            continue
        if "no_account" in tags and row.get("requires_account"):
            continue
        if "free" in tags and row.get("cost") not in ("free", "free_quota"):
            continue
        score = (_QUEUE_RANK.get(row.get("queue"), 9),
                 _COST_RANK.get(row.get("cost"), 9),
                 -row.get("max_qubits", 0))
        scored.append((score, row))
    scored.sort(key=lambda item: item[0])
    return {
        "n": n,
        "candidates": [row["id"] for _score, row in scored],
        "rows": [row for _score, row in scored],
    }


def select_pipeline(transport: Callable, config: LoomqConfig,
                    capability_table: Callable[[], list[dict]]) -> Callable[[Intent], str]:
    def run(intent: Intent) -> str:
        solution = solve_backend(intent, capability_table())
        rows = solution["rows"]
        best = solution["candidates"][0] if solution["candidates"] else \
            "braket_local_simulator"
        reasoning = ""
        if transport is not None:
            try:
                reply = _call_llm(
                    transport,
                    "You explain quantum backend choices to non-experts in "
                    "concise Chinese, based strictly on the provided "
                    "capability table. One short paragraph.",
                    "User asks: %s\nCapability table (JSON):\n%s\nThe "
                    "recommended backend id is %s. Explain why in <=80 words, "
                    "mention qubit capacity, queueing and cost."
                    % (intent.raw_prompt, _compact_table(rows), best))
                reasoning = reply.strip()
            except Exception:
                reasoning = ""
        if not reasoning:
            if rows:
                row = rows[0]
                reasoning = ("%s：容量 %d 比特，排队情况 %s，费用 %s，无需排队即可本地运行。"
                             % (row.get("notes") or row["id"], row.get("max_qubits", 0),
                                row.get("queue"), row.get("cost")))
            else:
                reasoning = "没有完全匹配的后端；请放宽约束（如允许排队或账号）。"
        lines = ["推荐后端：%s" % best]
        others = [cid for cid in solution["candidates"] if cid != best]
        if others:
            lines.append("同样满足条件的候选：%s" % ", ".join(others))
        lines.append(reasoning)
        return "\n".join(lines)
    return run


def _compact_table(rows: list[dict]) -> str:
    slim = [{k: row.get(k) for k in
             ("id", "kind", "max_qubits", "queue", "cost", "requires_account")}
            for row in rows[:8]]
    import json
    return json.dumps(slim, ensure_ascii=False)


# ==========================================================================
# public entry point
# ==========================================================================

def agent_chat(prompt: str, transport: Optional[Callable] = None,
               config: Optional[LoomqConfig] = None,
               capability_table: Optional[Callable[[], list[dict]]] = None) -> str:
    """Contract entry point. All dependencies optional & injectable."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    if config is None or capability_table is None or transport is None:
        resolved = _resolve_defaults(config, capability_table, transport)
        config, capability_table, transport = resolved

    deadline = time.monotonic() + float(getattr(config.llm, "timeout_seconds", 120)) \
        if transport is not None else None
    intent = extract_intent(prompt)
    intent = replace(intent, raw_prompt=prompt)

    if intent.task == "select":
        return select_pipeline(transport, config, capability_table)(intent)

    pipeline = generate_pipeline if intent.task == "generate" else fix_pipeline
    try:
        draft = pipeline(transport, config, deadline)(intent)
    except AgentError as exc:
        return (
            "暂时无法为这个请求生成经过验证的程序（%s）。\n"
            "建议：\n"
            "  · 明确状态类型，如“生成 N 比特 GHZ / 贝尔 / W / 均匀叠加态并测量”；\n"
            "  · 修复请求请附带需要修复的 QASM 代码；\n"
            "  · 配置 LOOMQ_LLM_BASE_URL / API_KEY / MODEL 后可解锁更复杂的请求。"
            % exc)
    return _format_answer(intent, draft)


def _resolve_defaults(config, capability_table, transport):
    try:
        from .di import bootstrap
        from .plugin_loader import load_plugins
    except ImportError:
        from di import bootstrap
        from plugin_loader import load_plugins
    cfg = config or LoomqConfig.load()
    registry = load_plugins(cfg)
    table_fn = capability_table or registry.capability_table
    if transport is None and cfg.llm.configured:
        def transport(messages, **extra):
            try:
                from .llm_client import chat_completion
            except ImportError:
                from llm_client import chat_completion
            return chat_completion(messages, **extra)
    return cfg, table_fn, transport


def _mini_histogram(counts: Mapping[str, int], width: int = 24,
                    top: int = 6) -> str:
    """ASCII distribution preview so the answer shows the verified run."""
    total = sum(counts.values())
    if total <= 0:
        return ""
    best = sorted(counts.items(), key=lambda kv: -kv[1])[:top]
    lines = ["  测量结果分布（%d shots）：" % total]
    for key, hits in best:
        bar = "█" * max(1, round(width * hits / total))
        lines.append("  %s  %5.1f%%  %s" % (key.ljust(6), 100.0 * hits / total, bar))
    return "\n".join(lines)


def _format_answer(intent: Intent, draft: Draft) -> str:
    label = {"generate": "生成", "fix": "修复"}.get(intent.task, "处理")
    head = "已%s %s 电路（来源：%s，自验：%s）" % (
        label,
        "%d 比特" % intent.n_qubits if intent.n_qubits else "",
        draft.origin,
        draft.verdict.reason or "ok")
    body = "%s\n\n```qasm\n%s```\n" % (head.strip(), draft.qasm)
    chart = _mini_histogram(draft.verdict.observed_counts or {})
    if chart and draft.verdict.ok:
        body += "\n" + chart + "\n"
    return body
