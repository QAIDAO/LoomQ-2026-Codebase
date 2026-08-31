"""Deterministic statevector simulator for the competition gate subset."""

import cmath
import math
from typing import Dict, List, Sequence, Tuple

from .model import Circuit, Operation


def simulate_counts(circuit: Circuit, shots: int) -> Dict[str, int]:
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    state = [0j] * (1 << circuit.qubit_count)
    state[0] = 1 + 0j
    for operation in circuit.operations:
        _apply(state, circuit, operation)
    probabilities: Dict[str, float] = {}
    width = circuit.classical_bit_count
    mappings = [
        (circuit.quantum_index(item.qubit), circuit.classical_index(item.classical))
        for item in circuit.measurements
    ]
    for basis, amplitude in enumerate(state):
        probability = amplitude.real * amplitude.real + amplitude.imag * amplitude.imag
        if probability < 1e-16:
            continue
        classical = [0] * width
        for qubit, bit in mappings:
            classical[bit] = (basis >> qubit) & 1
        key = "".join(str(classical[index]) for index in range(width - 1, -1, -1))
        probabilities[key] = probabilities.get(key, 0.0) + probability
    return _allocate(probabilities, shots)


def circuit_depth(circuit: Circuit) -> int:
    levels = [0] * circuit.qubit_count
    for operation in circuit.operations:
        indices = [circuit.quantum_index(bit) for bit in operation.qubits]
        level = 1 + max((levels[index] for index in indices), default=0)
        for index in indices:
            levels[index] = level
    return max(levels, default=0)


def _apply(state: List[complex], circuit: Circuit, operation: Operation) -> None:
    indices = tuple(circuit.quantum_index(bit) for bit in operation.qubits)
    name = operation.name
    theta = operation.parameter
    if name == "h":
        scale = 1 / math.sqrt(2)
        _single(state, indices[0], (scale, scale, scale, -scale))
    elif name == "x":
        _single(state, indices[0], (0, 1, 1, 0))
    elif name == "s":
        _single(state, indices[0], (1, 0, 0, 1j))
    elif name == "sdg":
        _single(state, indices[0], (1, 0, 0, -1j))
    elif name == "t":
        _single(state, indices[0], (1, 0, 0, cmath.exp(1j * math.pi / 4)))
    elif name == "tdg":
        _single(state, indices[0], (1, 0, 0, cmath.exp(-1j * math.pi / 4)))
    elif name == "ry":
        cosine, sine = math.cos(theta / 2), math.sin(theta / 2)
        _single(state, indices[0], (cosine, -sine, sine, cosine))
    elif name == "rz":
        _single(state, indices[0], (cmath.exp(-0.5j * theta), 0, 0, cmath.exp(0.5j * theta)))
    elif name == "cu1":
        control, target = indices
        phase = cmath.exp(1j * theta)
        for basis in range(len(state)):
            if (basis >> control) & 1 and (basis >> target) & 1:
                state[basis] *= phase
    elif name == "cx":
        _permute(state, lambda basis: basis ^ (1 << indices[1]) if (basis >> indices[0]) & 1 else basis)
    elif name == "swap":
        first, second = indices
        _permute(state, lambda basis: _swap_bits(basis, first, second))
    elif name == "ccx":
        first, second, target = indices
        _permute(state, lambda basis: basis ^ (1 << target) if (basis >> first) & 1 and (basis >> second) & 1 else basis)
    else:
        raise ValueError(f"Unsupported operation: {name}")


def _single(state: List[complex], qubit: int, matrix: Sequence[complex]) -> None:
    mask = 1 << qubit
    for zero in range(len(state)):
        if zero & mask:
            continue
        one = zero | mask
        zero_value, one_value = state[zero], state[one]
        state[zero] = matrix[0] * zero_value + matrix[1] * one_value
        state[one] = matrix[2] * zero_value + matrix[3] * one_value


def _permute(state: List[complex], destination) -> None:
    updated = [0j] * len(state)
    for basis, amplitude in enumerate(state):
        updated[destination(basis)] = amplitude
    state[:] = updated


def _swap_bits(basis: int, first: int, second: int) -> int:
    if ((basis >> first) & 1) == ((basis >> second) & 1):
        return basis
    return basis ^ (1 << first) ^ (1 << second)


def _allocate(probabilities: Dict[str, float], shots: int) -> Dict[str, int]:
    total = sum(probabilities.values())
    if total <= 0:
        raise ValueError("Circuit produced no measurable probability")
    exact = {key: value * shots / total for key, value in probabilities.items()}
    counts = {key: int(math.floor(value)) for key, value in exact.items()}
    remaining = shots - sum(counts.values())
    order = sorted(exact, key=lambda key: (exact[key] - counts[key], key), reverse=True)
    for key in order[:remaining]:
        counts[key] += 1
    return {key: value for key, value in sorted(counts.items()) if value > 0}
