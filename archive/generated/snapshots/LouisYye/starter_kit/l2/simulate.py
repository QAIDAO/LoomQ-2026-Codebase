from __future__ import annotations

import math
from typing import Any

import numpy as np


def _single(state, n, qubit, matrix):
    step = 1 << qubit
    for base in range(0, 1 << n, step * 2):
        for offset in range(step):
            a, b = base + offset, base + offset + step
            va, vb = state[a], state[b]
            state[a] = matrix[0, 0] * va + matrix[0, 1] * vb
            state[b] = matrix[1, 0] * va + matrix[1, 1] * vb


def _controlled_phase(state, control, target, phase):
    mask = (1 << control) | (1 << target)
    for index in range(len(state)):
        if index & mask == mask:
            state[index] *= phase


def _permutation(state, transform):
    output = np.zeros_like(state)
    for index, value in enumerate(state):
        output[transform(index)] += value
    state[:] = output


def simulate(circuit: Any) -> dict[str, float]:
    n = circuit.num_qubits
    state = np.zeros(1 << n, dtype=np.complex128)
    state[0] = 1.0
    one = np.array([[1, 0], [0, 1]], dtype=np.complex128)
    matrices = {
        "h": np.array([[1, 1], [1, -1]], dtype=np.complex128) / math.sqrt(2),
        "x": np.array([[0, 1], [1, 0]], dtype=np.complex128),
        "s": np.array([[1, 0], [0, 1j]], dtype=np.complex128),
        "sdg": np.array([[1, 0], [0, -1j]], dtype=np.complex128),
        "t": np.array([[1, 0], [0, np.exp(1j * math.pi / 4)]], dtype=np.complex128),
        "tdg": np.array([[1, 0], [0, np.exp(-1j * math.pi / 4)]], dtype=np.complex128),
    }
    for gate in circuit.gates:
        name, q = gate.name, gate.qubits
        if name in matrices:
            _single(state, n, q[0], matrices[name])
        elif name in {"ry", "rz"}:
            theta = gate.params[0]
            if name == "ry":
                matrix = np.array(
                    [[math.cos(theta / 2), -math.sin(theta / 2)],
                     [math.sin(theta / 2), math.cos(theta / 2)]], dtype=np.complex128
                )
            else:
                matrix = np.array(
                    [[np.exp(-1j * theta / 2), 0], [0, np.exp(1j * theta / 2)]],
                    dtype=np.complex128,
                )
            _single(state, n, q[0], matrix)
        elif name == "cx":
            c, t = q
            _permutation(state, lambda i, c=c, t=t: i ^ (1 << t) if i & (1 << c) else i)
        elif name == "swap":
            a, b = q
            def swap_index(i, a=a, b=b):
                return i ^ ((1 << a) | (1 << b)) if bool(i & (1 << a)) != bool(i & (1 << b)) else i
            _permutation(state, swap_index)
        elif name == "ccx":
            a, b, t = q
            _permutation(state, lambda i, a=a, b=b, t=t: i ^ (1 << t) if i & (1 << a) and i & (1 << b) else i)
        elif name == "cu1":
            _controlled_phase(state, q[0], q[1], np.exp(1j * gate.params[0]))
        else:
            _single(state, n, q[0], one)

    distribution: dict[str, float] = {}
    measurements = circuit.measurements or [
        type("M", (), {"qubit": q, "bit": q})() for q in range(circuit.num_bits)
    ]
    for index, amplitude in enumerate(state):
        probability = float(abs(amplitude) ** 2)
        if probability < 1e-12:
            continue
        bits = ["0"] * circuit.num_bits
        for measurement in measurements:
            bits[measurement.bit] = "1" if index & (1 << measurement.qubit) else "0"
        key = "".join(reversed(bits))
        distribution[key] = distribution.get(key, 0.0) + probability
    return distribution

