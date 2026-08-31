#!/usr/bin/env python3
"""Minimal L2 agent layer built on top of the stable L1 adapter.

Formal L2 cases must perform at least one successful LLM service call. This
module therefore treats the first model call as natural-language understanding:
the LLM extracts intent, optional constraints, and optional QASM. Deterministic
Python logic still makes the final decisions for known tasks and backend
selection, and L1 remains the source of QASM validation.

Without LOOMQ_LLM_* configuration, keep L2 disabled in ``submission.yaml``. The
module still exposes a no-key deterministic path for local development, while
tests inject a mock LLM callable to verify the formal call contract.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

try:
    from . import adapter
    from .llm_client import chat_completion
except ImportError:
    import adapter
    from llm_client import chat_completion


LOCAL_VALIDATION_SHOTS = 512
SEMANTIC_FIDELITY_THRESHOLD = 0.97
MAX_TOTAL_LLM_CALLS = 2

LLMCallable = Callable[[list[dict[str, Any]]], dict[str, Any]]


@dataclass
class ValidationResult:
    ok: bool
    message: str
    counts: Optional[Dict[str, int]] = None


@dataclass
class KnownTask:
    task_id: str
    generator: Callable[[dict[str, Any]], str]
    validator: Callable[[str, dict[str, Any]], ValidationResult]


def agent_chat_impl(
    prompt: str,
    llm_callable: Optional[LLMCallable] = None,
    require_llm: Optional[bool] = None,
) -> str:
    """Return an L2 response for backend choice, QASM generation, or QASM repair.

    In formal mode, ``require_llm`` is true whenever LOOMQ_LLM_* is configured.
    The deterministic fallback is only for local development while L2 remains
    disabled. A failed LLM service call is not counted as satisfying the formal
    service-call requirement.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    chat_fn = llm_callable or chat_completion
    formal_llm_required = _llm_configured() if require_llm is None else require_llm
    if llm_callable is not None:
        formal_llm_required = True if require_llm is None else require_llm

    if not formal_llm_required:
        return _agent_chat_without_llm(prompt)

    first_content = _call_llm_for_task_understanding(prompt, chat_fn)
    llm_task = _parse_llm_task(first_content)
    intent = _merge_intent(prompt, llm_task)

    if intent.get("type") == "backend_selection":
        backends = select_backends(intent.get("constraints", {}))
        return _format_backend_answer(backends, intent.get("constraints", {}), llm_used=True)

    task = _known_task(intent)
    if task is not None:
        qasm = task.generator(intent)
        validation = _validate_qasm_locally(qasm)
        semantic = task.validator(qasm, intent) if validation.ok else validation
        if validation.ok and semantic.ok:
            return _format_qasm_answer(qasm, semantic, source="LLM intent + deterministic known-task handler")
        feedback = "Known-task deterministic generation failed validation: " + semantic.message
    else:
        qasm = _extract_qasm_from_task_or_text(llm_task, first_content)
        feedback = None
        if qasm:
            validation = _validate_qasm_locally(qasm)
            if validation.ok:
                return _format_qasm_answer(qasm, validation, source="LLM QASM + L1 local validation")
            feedback = "Syntax/execution validation failed: " + validation.message
        else:
            feedback = "First LLM response did not contain usable QASM for this generic task."

    # One extra call at most: repair or generate after validation/format failure.
    repaired_qasm = _call_llm_for_qasm_repair(prompt, intent, feedback, chat_fn)
    validation = _validate_qasm_locally(repaired_qasm)
    if not validation.ok:
        return "Unable to produce valid QASM after LLM repair. Last error: %s\n" % validation.message
    if task is not None:
        semantic = task.validator(repaired_qasm, intent)
        if not semantic.ok:
            return "Unable to satisfy task semantics after LLM repair. Last error: %s\n" % semantic.message
        return _format_qasm_answer(repaired_qasm, semantic, source="LLM repair + semantic validator")
    return _format_qasm_answer(repaired_qasm, validation, source="LLM repair + L1 local validation")


def _agent_chat_without_llm(prompt: str) -> str:
    """Local development path only. Do not enable L2 until LLM env is configured."""
    intent = _deterministic_intent(prompt)
    if intent.get("type") == "backend_selection":
        backends = select_backends(intent.get("constraints", {}))
        return _format_backend_answer(backends, intent.get("constraints", {}), llm_used=False)

    task = _known_task(intent)
    if task is not None:
        qasm = task.generator(intent)
        validation = _validate_qasm_locally(qasm)
        semantic = task.validator(qasm, intent) if validation.ok else validation
        if validation.ok and semantic.ok:
            return _format_qasm_answer(qasm, semantic, source="local deterministic development path")

    return (
        "L2 deterministic layer could not fully handle this prompt without an LLM. "
        "Configure LOOMQ_LLM_BASE_URL, LOOMQ_LLM_API_KEY, and LOOMQ_LLM_MODEL "
        "before enabling L2.\n"
    )


def _llm_configured() -> bool:
    return all(os.environ.get(name) for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL"))


def _call_llm_for_task_understanding(prompt: str, chat_fn: LLMCallable) -> str:
    messages = [
        {"role": "system", "content": _intent_system_prompt()},
        {"role": "user", "content": prompt},
    ]
    return _llm_content(chat_fn(messages))


def _call_llm_for_qasm_repair(prompt: str, intent: dict[str, Any], feedback: str, chat_fn: LLMCallable) -> str:
    messages = [
        {"role": "system", "content": _qasm_system_prompt()},
        {"role": "user", "content": prompt},
        {"role": "user", "content": "Previous attempt failed validation. Fix it. Error: " + feedback},
    ]
    return _extract_qasm(_llm_content(chat_fn(messages)))


def _intent_system_prompt() -> str:
    return (
        "You are LoomQ Agent's intent extractor. Return compact JSON if possible, "
        "but include OpenQASM 2.0 if the task is generic generation or repair. "
        "JSON schema: {\"task_type\":\"generate|repair|backend_selection\", "
        "\"known_task\":\"bell|ghz|null\", \"num_qubits\":null, "
        "\"constraints\":{\"min_qubits\":null,\"queue\":null,\"free_only\":null,"
        "\"local_only\":null,\"real_hardware\":null,\"no_account\":null}, "
        "\"qasm\":null}. The LLM must not choose backend IDs; Python will filter "
        "backend_capabilities.json. For QASM, obey this L1 subset: one qreg, one "
        "creg, final measurement, only gates h, x, s, sdg, t, tdg, rz, ry, cx, "
        "cu1, swap, ccx; no custom gate, reset, if, opaque, barrier, multiple "
        "qreg/creg declarations, or other gates."
    )


def _qasm_system_prompt() -> str:
    return (
        "You are LoomQ Agent. Return a complete OpenQASM 2.0 program only. "
        "The current L1 parser supports exactly one qreg, exactly one creg, final "
        "measurement, and only these gates: h, x, s, sdg, t, tdg, rz, ry, cx, "
        "cu1, swap, ccx. Do not use custom gate definitions, reset, if, opaque, "
        "barrier, multiple qreg/creg declarations, or gates outside the whitelist. "
        "Always include OPENQASM 2.0;, include \"qelib1.inc\";, qreg, creg, and measure."
    )


def _parse_llm_task(text: str) -> dict[str, Any]:
    try:
        data = json.loads(_extract_json_object(text))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    normalized: dict[str, Any] = {}
    task_type = data.get("task_type") or data.get("type")
    if task_type == "generate":
        task_type = "qasm_generation"
    elif task_type == "repair":
        task_type = "qasm_repair"
    if task_type:
        normalized["type"] = task_type

    known_task = data.get("known_task") or data.get("task_id")
    if isinstance(known_task, str) and known_task.lower() not in {"null", "none", ""}:
        normalized["task_id"] = known_task.lower()

    if data.get("num_qubits") not in (None, "", "null"):
        try:
            normalized["num_qubits"] = int(data["num_qubits"])
        except (TypeError, ValueError):
            pass

    constraints = data.get("constraints")
    if isinstance(constraints, dict):
        normalized["constraints"] = {k: v for k, v in constraints.items() if v not in (None, "", "null")}

    qasm = data.get("qasm")
    if isinstance(qasm, str) and "OPENQASM" in qasm:
        normalized["qasm"] = qasm
    return normalized


def _merge_intent(prompt: str, llm_intent: dict[str, Any]) -> dict[str, Any]:
    text = prompt.lower()
    deterministic_facts = _deterministic_facts(text)
    llm_intent = _filter_llm_known_task_by_prompt(text, llm_intent)
    intent = _deterministic_intent(prompt)
    for key, value in llm_intent.items():
        if value not in (None, "", [], {}):
            if key == "constraints":
                merged = dict(intent.get("constraints", {}))
                merged.update(_filter_llm_backend_constraints(text, value, deterministic_facts.get("constraints", {})))
                merged.update(deterministic_facts.get("constraints", {}))
                intent["constraints"] = merged
            elif key in deterministic_facts:
                continue
            else:
                intent[key] = value
    for key, value in deterministic_facts.items():
        if key == "constraints":
            if value:
                merged = dict(intent.get("constraints", {}))
                merged.update(value)
                intent["constraints"] = merged
        else:
            intent[key] = value
    return intent


def _deterministic_intent(prompt: str) -> dict[str, Any]:
    text = prompt.lower()
    constraints = _extract_backend_constraints(text)
    if _looks_like_backend_selection(text):
        return {"type": "backend_selection", "constraints": constraints}

    if _looks_like_ghz(text):
        intent: dict[str, Any] = {"type": "qasm_generation", "task_id": "ghz"}
        ghz_n = _extract_ghz_size(text)
        if ghz_n is not None:
            intent["num_qubits"] = ghz_n
        return intent
    if _looks_like_bell(text):
        return {"type": "qasm_generation", "task_id": "bell", "num_qubits": 2}
    return {"type": "qasm_repair" if _contains_qasm_fragment(prompt) else "qasm_generation", "constraints": constraints}


def _deterministic_facts(text: str) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    constraints = _extract_backend_constraints(text)
    if constraints:
        facts["constraints"] = constraints
    if _looks_like_explicit_backend_selection(text):
        facts["type"] = "backend_selection"
    if _looks_like_bell(text):
        facts.update({"type": "qasm_generation", "task_id": "bell", "num_qubits": 2})
        return facts
    if _looks_like_ghz(text):
        facts.update({"type": "qasm_generation", "task_id": "ghz"})
        ghz_n = _extract_ghz_size(text)
        if ghz_n is not None:
            facts["num_qubits"] = ghz_n
    return facts


def _filter_llm_known_task_by_prompt(text: str, llm_intent: dict[str, Any]) -> dict[str, Any]:
    task_id = llm_intent.get("task_id")
    if task_id not in {"bell", "ghz"}:
        return llm_intent

    explicit_n = _extract_explicit_qubit_count(text)
    if task_id == "bell" and explicit_n is not None and explicit_n != 2 and not _looks_like_bell(text):
        filtered = dict(llm_intent)
        filtered.pop("task_id", None)
        filtered.pop("num_qubits", None)
        return filtered
    if task_id == "ghz" and explicit_n is not None and explicit_n < 2 and not _looks_like_ghz(text):
        filtered = dict(llm_intent)
        filtered.pop("task_id", None)
        filtered.pop("num_qubits", None)
        return filtered
    return llm_intent


def _filter_llm_backend_constraints(
    text: str,
    constraints: dict[str, Any],
    deterministic_constraints: dict[str, Any],
) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    for key, value in constraints.items():
        if key in deterministic_constraints:
            filtered[key] = value
        elif key == "min_qubits":
            filtered[key] = value
        elif key == "queue" and value == "none" and _has_queue_none_evidence(text):
            filtered[key] = value
        elif key == "free_only" and value is True and _has_free_evidence(text):
            filtered[key] = value
        elif key == "local_only" and value is True and _has_local_evidence(text):
            filtered[key] = value
        elif key == "real_hardware" and value is True and _has_real_hardware_evidence(text):
            filtered[key] = value
        elif key == "no_account" and value is True and _has_no_account_evidence(text):
            filtered[key] = value
        elif value is False:
            filtered[key] = value
    return filtered


def _looks_like_backend_selection(text: str) -> bool:
    return bool(
        re.search(r"\bbackend\b|\bplatform\b|\bsimulator\b|\bqpu\b|\bhardware\b|\blocal\b|\bqueue\b", text)
        or any(token in text for token in ("后端", "平台", "模拟器", "真机", "排队", "免费", "本地"))
    )


def _looks_like_explicit_backend_selection(text: str) -> bool:
    english_target = r"(?:backend|platform|simulator|qpu|hardware)"
    english_choice = (
        rf"\bwhich\s+{english_target}\b|"
        rf"\bwhat\s+{english_target}\b|"
        rf"\b{english_target}\s+should\s+i\s+use\b|"
        rf"\bshould\s+i\s+use\b.*\b{english_target}\b|"
        rf"\b(?:choose|select|pick|recommend)\b.*\b{english_target}\b|"
        rf"\b{english_target}\b.*\b(?:choose|select|pick|recommend)\b|"
        rf"\bbest\s+{english_target}\b"
    )
    chinese_choice = (
        r"哪个(?:后端|平台|模拟器|真机)|"
        r"(?:后端|平台|模拟器|真机).*(?:选哪个|选择哪个|用哪个|推荐|选择)|"
        r"(?:选哪个|选择哪个|用哪个|应该选|应该用|推荐|选择).*(?:后端|平台|模拟器|真机)"
    )
    return bool(re.search(english_choice, text) or re.search(chinese_choice, text))


def _extract_backend_constraints(text: str) -> dict[str, Any]:
    constraints: dict[str, Any] = {}
    explicit_qubits = _extract_explicit_qubit_count(text)
    if explicit_qubits is not None:
        constraints["min_qubits"] = explicit_qubits
    if _has_queue_none_evidence(text):
        constraints["queue"] = "none"
    if _has_free_evidence(text):
        constraints["free_only"] = True
    if _has_local_evidence(text):
        constraints["local_only"] = True
    if _has_real_hardware_evidence(text):
        constraints["real_hardware"] = True
    if _has_no_account_evidence(text):
        constraints["no_account"] = True
    return constraints


def _extract_explicit_qubit_count(text: str) -> Optional[int]:
    units = r"(?:qubit|qubits|比特|量子位|量子比特)"
    digit_match = re.search(rf"(\d+)\s*(?:-|个| )?\s*{units}", text, re.IGNORECASE)
    if digit_match:
        return int(digit_match.group(1))

    english_numbers = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
    }
    english_pattern = r"\b(" + "|".join(english_numbers) + rf")\s*(?:-| )?\s*{units}"
    english_match = re.search(english_pattern, text, re.IGNORECASE)
    if english_match:
        return english_numbers[english_match.group(1).lower()]

    chinese_match = re.search(r"([一二两三四五六七八九十]{1,3})\s*(?:个)?\s*(?:比特|量子位|量子比特)", text)
    if chinese_match:
        return _parse_small_chinese_int(chinese_match.group(1))
    return None


def _parse_small_chinese_int(text: str) -> Optional[int]:
    digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if text in digits:
        return digits[text]
    if text == "十":
        return 10
    if "十" not in text:
        return None
    left, right = text.split("十", 1)
    tens = digits.get(left, 1) if left else 1
    ones = digits.get(right, 0) if right else 0
    value = tens * 10 + ones
    return value if 1 <= value <= 99 else None


def _has_queue_none_evidence(text: str) -> bool:
    return any(token in text for token in ("zero queue", "no queue", "without queue", "no waiting", "无排队", "零排队", "不排队"))


def _has_free_evidence(text: str) -> bool:
    return any(token in text for token in ("free", "no cost", "no fee", "without paying", "免费", "不花钱", "不想付费"))


def _has_local_evidence(text: str) -> bool:
    return any(token in text for token in ("local", "local simulator", "本地", "本地模拟器"))


def _has_real_hardware_evidence(text: str) -> bool:
    return any(
        token in text
        for token in (
            "real hardware",
            "real quantum hardware",
            "physical qpu",
            "real quantum computer",
            "真机",
            "真实硬件",
            "真实量子硬件",
            "真实量子计算机",
        )
    )


def _has_no_account_evidence(text: str) -> bool:
    return any(token in text for token in ("no account", "without registration", "no registration", "no signup", "无需账号", "不需要账号", "不注册账号", "不注册"))


def _extract_ghz_size(text: str) -> Optional[int]:
    if not _looks_like_ghz(text):
        return None
    return _extract_explicit_qubit_count(text)


def _looks_like_ghz(text: str) -> bool:
    return bool(re.search(r"\bghz\b|greenberger|最大纠缠|多比特纠缠", text))


def _looks_like_bell(text: str) -> bool:
    return bool(re.search(r"\bbell\b|\bepr\b|贝尔", text))


def _contains_qasm_fragment(prompt: str) -> bool:
    return bool(re.search(r"OPENQASM|qreg|creg|measure|cx\s+q|h\s+q|x\s+q", prompt, re.IGNORECASE))


def _known_task(intent: dict[str, Any]) -> Optional[KnownTask]:
    tasks = {
        "bell": KnownTask("bell", _generate_bell, _validate_bell_semantics),
        "ghz": KnownTask("ghz", _generate_ghz, _validate_ghz_semantics),
    }
    return tasks.get(intent.get("task_id"))


def _generate_bell(intent: dict[str, Any]) -> str:
    return """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
"""


def _generate_ghz(intent: dict[str, Any]) -> str:
    n = int(intent.get("num_qubits", 3))
    if n < 2:
        raise ValueError("GHZ task requires at least 2 qubits")
    gates = ["h q[0];"] + [f"cx q[{i}],q[{i + 1}];" for i in range(n - 1)]
    return "\n".join(
        [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            f"qreg q[{n}];",
            f"creg c[{n}];",
            *gates,
            "measure q -> c;",
            "",
        ]
    )


def _validate_qasm_locally(qasm: str, shots: int = LOCAL_VALIDATION_SHOTS) -> ValidationResult:
    try:
        adapter._parse_qasm(qasm)
        result = adapter.run(qasm, "spinq", shots)
    except Exception as exc:
        return ValidationResult(False, "%s: %s" % (type(exc).__name__, exc))
    return ValidationResult(True, "QASM parsed and executed by the L1 local simulator", result["counts"])


def _validate_bell_semantics(qasm: str, intent: dict[str, Any]) -> ValidationResult:
    return _validate_two_peak_task(qasm, {"00": 0.5, "11": 0.5}, "Bell")


def _validate_ghz_semantics(qasm: str, intent: dict[str, Any]) -> ValidationResult:
    n = int(intent.get("num_qubits", 3))
    return _validate_two_peak_task(qasm, {"0" * n: 0.5, "1" * n: 0.5}, f"GHZ-{n}")


def _validate_two_peak_task(qasm: str, ideal_distribution: dict[str, float], label: str) -> ValidationResult:
    validation = _validate_qasm_locally(qasm)
    if not validation.ok or validation.counts is None:
        return validation
    unexpected = {state: count for state, count in validation.counts.items() if state not in ideal_distribution and count > 0}
    if unexpected:
        return ValidationResult(False, f"{label} produced unexpected state(s): {unexpected}", validation.counts)
    fidelity = _calculate_distribution_fidelity(validation.counts, ideal_distribution)
    if fidelity < SEMANTIC_FIDELITY_THRESHOLD:
        return ValidationResult(
            False,
            f"{label} distribution fidelity {fidelity:.4f} below local semantic threshold {SEMANTIC_FIDELITY_THRESHOLD:.2f}",
            validation.counts,
        )
    return ValidationResult(True, f"{label} semantic validation passed; fidelity={fidelity:.4f}", validation.counts)


def _calculate_distribution_fidelity(counts: dict[str, int], ideal_distribution: dict[str, float]) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    actual = {state: count / total for state, count in counts.items()}
    states = set(actual) | set(ideal_distribution)
    overlap = sum((actual.get(state, 0.0) * ideal_distribution.get(state, 0.0)) ** 0.5 for state in states)
    return overlap * overlap


def select_backends(constraints: dict[str, Any]) -> list[dict[str, Any]]:
    capabilities = _load_backend_capabilities()
    results = []
    for backend in capabilities:
        if backend["max_qubits"] < int(constraints.get("min_qubits", 0) or 0):
            continue
        if constraints.get("queue") == "none" and backend["queue"] != "none":
            continue
        if constraints.get("free_only") and backend["cost"] == "paid":
            continue
        if constraints.get("local_only") and backend["kind"] not in {"simulator"}:
            continue
        if constraints.get("real_hardware") and backend["kind"] != "qpu":
            continue
        if constraints.get("no_account") and backend["requires_account"]:
            continue
        results.append(backend)
    return results


def _load_backend_capabilities() -> list[dict[str, Any]]:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend_capabilities.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["backends"]


def _extract_qasm_from_task_or_text(task: dict[str, Any], text: str) -> Optional[str]:
    qasm = task.get("qasm")
    if isinstance(qasm, str) and "OPENQASM" in qasm:
        return qasm.strip() + "\n"
    try:
        return _extract_qasm(text)
    except Exception:
        return None


def _llm_content(response: dict[str, Any]) -> str:
    return response["choices"][0]["message"]["content"]


def _extract_json_object(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found")
    return match.group(0)


def _extract_qasm(text: str) -> str:
    match = re.search(r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", text, re.DOTALL | re.MULTILINE)
    if not match:
        raise ValueError("LLM response contains no OpenQASM 2.0 program")
    return match.group(0).strip() + "\n"


def _format_backend_answer(backends: list[dict[str, Any]], constraints: dict[str, Any], llm_used: bool) -> str:
    prefix = "LLM intent call completed; deterministic backend filtering used."
    if not llm_used:
        prefix = "Local deterministic development path; no LLM service call was made."
    if not backends:
        return prefix + "\nNo backend satisfies the requested constraints. Constraints: %s\n" % json.dumps(constraints, ensure_ascii=False)
    ids = [backend["id"] for backend in backends]
    lines = [prefix, "Recommended backend ID(s):", *[f"- {backend_id}" for backend_id in ids]]
    return "\n".join(lines) + "\n"


def _format_qasm_answer(qasm: str, validation: ValidationResult, source: str = "agent") -> str:
    counts = validation.counts or {}
    return (
        f"Source: {source}\n"
        f"Validation: {validation.message}\n"
        f"Local counts: {json.dumps(counts, ensure_ascii=False, sort_keys=True)}\n\n"
        "```qasm\n"
        f"{qasm.strip()}\n"
        "```\n"
    )
