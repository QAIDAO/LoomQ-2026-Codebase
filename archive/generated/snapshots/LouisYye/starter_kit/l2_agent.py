"""Budgeted, locally verified LoomQ L2 agent."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from .l2.backends import select as select_backend
    from .l2.budget import Budget
    from .l2.normalize import normalize
    from .l2.reference import reference_distribution
    from .l2.render import backend as render_backend
    from .l2.render import fallback, qasm as render_qasm
    from .l2.schema import AgentResult, parse_structured, parse_target
    from .l2.simulate import simulate
    from .l2.synthesize import synthesize
    from .l2.verify import fidelity
    from .llm_client import chat_completion
except ImportError:
    from l2.backends import select as select_backend
    from l2.budget import Budget
    from l2.normalize import normalize
    from l2.reference import reference_distribution
    from l2.render import backend as render_backend
    from l2.render import fallback, qasm as render_qasm
    from l2.schema import AgentResult, parse_structured, parse_target
    from l2.simulate import simulate
    from l2.synthesize import synthesize
    from l2.verify import fidelity
    from llm_client import chat_completion


MAX_ATTEMPTS = 3
VERIFY_THRESHOLD = 0.99
UNVERIFIED_SCORE = -1.0
QASM_START = re.compile(r"OPENQASM\s+2\.0\s*;", re.IGNORECASE)
CHOICE = re.compile(r'"choice"\s*:\s*"?([AB])"?', re.IGNORECASE)


def _load_backend_capabilities() -> dict[str, Any]:
    path = Path(__file__).with_name("backend_capabilities.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _system_prompt() -> str:
    capabilities = json.dumps(
        _load_backend_capabilities(), ensure_ascii=False, separators=(",", ":")
    )
    return f"""You are LoomQ Agent. Understand the user's intent and return JSON only.
Do not wrap JSON in Markdown. Use this exact shape:
{{
  "task": "generate" | "repair" | "backend",
  "qasm": "complete OpenQASM 2.0 string or null",
  "target": {{"kind": "ghz|bell|w|plus|uniform|basis|custom", "n": integer,
    "state": "optional basis bit string", "measure_all": boolean,
    "expected_distribution": {{"bitstring": probability}}}},
  "constraints": {{"min_qubits": integer, "queue": "none|null",
    "cost": "free|null", "no_account": boolean,
    "requires_hardware": boolean, "local_only": boolean}},
  "backend_hint": "your own best backend id, or null",
  "explanation": "short plain-language Chinese explanation"
}}

For generate/repair, qasm must be complete OpenQASM 2.0 with qelib1.inc,
register declarations, the requested circuit, and requested measurements. Put the
program directly in the JSON string with no Markdown fences. Preserve the explicit
target intent when repairing. Prefer these gates: h,x,s,sdg,t,tdg,ry,rz,cx,cu1,
swap,ccx. Declare the target accurately so local simulation can verify semantics.
"n" is the number of qubits in the target state. Bit strings are ordered
c[n-1]...c[0]: the RIGHTMOST character is c[0] (measured from q[0]) and the
LEFTMOST character is c[n-1] (measured from q[n-1]). Worked example with n=3:
if q[1] is |1> while q[0] and q[2] are in equal superposition, then
expected_distribution is {{"010":0.25,"011":0.25,"110":0.25,"111":0.25}} --- the
fixed qubit q[1] is the MIDDLE character. Never place q[0] first. Translate any
per-qubit description into this ordering before writing a single key.
If kind is "custom" you MUST supply a normalized
expected_distribution, otherwise the answer cannot be verified.

For backend tasks, qasm is null. Extract every explicit constraint faithfully and
leave unstated constraints null/false; the final choice is made locally from the
official table below, so backend_hint is only a cross-check.
Official capability snapshot:
{capabilities}
"""


def _target_prompt(original_prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": """Independently extract only the quantum measurement target from the user's original request. Do not design, inspect, or output a circuit. Return JSON only: {"target":{"kind":"ghz|bell|w|plus|uniform|basis|custom","n":2,"state":"optional bit string","measure_all":true,"expected_distribution":{"bitstring":0.5}}}. Always include a normalized expected_distribution using c[n-1]...c[0] ordering: the RIGHTMOST character is c[0] (measured from q[0]) and the LEFTMOST is c[n-1] (measured from q[n-1]). Worked example with n=3: "q[0] is |1> while q[1] and q[2] are in equal superposition" gives {"001":0.25,"011":0.25,"101":0.25,"111":0.25} --- the fixed 1 is the RIGHTMOST character, not the first. Never place q[0] first. Translate every per-qubit description into this ordering before writing a single key. For custom correlations, follow the user's described outcomes literally."""},
        {"role": "user", "content": original_prompt},
    ]


def _distribution(target: dict[str, Any]) -> dict[str, float] | None:
    return reference_distribution(target)


def _targets_agree(left: dict[str, Any], right: dict[str, Any]) -> bool:
    a, b = _distribution(left), _distribution(right)
    if a is None or b is None:
        return left == right
    return fidelity(a, b) >= 0.999999


def _mirrored(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """True when two candidates are the same outcomes read in opposite bit order.

    Every model we have tried is reliable about *which* qubits are constrained and
    unreliable about which end of the string they belong to, so this disagreement
    is an encoding conflict rather than a semantic one and deserves its own,
    much narrower question.
    """
    a, b = _distribution(left), _distribution(right)
    if not a or not b or len(a) != len(b):
        return False
    flipped: dict[str, float] = {}
    for state, probability in a.items():
        flipped[state[::-1]] = flipped.get(state[::-1], 0.0) + probability
    if set(flipped) == set(a):
        # Reversal changes nothing, so ordering cannot be what they disagree about.
        return False
    return fidelity(flipped, b) >= 0.999999


def _ordering_choice(
    completion, prompt: str, generated: dict[str, Any], independent: dict[str, Any], budget: Budget
) -> dict[str, Any] | None:
    """Ask which end of the bit string the constrained qubits belong to.

    Deliberately a binary pick rather than "write the distribution again": models
    that get the ordering wrong get it wrong the same way on a rewrite, but they
    answer the comparison correctly once the convention is spelled out.
    """
    left, right = _distribution(generated), _distribution(independent)
    messages = [
        {"role": "system", "content": (
            "Two candidate outcome lists describe the same measurement read in "
            "opposite bit orders. LoomQ orders every bit string c[n-1]...c[0]: the "
            "RIGHTMOST character is c[0], measured from q[0]; the LEFTMOST character "
            "is c[n-1], measured from q[n-1]. Example with n=3: if only q[0] is |1>, "
            'the outcome is "001", never "100". Under that ordering, decide which '
            "candidate matches the user's request. Do not produce a circuit and do "
            'not write a new distribution. Answer JSON only: {"choice":"A"} or '
            '{"choice":"B"}.'
        )},
        {"role": "user", "content": json.dumps(
            {"original_request": prompt, "candidate_A": left, "candidate_B": right},
            ensure_ascii=False,
        )},
    ]
    try:
        raw = _message_content(_call(completion, messages, budget.timeout_for_call()))
    except Exception:
        return None
    match = CHOICE.search(raw)
    if not match:
        return None
    return generated if match.group(1).upper() == "A" else independent


def _extract_independent_target(completion, prompt: str, budget: Budget) -> dict[str, Any]:
    try:
        raw = _message_content(_call(completion, _target_prompt(prompt), budget.timeout_for_call()))
        return parse_target(raw) or {}
    except Exception:
        return {}


def _adjudicate_target(
    completion, prompt: str, generated: dict[str, Any], independent: dict[str, Any], budget: Budget
) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": "Compare two candidate measurement targets against the user's original words. Do not inspect or produce a circuit. Return JSON only as {\"target\": {...}} with a normalized expected_distribution."},
        {"role": "user", "content": json.dumps({"original_request": prompt, "candidate_from_generation": generated, "candidate_from_independent_extraction": independent}, ensure_ascii=False)},
    ]
    try:
        raw = _message_content(_call(completion, messages, budget.timeout_for_call()))
        decided = parse_target(raw) or {}
        if decided and (_targets_agree(decided, generated) or _targets_agree(decided, independent)):
            return decided
    except Exception:
        pass
    return {}


def _resolve_target(
    completion, prompt: str, generated: dict[str, Any], budget: Budget
) -> dict[str, Any]:
    independent = _extract_independent_target(completion, prompt, budget)
    if not independent or not generated:
        confirmed = generated or independent
    elif _targets_agree(generated, independent):
        confirmed = generated
    elif _mirrored(generated, independent):
        # Same outcomes, opposite bit order: one pointed question beats a rewrite.
        picked = _ordering_choice(completion, prompt, generated, independent, budget)
        confirmed = picked if picked is not None else generated
    else:
        decided = _adjudicate_target(completion, prompt, generated, independent, budget)
        if decided and _targets_agree(decided, generated):
            confirmed = generated
        elif decided and _targets_agree(decided, independent):
            confirmed = independent
        else:
            confirmed = generated
    if os.environ.get("LOOMQ_L2_DEBUG"):
        print("[l2] generated=" + json.dumps(generated, ensure_ascii=False), file=sys.stderr)
        print("[l2] independent=" + json.dumps(independent, ensure_ascii=False), file=sys.stderr)
        print("[l2] confirmed=" + json.dumps(confirmed, ensure_ascii=False), file=sys.stderr)
    return confirmed


def _message_content(response: dict[str, Any]) -> str:
    content = response["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("model returned empty content")
    return content.strip()


def extract_qasm(text: str) -> str | None:
    match = QASM_START.search(text)
    if not match:
        return None
    tail = text[match.start() :]
    fence = re.search(r"^\s*```", tail, re.MULTILINE)
    return (tail[: fence.start()] if fence else tail).strip()


def _legacy_result(text: str) -> AgentResult | None:
    qasm = extract_qasm(text)
    if qasm:
        return AgentResult(task="generate", qasm=qasm, explanation="已生成量子电路。")
    return None


def _call(completion, messages, timeout):
    try:
        return completion(messages, timeout=timeout)
    except TypeError:
        if completion is chat_completion:
            raise
        return completion(messages)


def _target_qubits(target: dict) -> int | None:
    try:
        value = int(target.get("n"))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _structural_error(result: AgentResult, circuit) -> str | None:
    """Cheap checks that catch the most common malformed circuits."""
    expected_n = _target_qubits(result.target)
    if expected_n and circuit.num_qubits != expected_n:
        return (
            f"Circuit declares {circuit.num_qubits} qubits but the target needs "
            f"{expected_n}."
        )
    if result.target.get("measure_all") is True:
        measured = {measurement.qubit for measurement in circuit.measurements}
        if len(measured) != circuit.num_qubits:
            return (
                f"Target requires measuring all {circuit.num_qubits} qubits but only "
                f"{len(measured)} are measured."
            )
    return None


def _handle_backend(result: AgentResult, cross_check: bool):
    selected = select_backend(result.constraints)
    hint = result.backend_hint
    if (
        cross_check
        and isinstance(hint, str)
        and hint
        and hint != selected["id"]
    ):
        # A disagreement usually means a constraint was mis-extracted, not that
        # the table is wrong. Ask once, then keep the local decision regardless.
        return (
            False,
            render_backend(result.explanation, selected),
            UNVERIFIED_SCORE,
            (
                f"Your backend_hint was {hint} but the official table selects "
                f"{selected['id']} for the constraints you extracted "
                f"({json.dumps(result.constraints, ensure_ascii=False)}). "
                "Re-extract the constraints from my original request."
            ),
        )
    return True, render_backend(result.explanation, selected), 1.0, ""


def _handle(result: AgentResult, allow_retry: bool, first_attempt: bool):
    """Return (ok, rendered answer or None, score, error)."""
    if result.task == "backend":
        # Cross-check the model's own pick once; never spend a second retry on it.
        return _handle_backend(result, allow_retry and first_attempt)

    if not result.qasm:
        return False, None, UNVERIFIED_SCORE, "No complete QASM was supplied."

    try:
        program, circuit = normalize(result.qasm)
    except Exception as exc:
        return False, None, UNVERIFIED_SCORE, f"{type(exc).__name__}: {exc}"

    structural = _structural_error(result, circuit)
    if structural:
        return False, None, UNVERIFIED_SCORE, structural

    expected = reference_distribution(result.target)
    if expected is None:
        rendered = render_qasm(result.explanation, program)
        if allow_retry:
            # Never let an undeclared target silently skip semantic validation.
            return False, rendered, UNVERIFIED_SCORE, (
                "The target state was not declared in a verifiable way. Resend the "
                "same JSON with target.kind set, or with a normalized "
                "target.expected_distribution over c[n-1]...c[0] bit strings."
            )
        return True, rendered, UNVERIFIED_SCORE, ""

    observed = simulate(circuit)
    score = fidelity(observed, expected)
    if score >= VERIFY_THRESHOLD:
        return True, render_qasm(result.explanation, program, score), score, ""
    return (
        False,
        render_qasm(result.explanation, program, score, verified=False),
        score,
        (
            f"Local simulation fidelity was {score:.6f}, below {VERIFY_THRESHOLD}. "
            f"Observed={observed}; expected={expected}."
        ),
    )


def _synthesized_answer(target: dict) -> str | None:
    built = synthesize(target)
    if built is None:
        return None
    program, score = built
    return render_qasm(
        "以下电路依据你声明的目标态在本地重建。",
        program,
        score,
        synthesized=True,
    )


def agent_chat(
    prompt: str,
    *,
    completion: Callable[..., dict[str, Any]] = chat_completion,
) -> str:
    """Call the model at least once, then validate and deterministically render its work."""
    if not isinstance(prompt, str) or not prompt.strip():
        return fallback("请求不能为空")

    budget = Budget()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": prompt.strip()},
    ]
    best_answer: str | None = None
    best_score = float("-inf")
    last_target: dict[str, Any] = {}
    confirmed_target: dict[str, Any] = {}
    last_error = "模型没有返回可用结果"

    for attempt in range(MAX_ATTEMPTS):
        is_last = attempt + 1 >= MAX_ATTEMPTS or not budget.can_retry()
        try:
            raw = _message_content(_call(completion, messages, budget.timeout_for_call()))
            structured = parse_structured(raw) or _legacy_result(raw)
            if structured is None:
                last_error = "Response was not valid structured JSON and contained no QASM."
            else:
                if structured.task != "backend" and not confirmed_target:
                    confirmed_target = _resolve_target(
                        completion, prompt.strip(), structured.target, budget
                    )
                if structured.task != "backend" and confirmed_target:
                    structured.target = confirmed_target
                if structured.target:
                    last_target = structured.target
                ok, candidate, score, error = _handle(
                    structured, allow_retry=not is_last, first_attempt=attempt == 0
                )
                if candidate and score > best_score:
                    best_answer, best_score = candidate, score
                if ok:
                    return candidate
                last_error = error
            messages.extend([
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                        "The circuit and declared target disagree with local validation; either "
                        "the circuit or the target may be wrong. Compare both against my original "
                        f"request and correct the wrong one. Details: {last_error} Return corrected "
                        "JSON only and preserve the original intent."
                )},
            ])
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if is_last:
            break

    # A verified local reconstruction beats an unverified or failing model answer.
    if best_score < VERIFY_THRESHOLD:
        rebuilt = _synthesized_answer(last_target)
        if rebuilt is not None:
            return rebuilt

    return best_answer or fallback(last_error)
