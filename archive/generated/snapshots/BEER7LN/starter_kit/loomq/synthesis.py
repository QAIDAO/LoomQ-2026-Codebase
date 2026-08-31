"""Deterministic circuit synthesis from a normalized L2 task specification."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping

from .gate_policy import assert_gate_names
from .qasm import GateOperation, parse_openqasm2


_TASK_ALIASES = {
    "generate": "generate_qasm",
    "generate_circuit": "generate_qasm",
    "create_qasm": "generate_qasm",
    "repair": "repair_qasm",
    "fix_qasm": "repair_qasm",
    "recommend": "select_backend",
    "recommend_backend": "select_backend",
    "select": "select_backend",
}
_FAMILY_ALIASES = {
    "bell_pair": "bell",
    "epr": "bell",
    "cat": "ghz",
    "cat_state": "ghz",
    "w_state": "w",
    "fourier": "qft",
    "quantum_fourier_transform": "qft",
    "search": "grover",
    "uniform_superposition": "uniform",
    "basis_state": "basis",
    "computational_basis": "basis",
    "interference": "phase_interference",
}


@dataclass(frozen=True)
class CircuitSpec:
    family: str
    qubits: int
    target: str | None = None


@dataclass(frozen=True)
class SynthesisResult:
    spec: CircuitSpec
    qasm: str
    expected_dominant_states: tuple[str, ...]


def normalize_task_type(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("task_type must be a non-empty string")
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return _TASK_ALIASES.get(normalized, normalized)


def normalize_circuit_spec(
    plan: Mapping[str, Any], prompt: str
) -> CircuitSpec | None:
    """Normalize model aliases, then fill safe omissions from the user prompt."""

    raw = _first_mapping(plan, "circuit_spec", "spec", "target_spec")
    family_value: Any = None
    width_value: Any = None
    target_value: Any = None
    if raw is not None:
        family_value = _first(raw, "family", "state", "target_state", "algorithm")
        width_value = _first(raw, "qubits", "n_qubits", "width", "size")
        target_value = _first(raw, "target", "bitstring", "marked_state")

    prompt_family, prompt_width, prompt_target = _prompt_spec(prompt)
    family = _normalize_family(family_value) if family_value is not None else prompt_family
    if family is None:
        return None
    width = _positive_int(width_value) if width_value is not None else prompt_width
    target = _binary_target(target_value) if target_value is not None else prompt_target

    if family == "bell":
        width = 2
    elif family == "phase_interference":
        width = 1
    elif family == "basis" and target is not None:
        width = len(target)
    elif family == "grover":
        width = width or (len(target) if target else 3)
        target = target or "1" * width
    if width is None:
        return None
    _validate_spec(CircuitSpec(family, width, target))
    return CircuitSpec(family, width, target)


def synthesize(spec: CircuitSpec) -> SynthesisResult:
    """Create a measured circuit using only the public twelve-gate basis."""

    _validate_spec(spec)
    if spec.family == "bell":
        gates = ["h q[0];", "cx q[0], q[1];"]
        expected = ("00", "11")
    elif spec.family == "ghz":
        gates = ["h q[0];"] + [
            f"cx q[{index - 1}], q[{index}];"
            for index in range(1, spec.qubits)
        ]
        expected = ("0" * spec.qubits, "1" * spec.qubits)
    elif spec.family == "uniform":
        gates = [f"h q[{index}];" for index in range(spec.qubits)]
        expected = tuple(
            format(value, f"0{spec.qubits}b")
            for value in range(1 << spec.qubits)
        )
    elif spec.family == "basis":
        assert spec.target is not None
        gates = [
            f"x q[{index}];"
            for index, bit in enumerate(reversed(spec.target))
            if bit == "1"
        ]
        expected = (spec.target,)
    elif spec.family == "phase_interference":
        gates = ["h q[0];", "rz(pi) q[0];", "h q[0];"]
        expected = ("1",)
    elif spec.family == "w":
        gates = _w_state_gates(spec.qubits)
        expected = tuple(
            format(1 << index, f"0{spec.qubits}b")
            for index in range(spec.qubits)
        )
    elif spec.family == "qft":
        gates = _qft_gates(spec.qubits, spec.target)
        expected = tuple(
            format(value, f"0{spec.qubits}b")
            for value in range(1 << spec.qubits)
        )
    elif spec.family == "grover":
        assert spec.target is not None
        gates = _grover_gates(spec.target)
        expected = (spec.target,)
    else:
        raise ValueError(f"unsupported deterministic circuit family: {spec.family}")

    qasm = _program(spec.qubits, gates)
    program = parse_openqasm2(qasm)
    assert_gate_names(
        operation.name
        for operation in program.operations
        if isinstance(operation, GateOperation)
    )
    return SynthesisResult(spec, qasm, expected)


def _program(width: int, gates: list[str]) -> str:
    return "\n".join(
        [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            f"qreg q[{width}];",
            f"creg c[{width}];",
            *gates,
            "measure q -> c;",
            "",
        ]
    )


def _w_state_gates(width: int) -> list[str]:
    gates = ["x q[0];"]
    for index in range(width - 1):
        remaining = width - index
        angle = 2.0 * math.acos(1.0 / math.sqrt(remaining))
        gates.extend(_controlled_ry(index, index + 1, angle))
        gates.append(f"cx q[{index + 1}], q[{index}];")
    return gates


def _controlled_ry(control: int, target: int, angle: float) -> list[str]:
    half = _decimal(angle / 2.0)
    negative_half = _decimal(-angle / 2.0)
    return [
        f"ry({half}) q[{target}];",
        f"cx q[{control}], q[{target}];",
        f"ry({negative_half}) q[{target}];",
        f"cx q[{control}], q[{target}];",
    ]


def _qft_gates(width: int, target: str | None) -> list[str]:
    gates: list[str] = []
    if target is not None:
        gates.extend(
            f"x q[{index}];"
            for index, bit in enumerate(reversed(target))
            if bit == "1"
        )
    for current in reversed(range(width)):
        gates.append(f"h q[{current}];")
        for control in reversed(range(current)):
            denominator = 1 << (current - control)
            gates.append(
                f"cu1(pi/{denominator}) q[{current}], q[{control}];"
            )
    for index in range(width // 2):
        gates.append(f"swap q[{index}], q[{width - index - 1}];")
    return gates


def _grover_gates(target: str) -> list[str]:
    width = len(target)
    if width != 3:
        raise ValueError("deterministic Grover synthesis currently supports 3 qubits")
    gates = [f"h q[{index}];" for index in range(width)]
    for _iteration in range(2):
        gates.extend(_phase_marked_state(target))
        gates.extend(f"h q[{index}];" for index in range(width))
        gates.extend(f"x q[{index}];" for index in range(width))
        gates.extend(
            [
                "h q[2];",
                "ccx q[0], q[1], q[2];",
                "h q[2];",
            ]
        )
        gates.extend(f"x q[{index}];" for index in range(width))
        gates.extend(f"h q[{index}];" for index in range(width))
    return gates


def _phase_marked_state(target: str) -> list[str]:
    zero_qubits = [
        index for index, bit in enumerate(reversed(target)) if bit == "0"
    ]
    gates = [f"x q[{index}];" for index in zero_qubits]
    gates.extend(["h q[2];", "ccx q[0], q[1], q[2];", "h q[2];"])
    gates.extend(f"x q[{index}];" for index in reversed(zero_qubits))
    return gates


def _prompt_spec(prompt: str) -> tuple[str | None, int | None, str | None]:
    lowered = prompt.lower()
    width = _prompt_width(prompt)
    target = _prompt_binary_target(prompt, width)
    if "grover" in lowered or "格罗弗" in prompt or "量子搜索" in prompt:
        return "grover", width or 3, target
    if "qft" in lowered or "fourier" in lowered or "傅里叶" in prompt:
        return "qft", width, target
    if re.search(r"\bw(?:\s*[- ]?\s*state)?\b", lowered) or "w态" in lowered:
        return "w", width, None
    if any(
        cue in lowered
        for cue in ("ghz", "cat state", "猫态", "最大纠缠态", "最大纠缠")
    ):
        return "ghz", width, None
    if "bell" in lowered or "epr" in lowered or "贝尔" in prompt:
        return "bell", 2, None
    if any(
        cue in lowered
        for cue in (
            "uniform superposition",
            "equally likely",
            "equal probability",
            "均匀叠加",
            "等概率",
        )
    ):
        return "uniform", width, None
    if (
        "h-rz(pi)-h" in re.sub(r"\s+", "", lowered).replace("π", "pi")
        or "phase interference" in lowered
        or "相位干涉" in prompt
    ):
        return "phase_interference", 1, None
    if target is not None and any(
        cue in lowered
        for cue in (
            "always",
            "must measure",
            "must return",
            "deterministic",
            "始终",
            "总是",
            "确定性",
            "必然",
        )
    ):
        return "basis", len(target), target
    return None, width, target


def _prompt_width(prompt: str) -> int | None:
    matches = {
        int(value)
        for value in re.findall(
            r"(?<![\w.])(\d+)\s*-?\s*(?:qubits?|quantum\s+bits?|量子比特|比特)",
            prompt,
            flags=re.IGNORECASE,
        )
    }
    return next(iter(matches)) if len(matches) == 1 else None


def _prompt_binary_target(prompt: str, width: int | None) -> str | None:
    candidates = {
        match.group(0)
        for match in re.finditer(r"(?<![01])[01]{2,}(?![01])", prompt)
        if width is None or len(match.group(0)) == width
    }
    return next(iter(candidates)) if len(candidates) == 1 else None


def _normalize_family(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("circuit family must be a non-empty string")
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return _FAMILY_ALIASES.get(normalized, normalized)


def _validate_spec(spec: CircuitSpec) -> None:
    if spec.family not in {
        "bell",
        "ghz",
        "uniform",
        "basis",
        "phase_interference",
        "w",
        "qft",
        "grover",
    }:
        raise ValueError(f"unsupported circuit family: {spec.family}")
    if isinstance(spec.qubits, bool) or not 1 <= spec.qubits <= 12:
        raise ValueError("deterministic synthesis supports 1 through 12 qubits")
    if spec.family in {"ghz", "bell", "w"} and spec.qubits < 2:
        raise ValueError(f"{spec.family} requires at least two qubits")
    if spec.family == "grover" and spec.qubits != 3:
        raise ValueError("deterministic Grover synthesis currently supports 3 qubits")
    if spec.target is not None:
        if len(spec.target) != spec.qubits or set(spec.target) - {"0", "1"}:
            raise ValueError("target bit string must match the requested qubit width")
    if spec.family in {"basis", "grover"} and spec.target is None:
        raise ValueError(f"{spec.family} requires a target bit string")


def _positive_int(value: Any) -> int:
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("qubits must be a positive integer")
    return value


def _binary_target(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("target bit string must be text")
    normalized = value.strip().replace("0b", "").replace(" ", "")
    if not normalized or set(normalized) - {"0", "1"}:
        raise ValueError("target bit string must contain only zero and one")
    return normalized


def _first(source: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in source and source[name] is not None:
            return source[name]
    return None


def _first_mapping(
    source: Mapping[str, Any], *names: str
) -> Mapping[str, Any] | None:
    for name in names:
        value = source.get(name)
        if isinstance(value, Mapping):
            return value
    return None


def _decimal(value: float) -> str:
    rendered = format(value, ".17g")
    return "0" if rendered in {"-0", "-0.0"} else rendered
