"""Dependency-free statevector simulator used as LoomQ's own verification oracle.

This is not a competition backend. It exists so every transpile path, gate
identity and agent-generated circuit can be checked against exact semantics
without installing any vendor SDK.

Convention: qubit k is bit k of the state index. Result bitstrings follow the
LoomQ little-endian rule, i.e. key = c[n-1]...c[1]c[0].
"""

from __future__ import annotations

import cmath
import math
import random
from typing import Dict, List, Sequence, Tuple

from .circuit import Circuit, GateOp, MeasureOp
from .parse_qasm import parse_qasm

Complex = complex
Matrix2 = Tuple[Complex, Complex, Complex, Complex]  # row-major a, b, c, d

_SQRT1_2 = 1.0 / math.sqrt(2.0)

_STATIC_GATES: Dict[str, Matrix2] = {
    "h": (_SQRT1_2, _SQRT1_2, _SQRT1_2, -_SQRT1_2),
    "x": (0.0, 1.0, 1.0, 0.0),
    "s": (1.0, 0.0, 0.0, 1j),
    "sdg": (1.0, 0.0, 0.0, -1j),
    "t": (1.0, 0.0, 0.0, cmath.exp(1j * math.pi / 4)),
    "tdg": (1.0, 0.0, 0.0, cmath.exp(-1j * math.pi / 4)),
}


def _rz(theta: float) -> Matrix2:
    return (cmath.exp(-0.5j * theta), 0.0, 0.0, cmath.exp(0.5j * theta))


def _ry(theta: float) -> Matrix2:
    c = math.cos(theta / 2.0)
    s = math.sin(theta / 2.0)
    return (c, -s, s, c)


def _u1(theta: float) -> Matrix2:
    return (1.0, 0.0, 0.0, cmath.exp(1j * theta))


class StateVector:
    def __init__(self, n_qubits: int) -> None:
        if n_qubits < 1:
            raise ValueError("n_qubits must be >= 1")
        if n_qubits > 20:
            raise ValueError(f"reference simulator caps at 20 qubits, got {n_qubits}")
        self.n = n_qubits
        self.amps: List[Complex] = [0j] * (1 << n_qubits)
        self.amps[0] = 1.0 + 0j

    def apply_1q(self, matrix: Matrix2, qubit: int) -> None:
        a, b, c, d = matrix
        step = 1 << qubit
        amps = self.amps
        for base in range(0, len(amps), step << 1):
            for offset in range(base, base + step):
                i0 = offset
                i1 = offset + step
                x0 = amps[i0]
                x1 = amps[i1]
                amps[i0] = a * x0 + b * x1
                amps[i1] = c * x0 + d * x1

    def apply_cx(self, control: int, target: int) -> None:
        amps = self.amps
        cmask = 1 << control
        tmask = 1 << target
        for i in range(len(amps)):
            if (i & cmask) and not (i & tmask):
                j = i | tmask
                amps[i], amps[j] = amps[j], amps[i]

    def apply_cphase(self, theta: float, a_qubit: int, b_qubit: int) -> None:
        phase = cmath.exp(1j * theta)
        amask = 1 << a_qubit
        bmask = 1 << b_qubit
        amps = self.amps
        for i in range(len(amps)):
            if (i & amask) and (i & bmask):
                amps[i] *= phase

    def apply_swap(self, a_qubit: int, b_qubit: int) -> None:
        amask = 1 << a_qubit
        bmask = 1 << b_qubit
        amps = self.amps
        for i in range(len(amps)):
            has_a = bool(i & amask)
            has_b = bool(i & bmask)
            if has_a and not has_b:
                j = (i & ~amask) | bmask
                amps[i], amps[j] = amps[j], amps[i]

    def apply_ccx(self, c1: int, c2: int, target: int) -> None:
        m1 = 1 << c1
        m2 = 1 << c2
        tmask = 1 << target
        amps = self.amps
        for i in range(len(amps)):
            if (i & m1) and (i & m2) and not (i & tmask):
                j = i | tmask
                amps[i], amps[j] = amps[j], amps[i]

    def probabilities(self) -> List[float]:
        return [abs(amp) ** 2 for amp in self.amps]


def _apply_gate(state: StateVector, op: GateOp, circuit: Circuit) -> None:
    idx = [circuit.qubit_index(q) for q in op.qubits]
    name = op.name
    if name in _STATIC_GATES:
        state.apply_1q(_STATIC_GATES[name], idx[0])
    elif name == "rz":
        state.apply_1q(_rz(op.params[0]), idx[0])
    elif name == "ry":
        state.apply_1q(_ry(op.params[0]), idx[0])
    elif name == "u1":
        state.apply_1q(_u1(op.params[0]), idx[0])
    elif name == "cx":
        state.apply_cx(idx[0], idx[1])
    elif name == "cu1":
        state.apply_cphase(op.params[0], idx[0], idx[1])
    elif name == "swap":
        state.apply_swap(idx[0], idx[1])
    elif name == "ccx":
        state.apply_ccx(idx[0], idx[1], idx[2])
    else:
        raise ValueError(f"reference simulator does not implement gate '{name}'")


def simulate(circuit: Circuit) -> Tuple[List[float], List[Tuple[int, int]]]:
    """Return (probabilities over qubit basis, [(qubit_index, cbit_index)])."""
    state = StateVector(circuit.n_qubits())
    measured: List[Tuple[int, int]] = []
    for op in circuit.ops:
        if isinstance(op, MeasureOp):
            measured.append(
                (circuit.qubit_index(op.qubit), circuit.cbit_index(op.cbit))
            )
        else:
            _apply_gate(state, op, circuit)
    return state.probabilities(), measured


def ideal_distribution(qasm_str: str) -> Dict[str, float]:
    """Exact measurement distribution, keyed by LoomQ little-endian bitstrings."""
    circuit = parse_qasm(qasm_str)
    probs, measured = simulate(circuit)
    n_bits = circuit.n_clbits() or circuit.n_qubits()
    if not measured:
        measured = [(i, i) for i in range(circuit.n_qubits())]

    dist: Dict[str, float] = {}
    for state_index, prob in enumerate(probs):
        if prob <= 1e-15:
            continue
        bits = ["0"] * n_bits
        for qubit_index, cbit_index in measured:
            value = (state_index >> qubit_index) & 1
            # key position: rightmost char is c[0]
            bits[n_bits - 1 - cbit_index] = str(value)
        key = "".join(bits)
        dist[key] = dist.get(key, 0.0) + prob
    return dist


def sample_counts(qasm_str: str, shots: int, seed: int | None = None) -> Dict[str, int]:
    """Sample shots from the ideal distribution (used for offline regression)."""
    dist = ideal_distribution(qasm_str)
    keys = list(dist)
    weights = [dist[key] for key in keys]
    rng = random.Random(seed)
    counts: Dict[str, int] = {key: 0 for key in keys}
    for _ in range(shots):
        counts[rng.choices(keys, weights=weights, k=1)[0]] += 1
    return {key: value for key, value in counts.items() if value}


def hellinger_fidelity(
    observed: Dict[str, float], expected: Dict[str, float]
) -> float:
    """Same formula as the official evaluator."""
    states = set(observed) | set(expected)
    distance = math.sqrt(
        sum(
            (math.sqrt(observed.get(state, 0.0)) - math.sqrt(expected.get(state, 0.0)))
            ** 2
            for state in states
        )
    ) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - distance))


def counts_fidelity(counts: Dict[str, int], expected: Dict[str, float]) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    observed = {key: value / total for key, value in counts.items()}
    return hellinger_fidelity(observed, expected)
