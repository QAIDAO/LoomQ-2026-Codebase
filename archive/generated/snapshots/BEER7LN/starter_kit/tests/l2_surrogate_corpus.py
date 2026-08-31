"""Generated hidden-family surrogate corpus for LoomQ L2 development.

The corpus is locally authored. It is not the organizer's private case set and
its results are never an official competition score.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

from loomq.qasm import parse_openqasm2  # noqa: E402
from tests.test_l1_property import _reference_distribution  # noqa: E402
CAPABILITIES_FILE = STARTER_KIT / "backend_capabilities.json"
EXTENDED_SEED = 2026081203


@dataclass(frozen=True)
class ExtendedCase:
    case_id: str
    category: str
    prompt: str
    family: str
    qubits: int
    language: str
    expected_distribution: dict[str, float] | None = None
    reference_qasm: str | None = None
    selection_constraints: dict[str, Any] | None = None
    mutation: str | None = None
    semantic_mutation: bool = False
    broken_qasm: str | None = None


@dataclass(frozen=True)
class TargetSpec:
    name: str
    family: str
    qubits: int
    expected: dict[str, float]
    qasm: str


def _distribution(*states: str) -> dict[str, float]:
    probability = 1.0 / len(states)
    return {state: probability for state in states}


def _uniform(width: int) -> dict[str, float]:
    probability = 1.0 / (1 << width)
    return {format(value, f"0{width}b"): probability for value in range(1 << width)}


def _program(width: int, gates: list[str]) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{width}];",
        f"creg c[{width}];",
        *gates,
        "measure q -> c;",
    ]
    return "\n".join(lines) + "\n"


def _ghz(width: int) -> str:
    gates = ["h q[0];"] + [f"cx q[{index - 1}],q[{index}];" for index in range(1, width)]
    return _program(width, gates)


def _deterministic(target: str) -> str:
    gates = [f"x q[{index}];" for index, bit in enumerate(reversed(target)) if bit == "1"]
    return _program(len(target), gates)


def _target_specs() -> tuple[TargetSpec, ...]:
    specs: list[TargetSpec] = [
        TargetSpec("bell", "bell", 2, _distribution("00", "11"), _ghz(2)),
    ]
    for width in (2, 3, 4, 5, 6, 8):
        specs.append(TargetSpec(f"ghz-{width}", "ghz", width, _distribution("0" * width, "1" * width), _ghz(width)))
    for width in (1, 2, 3, 4):
        specs.append(TargetSpec(f"uniform-{width}", "uniform", width, _uniform(width), _program(width, [f"h q[{index}];" for index in range(width)])))
    for target in ("10", "101", "0110", "10101"):
        specs.append(TargetSpec(f"deterministic-{target}", "deterministic", len(target), _distribution(target), _deterministic(target)))
    specs.append(TargetSpec("phase-interference-1", "phase", 1, _distribution("1"), _program(1, ["h q[0];", "rz(pi) q[0];", "h q[0];"])))
    assert len(specs) == 16
    return tuple(specs)


def _target_phrase(spec: TargetSpec, language: str) -> str:
    if spec.family == "bell":
        return "a fully measured Bell state with 00 and 11 equally likely" if language == "en" else "全测量的贝尔态，00 与 11 等概率"
    if spec.family == "ghz":
        return f"a fully measured {spec.qubits}-qubit GHZ state" if language == "en" else f"全测量的 {spec.qubits} 量子比特 GHZ 最大纠缠态"
    if spec.family == "uniform":
        return f"a fully measured {spec.qubits}-qubit uniform superposition, with all outcomes equally likely" if language == "en" else f"全测量的 {spec.qubits} 量子比特均匀叠加态，让所有结果等概率"
    if spec.family == "deterministic":
        target = next(iter(spec.expected))
        return f"a measured {spec.qubits}-qubit state that always returns {target}" if language == "en" else f"测量后始终返回 {target} 的 {spec.qubits} 量子比特状态"
    return "the one-qubit interference H-RZ(pi)-H that must measure 1" if language == "en" else "单比特干涉 H-RZ(pi)-H，测量结果必须为 1"


def _generation_prompt(spec: TargetSpec, variant: int) -> tuple[str, str]:
    languages = ("en", "zh", "mixed", "en")
    language = languages[variant]
    phrase = _target_phrase(spec, "zh" if language == "zh" else "en")
    templates = (
        "Generate complete executable OpenQASM 2.0 for {target}. Include all measurements.",
        "请生成完整且可执行的 OpenQASM 2.0，实现{target}，并测量全部量子比特。",
        "I need 可执行 OpenQASM 2.0 for {target}; 请补齐寄存器与全测量。",
        "Without relying on pseudocode, return a complete OpenQASM 2.0 circuit for {target}.",
    )
    return templates[variant].format(target=phrase), language


MUTATIONS = (
    "missing_declarations",
    "case_and_punctuation",
    "wrong_gate",
    "wrong_control",
    "wrong_bit_order",
    "missing_measurement",
)
SEMANTIC_MUTATIONS = {"wrong_gate", "wrong_control", "wrong_bit_order"}


def _mutate(spec: TargetSpec, mutation: str) -> str:
    lines = [line for line in spec.qasm.strip().splitlines()]
    if mutation == "missing_declarations":
        return " ".join(line for line in lines if not line.startswith(("OPENQASM", "include", "qreg", "creg")))
    if mutation == "case_and_punctuation":
        return " ".join(lines).replace("h q", "H q").replace("cx q", "CX q").replace("measure", "MEASURE").replace(",", " ").replace(";", "", 2)
    if mutation == "missing_measurement":
        return "\n".join(line for line in lines if not line.startswith("measure"))
    if mutation == "wrong_gate":
        if spec.family == "phase":
            return _program(spec.qubits, [])
        return _program(spec.qubits, ["x q[0];"])
    if mutation == "wrong_control":
        gates = ["cx q[0],q[1];"] if spec.qubits > 1 else []
        return _program(spec.qubits, gates)
    if mutation == "wrong_bit_order":
        if spec.family == "deterministic":
            target = next(iter(spec.expected))
            reversed_target = target[::-1]
            if reversed_target == target:
                reversed_target = ("0" if target[0] == "1" else "1") + target[1:]
            return _deterministic(reversed_target)
        if spec.qubits == 1:
            return _program(1, [])
        gates = [line for line in lines if line.startswith(("h ", "x ", "rz", "ry", "cx ", "cu1", "swap", "ccx"))]
        header = _program(spec.qubits, gates).replace("measure q -> c;\n", "")
        return header + f"measure q[0] -> c[{spec.qubits - 1}];\n"
    raise ValueError(f"unknown mutation: {mutation}")

def _repair_prompt(spec: TargetSpec, variant: int, mutation: str) -> tuple[str, str, str]:
    languages = ("en", "zh", "mixed", "en")
    language = languages[variant]
    phrase = _target_phrase(spec, "zh" if language == "zh" else "en")
    broken = _mutate(spec, mutation)
    templates = (
        "Repair the following program while preserving the declared target, {target}. Return complete OpenQASM 2.0:\n{broken}",
        "目标是{target}。以下代码有错误，请保持目标不变并修复为完整 OpenQASM 2.0：\n{broken}",
        "Please 修复 this circuit for {target}. Preserve semantics and return executable OpenQASM 2.0:\n{broken}",
        "The snippet may be syntactically valid but semantically wrong. Make it implement {target}:\n{broken}",
    )
    return templates[variant].format(target=phrase, broken=broken), language, broken


def _base_constraints(qubits: int, profile: int) -> dict[str, Any]:
    profiles = (
        {},
        {"require_zero_queue": True, "avoid_paid": True},
        {"require_real_hardware": True, "avoid_paid": True},
        {"require_no_account": True, "require_zero_queue": True},
    )
    constraints: dict[str, Any] = {
        "min_qubits": qubits,
        "required_kind": None,
        "require_real_hardware": False,
        "require_zero_queue": False,
        "avoid_paid": False,
        "require_no_account": False,
        "allowed_platforms": [],
    }
    constraints.update(profiles[profile])
    return constraints


def _selection_prompt(qubits: int, variant: int, constraints: Mapping[str, Any]) -> tuple[str, str]:
    languages = ("en", "zh", "mixed", "en")
    language = languages[variant]
    requirements: list[str] = [f"at least {qubits} qubits"]
    if constraints.get("required_kind"):
        requirements.append(str(constraints["required_kind"]))
    if constraints.get("require_real_hardware"):
        requirements.append("real quantum hardware")
    if constraints.get("require_zero_queue"):
        requirements.append("zero queue")
    if constraints.get("avoid_paid"):
        requirements.append("not paid-only")
    if constraints.get("require_no_account"):
        requirements.append("no account")
    if constraints.get("allowed_platforms"):
        requirements.append("platform " + ",".join(str(item) for item in constraints["allowed_platforms"]))
    joined = ", ".join(requirements)
    templates = (
        "Using only the official capability table, recommend one canonical backend ID for: {requirements}.",
        "只根据官方后端能力表，为这些条件推荐一个规范后端 ID：至少 {qubits} 比特；{requirements}。若无解请直说。",
        "Select 后端 canonical ID with {requirements}; 不满足全部约束时不得编造答案。",
        "Find a published backend satisfying every constraint ({requirements}). Return no backend ID if impossible.",
    )
    return templates[variant].format(qubits=qubits, requirements=joined), language


def build_extended_cases() -> list[ExtendedCase]:
    cases: list[ExtendedCase] = []
    specs = _target_specs()
    for spec_index, spec in enumerate(specs):
        for variant in range(4):
            prompt, language = _generation_prompt(spec, variant)
            cases.append(ExtendedCase(
                f"ext-g-{spec.name}-v{variant + 1}", "generate", prompt,
                spec.family, spec.qubits, language, dict(spec.expected), spec.qasm,
            ))
            mutation = MUTATIONS[(spec_index * 4 + variant) % len(MUTATIONS)]
            repair_prompt, repair_language, broken = _repair_prompt(spec, variant, mutation)
            semantic = False
            if mutation in SEMANTIC_MUTATIONS:
                broken_distribution = independent_distribution(broken)
                semantic = hellinger_fidelity(broken_distribution, spec.expected) < 0.97
            cases.append(ExtendedCase(
                f"ext-r-{spec.name}-{mutation}-v{variant + 1}", "repair", repair_prompt,
                spec.family, spec.qubits, repair_language, dict(spec.expected), spec.qasm,
                mutation=mutation, semantic_mutation=semantic, broken_qasm=broken,
            ))

    boundaries = (1, 8, 9, 15, 24, 25, 26, 30, 31, 34, 35, 50, 180, 181, 200, 5)
    for boundary_index, qubits in enumerate(boundaries):
        for variant in range(4):
            constraints = _base_constraints(qubits, variant)
            if boundary_index == 15 and variant == 0:
                constraints["required_kind"] = "cloud"
            if boundary_index == 15 and variant == 1:
                constraints["allowed_platforms"] = ["braket"]
            prompt, language = _selection_prompt(qubits, variant, constraints)
            cases.append(ExtendedCase(
                f"ext-s-q{qubits}-p{variant + 1}-b{boundary_index}", "select", prompt,
                "backend", qubits, language, selection_constraints=constraints,
            ))
    assert len(cases) == 192
    return cases


def independent_distribution(qasm: str | None) -> dict[str, float]:
    if not qasm:
        raise ValueError("reference QASM is required")
    return _reference_distribution(parse_openqasm2(qasm))


def hellinger_fidelity(observed: Mapping[str, float], expected: Mapping[str, float]) -> float:
    states = set(observed) | set(expected)
    coefficient = sum(
        max(0.0, float(observed.get(state, 0.0))) ** 0.5
        * max(0.0, float(expected.get(state, 0.0))) ** 0.5
        for state in states
    )
    return min(1.0, coefficient * coefficient)


def _capabilities() -> list[dict[str, Any]]:
    payload = json.loads(CAPABILITIES_FILE.read_text(encoding="utf-8"))
    return [dict(item) for item in payload["backends"]]


def canonical_backend_ids() -> set[str]:
    return {str(item["id"]) for item in _capabilities()}


def expected_backend_ids(constraints: Mapping[str, Any] | None) -> set[str]:
    if constraints is None:
        return set()
    required_kind = "qpu" if constraints.get("require_real_hardware") else constraints.get("required_kind")
    allowed = {str(item).lower() for item in constraints.get("allowed_platforms", [])}
    matches: set[str] = set()
    for backend in _capabilities():
        if int(backend["max_qubits"]) < int(constraints.get("min_qubits", 1)):
            continue
        if required_kind and backend["kind"] != required_kind:
            continue
        if constraints.get("require_zero_queue") and backend["queue"] != "none":
            continue
        if constraints.get("avoid_paid") and backend["cost"] == "paid":
            continue
        if constraints.get("require_no_account") and backend["requires_account"]:
            continue
        if allowed and str(backend["platform"]).lower() not in allowed:
            continue
        matches.add(str(backend["id"]))
    return matches


def _case_rank(case: ExtendedCase, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{case.case_id}".encode("utf-8")).hexdigest()


def _sample_category(cases: list[ExtendedCase], count: int, seed: int) -> list[ExtendedCase]:
    selected: list[ExtendedCase] = []
    if cases[0].category in {"generate", "repair"}:
        for family in ("bell", "ghz", "uniform", "deterministic", "phase"):
            family_cases = [case for case in cases if case.family == family]
            selected.append(min(family_cases, key=lambda case: _case_rank(case, seed)))
        if cases[0].category == "repair" and not any(case.semantic_mutation for case in selected):
            selected.append(min((case for case in cases if case.semantic_mutation), key=lambda case: _case_rank(case, seed)))
    else:
        no_solution = [case for case in cases if not expected_backend_ids(case.selection_constraints)]
        selected.append(min(no_solution, key=lambda case: _case_rank(case, seed)))
    selected_ids = {case.case_id for case in selected}
    remaining = sorted((case for case in cases if case.case_id not in selected_ids), key=lambda case: _case_rank(case, seed))
    selected.extend(remaining[: count - len(selected)])
    return sorted(selected, key=lambda case: case.case_id)


def stratified_live_sample(size: int = 60, seed: int = EXTENDED_SEED) -> list[ExtendedCase]:
    if size <= 0 or size % 3:
        raise ValueError("sample size must be a positive multiple of three")
    per_category = size // 3
    cases = build_extended_cases()
    if per_category > 64:
        raise ValueError("sample requests more cases than the corpus contains")
    selected: list[ExtendedCase] = []
    for category in ("generate", "repair", "select"):
        selected.extend(_sample_category([case for case in cases if case.category == category], per_category, seed))
    return selected
