"""Small independent statevector oracle for verification and regression tests."""

from __future__ import annotations

import bisect
import cmath
import math
import random

from .compiler.ir import Circuit, Gate
from .compiler.validator import validate_circuit


MAX_REFERENCE_QUBITS = 16
_EPSILON = 1e-15


class SimulationError(RuntimeError):
    """Raised when a circuit cannot be simulated within the local guardrails."""


def _apply_single(
    state: list[complex],
    qubit: int,
    matrix: tuple[tuple[complex, complex], tuple[complex, complex]],
) -> None:
    mask = 1 << qubit
    for lower in range(len(state)):
        if lower & mask:
            continue
        upper = lower | mask
        zero = state[lower]
        one = state[upper]
        state[lower] = matrix[0][0] * zero + matrix[0][1] * one
        state[upper] = matrix[1][0] * zero + matrix[1][1] * one


def _single_matrix(gate: Gate) -> tuple[tuple[complex, complex], tuple[complex, complex]]:
    inverse_root_two = 1 / math.sqrt(2)
    if gate.name == "h":
        return ((inverse_root_two, inverse_root_two), (inverse_root_two, -inverse_root_two))
    if gate.name == "x":
        return ((0, 1), (1, 0))
    if gate.name == "s":
        return ((1, 0), (0, 1j))
    if gate.name == "sdg":
        return ((1, 0), (0, -1j))
    if gate.name == "t":
        return ((1, 0), (0, cmath.exp(1j * math.pi / 4)))
    if gate.name == "tdg":
        return ((1, 0), (0, cmath.exp(-1j * math.pi / 4)))
    if gate.name == "rz":
        theta = gate.params[0]
        return ((cmath.exp(-0.5j * theta), 0), (0, cmath.exp(0.5j * theta)))
    if gate.name == "ry":
        half = gate.params[0] / 2
        return ((math.cos(half), -math.sin(half)), (math.sin(half), math.cos(half)))
    raise SimulationError(f"no single-qubit matrix for gate `{gate.name}`")


def _apply_gate(state: list[complex], gate: Gate) -> None:
    if len(gate.qubits) == 1:
        _apply_single(state, gate.qubits[0], _single_matrix(gate))
        return

    if gate.name == "cx":
        control_mask = 1 << gate.qubits[0]
        target_mask = 1 << gate.qubits[1]
        for index in range(len(state)):
            if index & control_mask and not index & target_mask:
                partner = index | target_mask
                state[index], state[partner] = state[partner], state[index]
        return

    if gate.name == "cu1":
        both = (1 << gate.qubits[0]) | (1 << gate.qubits[1])
        phase = cmath.exp(1j * gate.params[0])
        for index in range(len(state)):
            if index & both == both:
                state[index] *= phase
        return

    if gate.name == "swap":
        first_mask = 1 << gate.qubits[0]
        second_mask = 1 << gate.qubits[1]
        toggle = first_mask | second_mask
        for index in range(len(state)):
            if not index & first_mask and index & second_mask:
                partner = index ^ toggle
                state[index], state[partner] = state[partner], state[index]
        return

    if gate.name == "ccx":
        controls = (1 << gate.qubits[0]) | (1 << gate.qubits[1])
        target = 1 << gate.qubits[2]
        for index in range(len(state)):
            if index & controls == controls and not index & target:
                partner = index | target
                state[index], state[partner] = state[partner], state[index]
        return

    raise SimulationError(f"unsupported gate `{gate.name}`")


def _statevector(circuit: Circuit) -> list[complex]:
    validate_circuit(circuit)
    if circuit.qubit_count > MAX_REFERENCE_QUBITS:
        raise SimulationError(
            f"reference simulator supports at most {MAX_REFERENCE_QUBITS} qubits"
        )
    state = [0j] * (1 << circuit.qubit_count)
    state[0] = 1 + 0j
    for gate in circuit.gates:
        _apply_gate(state, gate)
    return state


def probabilities(circuit: Circuit) -> dict[str, float]:
    """Return the exact final classical distribution for a validated circuit."""

    state = _statevector(circuit)
    distribution: dict[str, float] = {}
    for basis, amplitude in enumerate(state):
        probability = abs(amplitude) ** 2
        if probability <= _EPSILON:
            continue
        classical_value = 0
        for measurement in circuit.measurements:
            if basis & (1 << measurement.qubit):
                classical_value |= 1 << measurement.cbit
        key = f"{classical_value:0{circuit.cbit_count}b}"
        distribution[key] = distribution.get(key, 0.0) + probability
    total = sum(distribution.values())
    if total <= 0:
        raise SimulationError("simulation produced no measurable probability")
    return {key: value / total for key, value in sorted(distribution.items())}


def sample(circuit: Circuit, shots: int, *, seed: int | None = None) -> dict[str, int]:
    """Sample the exact reference distribution with a reproducible optional seed."""

    if isinstance(shots, bool) or not isinstance(shots, int) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    distribution = probabilities(circuit)
    states = list(distribution)
    cumulative: list[float] = []
    running = 0.0
    for state in states:
        running += distribution[state]
        cumulative.append(running)
    cumulative[-1] = 1.0

    generator = random.Random(seed)
    counts: dict[str, int] = {}
    for _ in range(shots):
        index = bisect.bisect_left(cumulative, generator.random())
        state = states[min(index, len(states) - 1)]
        counts[state] = counts.get(state, 0) + 1
    return dict(sorted(counts.items()))
