"""Dependency-free statevector simulator for the LoomQ gate whitelist.

Qubit k is bit k of the state index (little-endian), matching the contest's
counts convention: the rightmost character of a counts key is c[0].

This is the reference executor used by ``run()``: the transpiled target IR is
parsed back and executed here, so every ``run()`` call also exercises the
transpiler end to end.
"""

from __future__ import annotations

import cmath
import math
import random
from typing import Dict, List, Tuple

from .qasm import Circuit, Gate


_SQRT1_2 = 1.0 / math.sqrt(2.0)


def _single_qubit_matrix(gate: Gate) -> List[List[complex]]:
    name = gate.name
    if name == "h":
        return [[_SQRT1_2, _SQRT1_2], [_SQRT1_2, -_SQRT1_2]]
    if name == "x":
        return [[0, 1], [1, 0]]
    if name == "s":
        return [[1, 0], [0, 1j]]
    if name == "sdg":
        return [[1, 0], [0, -1j]]
    if name == "t":
        return [[1, 0], [0, cmath.exp(1j * math.pi / 4)]]
    if name == "tdg":
        return [[1, 0], [0, cmath.exp(-1j * math.pi / 4)]]
    if name in ("u1", "p"):
        return [[1, 0], [0, cmath.exp(1j * gate.params[0])]]
    if name == "rz":
        theta = gate.params[0]
        return [
            [cmath.exp(-0.5j * theta), 0],
            [0, cmath.exp(0.5j * theta)],
        ]
    if name == "ry":
        theta = gate.params[0]
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        return [[c, -s], [s, c]]
    raise ValueError("not a single-qubit gate: %s" % name)


def _apply_single(state: List[complex], num_qubits: int, matrix, target: int) -> None:
    step = 1 << target
    size = 1 << num_qubits
    m00, m01 = matrix[0]
    m10, m11 = matrix[1]
    for base in range(0, size, step << 1):
        for off in range(base, base + step):
            i0 = off
            i1 = off | step
            a0, a1 = state[i0], state[i1]
            state[i0] = m00 * a0 + m01 * a1
            state[i1] = m10 * a0 + m11 * a1


def _apply_controlled_single(
    state: List[complex], num_qubits: int, matrix, control: int, target: int
) -> None:
    cstep = 1 << control
    tstep = 1 << target
    size = 1 << num_qubits
    m00, m01 = matrix[0]
    m10, m11 = matrix[1]
    for i in range(size):
        if (i & cstep) and not (i & tstep):
            j = i | tstep
            a0, a1 = state[i], state[j]
            state[i] = m00 * a0 + m01 * a1
            state[j] = m10 * a0 + m11 * a1


def _apply_cu1(state: List[complex], num_qubits: int, theta: float, control: int, target: int) -> None:
    phase = cmath.exp(1j * theta)
    cstep = 1 << control
    tstep = 1 << target
    size = 1 << num_qubits
    for i in range(size):
        if (i & cstep) and (i & tstep):
            state[i] *= phase


def _apply_swap(state: List[complex], num_qubits: int, a: int, b: int) -> None:
    if a == b:
        return
    sa = 1 << a
    sb = 1 << b
    size = 1 << num_qubits
    for i in range(size):
        ba = 1 if (i & sa) else 0
        bb = 1 if (i & sb) else 0
        if ba == 0 and bb == 1:
            j = (i | sa) & ~sb
            state[i], state[j] = state[j], state[i]


def _apply_ccx(state: List[complex], num_qubits: int, c1: int, c2: int, target: int) -> None:
    m1 = 1 << c1
    m2 = 1 << c2
    mt = 1 << target
    size = 1 << num_qubits
    for i in range(size):
        if (i & m1) and (i & m2) and not (i & mt):
            j = i | mt
            state[i], state[j] = state[j], state[i]


def statevector(circuit: Circuit) -> List[complex]:
    """Compute the final statevector of a circuit (before measurement)."""
    if circuit.num_qubits > 20:
        raise ValueError("circuit too large for the built-in simulator (>20 qubits)")
    size = 1 << circuit.num_qubits
    state = [0j] * size
    state[0] = 1.0 + 0j
    for gate in circuit.gates:
        name = gate.name
        if name in ("h", "x", "s", "sdg", "t", "tdg", "u1", "p", "rz", "ry"):
            _apply_single(state, circuit.num_qubits, _single_qubit_matrix(gate), gate.qubits[0])
        elif name == "cx":
            _apply_controlled_single(
                state, circuit.num_qubits, [[0, 1], [1, 0]], gate.qubits[0], gate.qubits[1]
            )
        elif name == "cu1":
            _apply_cu1(state, circuit.num_qubits, gate.params[0], gate.qubits[0], gate.qubits[1])
        elif name == "swap":
            _apply_swap(state, circuit.num_qubits, gate.qubits[0], gate.qubits[1])
        elif name == "ccx":
            _apply_ccx(state, circuit.num_qubits, gate.qubits[0], gate.qubits[1], gate.qubits[2])
        else:
            raise ValueError("unsupported gate in simulator: %s" % name)
    return state


def simulate_counts(
    circuit: Circuit, shots: int, rng: random.Random | None = None
) -> Dict[str, int]:
    """Sample measurement outcomes and return counts with little-endian keys.

    The key's rightmost character is c[0] (Qiskit convention), as required by
    the contest's unified result schema.
    """
    if shots <= 0:
        raise ValueError("shots must be positive")
    rng = rng or random.Random()
    state = statevector(circuit)
    size = len(state)
    probs = [abs(a) ** 2 for a in state]

    # Build cumulative distribution once, then draw `shots` samples.
    cumulative: List[float] = []
    acc = 0.0
    for p in probs:
        acc += p
        cumulative.append(acc)
    cumulative[-1] = 1.0  # guard against float drift

    if circuit.measurements:
        measured = circuit.measurements
        # Explicit measurements: key width = classical register width
        # (key = c[n-1]...c[0]), exactly as the contest schema requires.
        num_clbits = circuit.num_clbits
    else:
        # No explicit measurement: read out every qubit into a same-size register.
        measured = [(k, k) for k in range(circuit.num_qubits)]
        num_clbits = max(circuit.num_clbits, circuit.num_qubits)

    counts: Dict[str, int] = {}
    import bisect

    for _ in range(shots):
        outcome = bisect.bisect_left(cumulative, rng.random())
        if outcome >= size:
            outcome = size - 1
        bits = ["0"] * num_clbits
        for qubit, clbit in measured:
            if (outcome >> qubit) & 1:
                # rightmost character is c[0]
                bits[num_clbits - 1 - clbit] = "1"
        key = "".join(bits)
        counts[key] = counts.get(key, 0) + 1
    return counts
