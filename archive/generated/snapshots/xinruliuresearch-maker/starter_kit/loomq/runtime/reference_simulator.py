"""A compact, genuine state-vector simulator used for local fallback and verification.

The implementation computes amplitudes and samples them; it does not contain
case-specific distributions or precomputed circuit answers.
"""

import bisect
import cmath
import math
import random
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from ..errors import SimulationError
from ..targets.base import gate_fields, is_measurement, measurement_fields


MAX_REFERENCE_QUBITS = 20


def _single_qubit(state: List[complex], qubit: int, matrix: Sequence[Sequence[complex]]) -> None:
    mask = 1 << qubit
    for base in range(len(state)):
        if base & mask:
            continue
        paired = base | mask
        zero = state[base]
        one = state[paired]
        state[base] = matrix[0][0] * zero + matrix[0][1] * one
        state[paired] = matrix[1][0] * zero + matrix[1][1] * one


def _cx(state: List[complex], control: int, target: int) -> None:
    control_mask = 1 << control
    target_mask = 1 << target
    for index in range(len(state)):
        if index & control_mask and not index & target_mask:
            paired = index | target_mask
            state[index], state[paired] = state[paired], state[index]


def _controlled_phase(state: List[complex], control: int, target: int, angle: float) -> None:
    mask = (1 << control) | (1 << target)
    phase = cmath.exp(1j * angle)
    for index in range(len(state)):
        if index & mask == mask:
            state[index] *= phase


def _swap(state: List[complex], first: int, second: int) -> None:
    first_mask = 1 << first
    second_mask = 1 << second
    for index in range(len(state)):
        if not index & first_mask and index & second_mask:
            paired = index ^ first_mask ^ second_mask
            state[index], state[paired] = state[paired], state[index]


def _ccx(state: List[complex], first: int, second: int, target: int) -> None:
    controls = (1 << first) | (1 << second)
    target_mask = 1 << target
    for index in range(len(state)):
        if index & controls == controls and not index & target_mask:
            paired = index | target_mask
            state[index], state[paired] = state[paired], state[index]


def _apply_gate(state: List[complex], operation: Any) -> None:
    name, params, qubits = gate_fields(operation)
    inv_sqrt_two = 1.0 / math.sqrt(2.0)
    if name == "h":
        _single_qubit(state, qubits[0], ((inv_sqrt_two, inv_sqrt_two), (inv_sqrt_two, -inv_sqrt_two)))
    elif name == "x":
        _single_qubit(state, qubits[0], ((0, 1), (1, 0)))
    elif name == "s":
        _single_qubit(state, qubits[0], ((1, 0), (0, 1j)))
    elif name == "sdg":
        _single_qubit(state, qubits[0], ((1, 0), (0, -1j)))
    elif name == "t":
        _single_qubit(state, qubits[0], ((1, 0), (0, cmath.exp(1j * math.pi / 4.0))))
    elif name == "tdg":
        _single_qubit(state, qubits[0], ((1, 0), (0, cmath.exp(-1j * math.pi / 4.0))))
    elif name == "ry":
        half = params[0] / 2.0
        cosine, sine = math.cos(half), math.sin(half)
        _single_qubit(state, qubits[0], ((cosine, -sine), (sine, cosine)))
    elif name == "rz":
        half = params[0] / 2.0
        _single_qubit(state, qubits[0], ((cmath.exp(-1j * half), 0), (0, cmath.exp(1j * half))))
    elif name == "cx":
        _cx(state, qubits[0], qubits[1])
    elif name == "cu1":
        _controlled_phase(state, qubits[0], qubits[1], params[0])
    elif name == "swap":
        _swap(state, qubits[0], qubits[1])
    elif name == "ccx":
        _ccx(state, qubits[0], qubits[1], qubits[2])
    else:
        raise SimulationError("unsupported normalized gate: %s" % name)


def _measure(state: List[complex], qubit: int, rng: random.Random) -> int:
    mask = 1 << qubit
    probability_one = sum(abs(amplitude) ** 2 for index, amplitude in enumerate(state) if index & mask)
    probability_one = min(1.0, max(0.0, probability_one))
    outcome = 1 if rng.random() < probability_one else 0
    selected_probability = probability_one if outcome else 1.0 - probability_one
    if selected_probability <= 1e-15:
        outcome = 1 - outcome
        selected_probability = 1.0 - selected_probability
    normalizer = math.sqrt(selected_probability)
    for index in range(len(state)):
        if bool(index & mask) != bool(outcome):
            state[index] = 0j
        else:
            state[index] /= normalizer
    return outcome


def _initial_state(qubit_count: int) -> List[complex]:
    if qubit_count <= 0:
        raise SimulationError("a circuit must declare at least one qubit")
    if qubit_count > MAX_REFERENCE_QUBITS:
        raise SimulationError(
            "reference simulator limit is %d qubits; install a native provider for larger circuits"
            % MAX_REFERENCE_QUBITS
        )
    state = [0j] * (1 << qubit_count)
    state[0] = 1.0 + 0j
    return state


def _bitstring(classical_value: int, width: int) -> str:
    return format(classical_value, "0%db" % width)


def _sample_final_measurements(
    state: Sequence[complex], measurements: Iterable[Any], classical_count: int, shots: int, rng: random.Random
) -> Dict[str, int]:
    cumulative: List[float] = []
    total = 0.0
    for amplitude in state:
        total += abs(amplitude) ** 2
        cumulative.append(total)
    if total <= 0.0:
        raise SimulationError("state vector has zero norm")
    cumulative[-1] = total
    mapping = [measurement_fields(item) for item in measurements]
    counts: Dict[str, int] = {}
    for _ in range(shots):
        basis = bisect.bisect_left(cumulative, rng.random() * total)
        classical_value = 0
        for qubit, cbit in mapping:
            bit = (basis >> qubit) & 1
            if bit:
                classical_value |= 1 << cbit
            else:
                classical_value &= ~(1 << cbit)
        key = _bitstring(classical_value, classical_count)
        counts[key] = counts.get(key, 0) + 1
    return counts


def simulate_counts(circuit: Any, shots: int, seed: int) -> Dict[str, int]:
    """Execute normalized operations and return little-endian classical counts."""
    if not isinstance(shots, int) or isinstance(shots, bool) or not 1 <= shots <= 100_000:
        raise SimulationError("shots must be an integer between 1 and 100000")
    if circuit.classical_count <= 0:
        raise SimulationError("run requires at least one declared classical bit")
    rng = random.Random(seed)
    operations = list(circuit.operations)
    first_measurement = next((index for index, op in enumerate(operations) if is_measurement(op)), len(operations))
    only_final_measurements = all(is_measurement(op) for op in operations[first_measurement:])

    if only_final_measurements:
        state = _initial_state(circuit.qubit_count)
        for operation in operations[:first_measurement]:
            _apply_gate(state, operation)
        return _sample_final_measurements(
            state, operations[first_measurement:], circuit.classical_count, shots, rng
        )

    if circuit.qubit_count > 12:
        raise SimulationError("mid-circuit measurement fallback is limited to 12 qubits")
    counts: Dict[str, int] = {}
    for _ in range(shots):
        state = _initial_state(circuit.qubit_count)
        classical_value = 0
        for operation in operations:
            if is_measurement(operation):
                qubit, cbit = measurement_fields(operation)
                outcome = _measure(state, qubit, rng)
                if outcome:
                    classical_value |= 1 << cbit
                else:
                    classical_value &= ~(1 << cbit)
            else:
                _apply_gate(state, operation)
        key = _bitstring(classical_value, circuit.classical_count)
        counts[key] = counts.get(key, 0) + 1
    return counts
