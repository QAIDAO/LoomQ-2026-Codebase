"""Shared, deterministic semantic checks for explicit LoomQ L2 requests."""

from __future__ import annotations

import json
import re
from pathlib import Path

from starter_kit.loomq_l1.model import Circuit
from starter_kit.loomq_l1.parser import parse_qasm


_QASM_PATTERN = re.compile(r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", re.DOTALL | re.MULTILINE)
_GHZ_PATTERN = re.compile(r"(?<![A-Za-z0-9_])ghz(?![A-Za-z0-9_])|格林伯格|猫态", re.IGNORECASE)
_BELL_PATTERN = re.compile(r"(?<![A-Za-z0-9_])bell(?![A-Za-z0-9_])|贝尔", re.IGNORECASE)
_EPR_PATTERN = re.compile(r"(?<![A-Za-z0-9_])epr(?![A-Za-z0-9_])|EPR\s*对", re.IGNORECASE)
_MAXIMALLY_ENTANGLED_PATTERN = re.compile(r"最大纠缠态|maximally\s+entangled\s+state", re.IGNORECASE)
_EXECUTION_ACTION_PATTERN = re.compile(
    r"\b(?:generate|create|prepare|build|make|produce|repair|fix|run)\b|生成|制备|构建|创建|给出|修复|运行|执行",
    re.IGNORECASE,
)
_EDUCATIONAL_PROSE_PATTERN = re.compile(
    r"\b(?:explain|explanation|describe|introduction|tutorial|article|about)\b|解释|说明|介绍|科普",
    re.IGNORECASE,
)
_TWO_QUBIT_PATTERN = re.compile(
    r"\b(?:2|two)\s*(?:quantum\s*)?-?\s*qubits?\b|(?:2|二|两)\s*(?:个\s*)?量子?比特",
    re.IGNORECASE,
)
_BACKEND_PATTERN = re.compile(
    r"\b(?:backend|platform|device|simulator)\b|后端|平台|设备|模拟器|真机",
    re.IGNORECASE,
)
_BACKEND_SELECTION_PATTERN = re.compile(
    r"\b(?:choose|select|recommend|pick|use|run)\b|选择|选用|推荐|挑选|使用|运行|执行|给我找",
    re.IGNORECASE,
)
_ZERO_WAIT_PATTERN = re.compile(
    r"queue\s*=\s*none|zero[-\s]?(?:queue|wait(?:ing)?)|no\s+waiting|"
    r"零(?:排队|等待)|无排队|无需等待",
    re.IGNORECASE,
)
_NUMBER_WORDS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
# 16 qubits bounds the local exact statevector at 65,536 amplitudes while
# comfortably covering the GHZ/Bell tasks evaluated by this semantic check.
MAX_SEMANTIC_SIMULATION_QUBITS = 16
# Each H/CX implementation scans the statevector once.  Two million total
# scans retains normal GHZ/Bell circuits (including a 16-qubit GHZ chain) and
# bounds local semantic checking well below the evaluator's 120-second budget.
MAX_SEMANTIC_SIMULATION_WORK = 2_000_000


def _extract_qasm(reply: str) -> str:
    match = _QASM_PATTERN.search(reply)
    if match is None:
        raise ValueError("reply did not contain OpenQASM 2.0")
    return match.group(0).strip()


def _probabilities(circuit: Circuit) -> dict[str, float]:
    width = circuit.num_qubits
    state = [0j] * (1 << width)
    state[0] = 1.0 + 0j
    inv_sqrt2 = 2 ** -0.5
    for operation in circuit.operations:
        if operation.name == "h":
            qubit = operation.qubits[0]
            bit = 1 << qubit
            for index in range(len(state)):
                if index & bit:
                    continue
                paired = index | bit
                zero, one = state[index], state[paired]
                state[index] = (zero + one) * inv_sqrt2
                state[paired] = (zero - one) * inv_sqrt2
        elif operation.name == "cx":
            control, target = operation.qubits
            control_bit, target_bit = 1 << control, 1 << target
            for index in range(len(state)):
                if index & control_bit and not index & target_bit:
                    paired = index | target_bit
                    state[index], state[paired] = state[paired], state[index]
        else:
            raise ValueError("semantic simulator only supports h and cx gates")

    if {measurement.qubit for measurement in circuit.measurements} != set(range(width)):
        raise ValueError("circuit must measure every quantum bit")
    if len(circuit.measurements) != width or circuit.num_clbits != width:
        raise ValueError("circuit must have one full-width classical measurement per quantum bit")

    probabilities: dict[str, float] = {}
    for index, amplitude in enumerate(state):
        probability = abs(amplitude) ** 2
        if probability < 1e-12:
            continue
        cbits = [0] * circuit.num_clbits
        for measurement in circuit.measurements:
            cbits[measurement.cbit] = (index >> measurement.qubit) & 1
        key = "".join(str(bit) for bit in reversed(cbits))
        probabilities[key] = probabilities.get(key, 0.0) + probability
    return probabilities


def _requested_width(prompt: str, default: int) -> int:
    numeric = re.search(
        r"(?<!\d)(\d+)\s*(?:(?:量子\s*)?比特|(?:quantum\s*)?-?\s*qubits?)",
        prompt,
        re.IGNORECASE,
    )
    if numeric is not None:
        return int(numeric.group(1))
    for word, width in _NUMBER_WORDS.items():
        if re.search(re.escape(word) + r"\s*(?:量子)?比特", prompt):
            return width
    return default


def _requests_two_qubit_entanglement(prompt: str) -> bool:
    """Recognize only actionable, unambiguously two-qubit entanglement tasks."""
    if not _requests_circuit_task(prompt):
        return False
    if _EPR_PATTERN.search(prompt) or _BELL_PATTERN.search(prompt):
        return True
    return bool(
        _MAXIMALLY_ENTANGLED_PATTERN.search(prompt)
        and _TWO_QUBIT_PATTERN.search(prompt)
    )


def _requests_circuit_task(prompt: str) -> bool:
    """Keep a pure tutorial or article out of the structured-circuit path."""
    if not _EXECUTION_ACTION_PATTERN.search(prompt):
        return False
    return not _EDUCATIONAL_PROSE_PATTERN.search(prompt) or bool(
        re.search(r"\b(?:circuit|qasm|openqasm|measure(?:ment)?)\b|电路|测量", prompt, re.IGNORECASE)
    )


def _distribution_error(reply: str, width: int) -> str | None:
    try:
        circuit = parse_qasm(_extract_qasm(reply))
        if circuit.num_qubits != width:
            return f"expected {width} quantum bits, got {circuit.num_qubits}"
        if circuit.num_qubits > MAX_SEMANTIC_SIMULATION_QUBITS:
            return "circuit width exceeds safe semantic simulation limit"
        if len(circuit.operations) * (1 << circuit.num_qubits) > MAX_SEMANTIC_SIMULATION_WORK:
            return "circuit semantic simulation work exceeds safe limit"
        observed = _probabilities(circuit)
    except Exception:
        return "invalid circuit syntax or unsupported operation"
    expected = {"0" * width: 0.5, "1" * width: 0.5}
    if set(observed) != set(expected) or any(
        abs(observed.get(key, 0.0) - probability) > 1e-9
        for key, probability in expected.items()
    ):
        return f"expected GHZ/Bell distribution {expected}, got {observed}"
    return None


def _backend_constraints(prompt: str) -> tuple[int | None, bool, bool] | None:
    if not _BACKEND_PATTERN.search(prompt):
        return None
    minimum = re.search(r"(?:至少|at\s+least)\s*(\d+)\s*(?:量子)?(?:比特|qubits?)", prompt, re.IGNORECASE)
    requires_free = bool(re.search(r"\bfree\b|免费", prompt, re.IGNORECASE))
    selects_backend = bool(_BACKEND_SELECTION_PATTERN.search(prompt))
    requires_zero_queue = bool(
        _ZERO_WAIT_PATTERN.search(prompt) and selects_backend
    )
    if _EDUCATIONAL_PROSE_PATTERN.search(prompt) and not (
        selects_backend and (minimum is not None or requires_free)
    ):
        return None
    if minimum is None and not requires_free and not requires_zero_queue:
        return None
    return (int(minimum.group(1)) if minimum else None, requires_free, requires_zero_queue)


def _qualified_backend_ids(prompt: str) -> tuple[str, ...]:
    constraints = _backend_constraints(prompt)
    if constraints is None:
        return ()
    min_qubits, requires_free, requires_zero_queue = constraints
    source = Path(__file__).with_name("backend_capabilities.json")
    payload = json.loads(source.read_text(encoding="utf-8"))
    return tuple(
        item["id"]
        for item in payload["backends"]
        if (min_qubits is None or item.get("max_qubits", 0) >= min_qubits)
        and (not requires_free or item.get("cost") == "free")
        and (not requires_zero_queue or item.get("queue") == "none")
    )


def validate_prompt_reply(prompt: str, reply: str) -> str | None:
    """Validate only semantics explicitly requested in *prompt*.

    Unknown requests deliberately return ``None`` so a caller can retain its
    ordinary syntax validation without inventing an unsupported semantic rule.
    """
    if not isinstance(prompt, str):
        return None
    if _GHZ_PATTERN.search(prompt) and _requests_circuit_task(prompt):
        return _distribution_error(reply, _requested_width(prompt, 3))
    if _requests_two_qubit_entanglement(prompt):
        return _distribution_error(reply, 2)

    backend_constraints = _backend_constraints(prompt)
    if backend_constraints is not None:
        backend_ids = _qualified_backend_ids(prompt)
        if not backend_ids:
            return "no configured backend satisfies the explicit capability constraints"
        for backend_id in backend_ids:
            if re.search(r"(?<![A-Za-z0-9_])" + re.escape(backend_id) + r"(?![A-Za-z0-9_])", reply):
                return None
        return "reply must contain a canonical backend id satisfying the explicit capability constraints"
    return None
