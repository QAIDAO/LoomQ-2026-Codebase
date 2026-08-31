"""Local validation of generated OpenQASM against explicit user intent."""

import math
import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

try:
    from ..loomq_core.model import Circuit
    from ..loomq_core.qasm2 import parse_qasm2
    from ..loomq_core.simulator import simulate_counts
except ImportError:
    from loomq_core.model import Circuit
    from loomq_core.qasm2 import parse_qasm2
    from loomq_core.simulator import simulate_counts


@dataclass(frozen=True)
class ValidationResult:
    circuit: Circuit
    counts: Dict[str, int]
    fidelity: Optional[float]


_CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def validate_generated_qasm(prompt: str, qasm: str) -> ValidationResult:
    circuit = parse_qasm2(qasm)
    counts = simulate_counts(circuit, 8192)
    expected = _expected_distribution(prompt, circuit)
    fidelity = None
    if expected is not None:
        fidelity = _fidelity(counts, expected)
        if fidelity < 0.97:
            rendered = ", ".join(f"{key}:{value}" for key, value in counts.items())
            raise ValueError(
                "generated circuit does not match the requested measurement distribution "
                f"(fidelity={fidelity:.4f}, counts={rendered})"
            )
    return ValidationResult(circuit, counts, fidelity)


def qasm_correction_guidance(prompt: str) -> str:
    pair = _explicit_binary_pair(prompt)
    if pair is None:
        return ""
    first, second = pair
    differing = [index for index in range(len(first)) if first[index] != second[index]]
    pivot_character = next(
        (index for index in differing if first[index] == "0"),
        None,
    )
    if pivot_character is None:
        first, second = second, first
        pivot_character = next(index for index in differing if first[index] == "0")
    width = len(first)
    pivot_qubit = width - 1 - pivot_character
    operations = [
        f"x q[{width - 1 - index}];"
        for index, bit in enumerate(first)
        if bit == "1"
    ]
    operations.append(f"h q[{pivot_qubit}];")
    operations.extend(
        f"cx q[{pivot_qubit}], q[{width - 1 - index}];"
        for index in differing
        if index != pivot_character
    )
    return (
        "。由目标位串自动推导的修正门序列为："
        + " ".join(operations)
        + f" 该序列从 |{first}> 得到 |{first}> 与 |{second}> 的等概率叠加"
    )


def _expected_distribution(
    prompt: str, circuit: Circuit
) -> Optional[Dict[str, float]]:
    lowered = prompt.lower()
    explicit = _explicit_binary_pair(prompt)
    if explicit is not None:
        first, second = explicit
        _require_width(circuit, len(first))
        return {first: 0.5, second: 0.5}
    single = _explicit_binary_state(prompt)
    if single is not None:
        _require_width(circuit, len(single))
        return {single: 1.0}
    if "bell" in lowered or "贝尔" in prompt or "epr" in lowered:
        _require_width(circuit, 2)
        return {"00": 0.5, "11": 0.5}
    requested_width = _requested_width(prompt)
    if (
        "ghz" in lowered
        or "最大纠缠" in prompt
        or "猫态" in prompt
        or "cat state" in lowered
        or "maximally entangled" in lowered
        or (requested_width == 2 and "纠缠态" in prompt)
    ):
        width = requested_width or circuit.qubit_count
        _require_width(circuit, width)
        return {"0" * width: 0.5, "1" * width: 0.5}
    return None


def _explicit_binary_pair(prompt: str) -> Optional[Tuple[str, str]]:
    values = re.findall(r"(?<![01])([01]{2,})(?![01])", prompt)
    for index, first in enumerate(values):
        for second in values[index + 1 :]:
            if len(first) == len(second) and first != second:
                return first, second
    return None


def _explicit_binary_state(prompt: str) -> Optional[str]:
    ket = re.findall(r"\|\s*([01]{2,})\s*>", prompt)
    return ket[0] if len(set(ket)) == 1 else None


def _requested_width(prompt: str) -> Optional[int]:
    digit = re.search(r"(\d+)\s*(?:个\s*)?(?:量子)?比特", prompt, re.I)
    if digit:
        return int(digit.group(1))
    chinese = re.search(r"([一二两三四五六七八九十])\s*(?:个\s*)?(?:量子)?比特", prompt)
    if chinese:
        return _CHINESE_NUMBERS[chinese.group(1)]
    english = re.search(r"(\d+)\s*[- ]?\s*qubits?", prompt, re.I)
    if english:
        return int(english.group(1))
    return None


def _require_width(circuit: Circuit, width: int) -> None:
    if circuit.qubit_count != width or circuit.classical_bit_count != width:
        raise ValueError(
            f"generated circuit uses {circuit.qubit_count} qubits and "
            f"{circuit.classical_bit_count} classical bits; requested {width}"
        )
    measured_qubits = {circuit.quantum_index(item.qubit) for item in circuit.measurements}
    measured_bits = {circuit.classical_index(item.classical) for item in circuit.measurements}
    expected = set(range(width))
    if (
        len(circuit.measurements) != width
        or measured_qubits != expected
        or measured_bits != expected
    ):
        raise ValueError("generated circuit must measure every requested qubit exactly once")


def _fidelity(counts: Dict[str, int], expected: Dict[str, float]) -> float:
    shots = sum(counts.values())
    keys = set(counts) | set(expected)
    distance = math.sqrt(
        sum(
            (
                math.sqrt(counts.get(key, 0) / shots)
                - math.sqrt(expected.get(key, 0.0))
            )
            ** 2
            for key in keys
        )
        / 2
    )
    return 1 - distance
