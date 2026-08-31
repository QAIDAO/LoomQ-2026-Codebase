"""Zero-dependency state-vector simulator for the LoomQ 12-gate whitelist.

Amplitudes are indexed with Qiskit's convention: index bit ``k`` is the
state of qubit ``k``. Measurement aggregates outcome probabilities per
classical-register key once (O(2^n)), then samples with bisect on the
cumulative distribution - so 8192 shots cost O(keys log keys), not
O(shots * 2^n).

Counts keys follow the LoomQ bit-order contract: the rightmost character
is c[0] (little-endian, Qiskit convention).
"""

import bisect
import cmath
import math
import random
from typing import Dict, List

try:
    from .circuit_ir import Circuit, GateOp
except ImportError:  # standalone-module fallback (evaluator imports by path)
    from circuit_ir import Circuit, GateOp

_SQRT2 = math.sqrt(2.0)
_PHASE_S = cmath.exp(1j * math.pi / 2)     # s
_PHASE_T = cmath.exp(1j * math.pi / 4)     # t

# Single-qubit 2x2 matrices.
_GATES: Dict[str, List[List[complex]]] = {
    "h": [[1 / _SQRT2, 1 / _SQRT2], [1 / _SQRT2, -1 / _SQRT2]],
    "x": [[0, 1], [1, 0]],
}


def _apply_single(sv: List[complex], n: int, k: int, mat: List[List[complex]]) -> None:
    """Apply a 2x2 unitary to qubit ``k`` in place."""
    m00, m01, m10, m11 = mat[0][0], mat[0][1], mat[1][0], mat[1][1]
    step = 1 << k
    span = step << 1
    for base in range(0, 1 << n, span):
        for i in range(base, base + step):
            j = i + step
            a, b = sv[i], sv[j]
            sv[i] = m00 * a + m01 * b
            sv[j] = m10 * a + m11 * b


def _apply_diagonal(sv: List[complex], n: int, k: int, phase0: complex, phase1: complex) -> None:
    """Apply diag(phase0, phase1) to qubit ``k`` in place."""
    step = 1 << k
    span = step << 1
    for base in range(0, 1 << n, span):
        for i in range(base, base + step):
            j = i + step
            sv[i] *= phase0
            sv[j] *= phase1


def _apply_cx(sv: List[complex], n: int, ctrl: int, tgt: int) -> None:
    """Controlled-X: swap (ctrl=1, tgt=0) <-> (ctrl=1, tgt=1) amplitudes."""
    step_t = 1 << tgt
    mask_c = 1 << ctrl
    for i in range(1 << n):
        if (i & mask_c) and not (i & step_t):
            j = i | step_t
            sv[i], sv[j] = sv[j], sv[i]


def _apply_ccx(sv: List[complex], n: int, c1: int, c2: int, tgt: int) -> None:
    """Toffoli: flip target when both controls are 1."""
    mask = (1 << c1) | (1 << c2)
    step_t = 1 << tgt
    for i in range(1 << n):
        if (i & mask) == mask and not (i & step_t):
            j = i | step_t
            sv[i], sv[j] = sv[j], sv[i]


def _apply_swap(sv: List[complex], n: int, a: int, b: int) -> None:
    """Swap qubits a and b by exchanging amplitude pairs."""
    step_a, step_b = 1 << a, 1 << b
    for i in range(1 << n):
        if (i & step_a) and not (i & step_b):
            j = (i ^ step_a) | step_b
            sv[i], sv[j] = sv[j], sv[i]


def _apply_cu1(sv: List[complex], n: int, ctrl: int, tgt: int, theta: float) -> None:
    """Controlled phase: multiply amplitudes with both bits set by e^{i*theta}."""
    mask = (1 << ctrl) | (1 << tgt)
    phase = cmath.exp(1j * theta)
    for i in range(1 << n):
        if (i & mask) == mask:
            sv[i] *= phase


def _apply_gate(sv: List[complex], n: int, op: GateOp) -> None:
    name = op.name
    if name == "h" or name == "x":
        _apply_single(sv, n, op.qubits[0], _GATES[name])
    elif name == "s":
        _apply_diagonal(sv, n, op.qubits[0], 1.0, _PHASE_S)
    elif name == "sdg":
        _apply_diagonal(sv, n, op.qubits[0], 1.0, _PHASE_S.conjugate())
    elif name == "t":
        _apply_diagonal(sv, n, op.qubits[0], 1.0, _PHASE_T)
    elif name == "tdg":
        _apply_diagonal(sv, n, op.qubits[0], 1.0, _PHASE_T.conjugate())
    elif name == "rz":
        theta = op.params[0]
        _apply_diagonal(
            sv, n, op.qubits[0],
            cmath.exp(-0.5j * theta), cmath.exp(0.5j * theta),
        )
    elif name == "ry":
        theta = op.params[0]
        half = theta / 2.0
        c, s = math.cos(half), math.sin(half)
        _apply_single(sv, n, op.qubits[0], [[c, -s], [s, c]])
    elif name == "u1":
        theta = op.params[0]
        _apply_diagonal(sv, n, op.qubits[0], 1.0, cmath.exp(1j * theta))
    elif name == "cx":
        _apply_cx(sv, n, op.qubits[0], op.qubits[1])
    elif name == "cu1":
        _apply_cu1(sv, n, op.qubits[0], op.qubits[1], op.params[0])
    elif name == "swap":
        _apply_swap(sv, n, op.qubits[0], op.qubits[1])
    elif name == "ccx":
        _apply_ccx(sv, n, op.qubits[0], op.qubits[1], op.qubits[2])
    else:
        raise ValueError("simulator cannot apply gate %r" % name)


def simulate(circuit: Circuit, shots: int, seed: int = 0) -> Dict[str, int]:
    """Run the circuit on the zero state and return little-endian counts."""
    dim = 1 << circuit.num_qubits
    sv = [0j] * dim
    sv[0] = 1.0 + 0j
    for op in circuit.ops:
        _apply_gate(sv, circuit.num_qubits, op)

    # Aggregate outcome probabilities per creg key in one pass.
    probs: Dict[int, float] = {}
    for idx, amp in enumerate(sv):
        prob = (amp.conjugate() * amp).real
        if prob == 0.0:
            continue
        key = 0
        for qubit, cbit in circuit.measures:
            if (idx >> qubit) & 1:
                key |= 1 << cbit
        probs[key] = probs.get(key, 0.0) + prob

    keys = sorted(probs)
    cum: List[float] = []
    acc = 0.0
    for k in keys:
        acc += probs[k]
        cum.append(acc)
    total = acc
    if total <= 0.0:
        raise ValueError("circuit yields zero total probability")

    width = max(1, circuit.num_cbits)
    counts = {format(k, "0%db" % width): 0 for k in keys}
    rng = random.Random(seed)
    for _ in range(shots):
        pick = rng.random() * total
        counts[format(keys[bisect.bisect_left(cum, pick)], "0%db" % width)] += 1
    return counts
