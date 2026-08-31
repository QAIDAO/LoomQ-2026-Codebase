#!/usr/bin/env python3
"""Zero-dependency exact statevector engine.

Serves three roles:
  1. guaranteed execution path when a native SDK is not installed;
  2. the L2 agent's self-verification oracle (generate -> simulate -> retry);
  3. reference semantics for cross-checking native backends in tests.

Basis convention matches gates.py: amplitude index i, qubit k = (i>>k)&1.
Sampling is an exact multinomial draw over |amplitude|^2 with a seedable RNG,
so runs are reproducible for tests while production calls stay random.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional

try:
    from .gates import GATES
    from .ir import Circuit
except ImportError:
    from gates import GATES
    from ir import Circuit

MAX_QUBITS = 26          # 2**26 amplitudes ~= 512 MiB of complex pairs
_EPS = 1e-9


class SimulationError(ValueError):
    pass


def _validate_qubits(n_qubits: int, qubits: Iterable[int]) -> tuple[int, ...]:
    resolved = tuple(qubits)
    if len(set(resolved)) != len(resolved):
        raise SimulationError("gate acts on the same qubit twice: %r" % (resolved,))
    for q in resolved:
        if not 0 <= q < n_qubits:
            raise SimulationError("qubit index %d out of range (n=%d)" % (q, n_qubits))
    return resolved


@dataclass(frozen=True)
class Statevector:
    """Immutable quantum state; every gate application returns a new instance."""

    amplitudes: tuple[complex, ...]
    n_qubits: int

    @staticmethod
    def zero(n_qubits: int) -> "Statevector":
        if not 1 <= n_qubits <= MAX_QUBITS:
            raise SimulationError(
                "internal engine supports 1..%d qubits, got %d" % (MAX_QUBITS, n_qubits))
        amps = [0j] * (1 << n_qubits)
        amps[0] = 1.0 + 0.0j
        return Statevector(tuple(amps), n_qubits)

    def apply_gate(self, gate: str, params: tuple[float, ...], qubits: tuple[int, ...]) -> "Statevector":
        definition = GATES.get(gate)
        if definition is None:
            raise SimulationError("unknown gate %r" % gate)
        resolved = _validate_qubits(self.n_qubits, qubits)
        matrix = definition.build(params)

        k = len(resolved)
        sub_dim = 1 << k
        masks = [1 << q for q in resolved]

        def subspace_index(pattern: int) -> int:
            # gate matrices are written MSB-first over the listed qubit
            # tuple (textbook style): pattern bit k-1 <-> resolved[0].
            idx = 0
            for pos in range(k):
                if (pattern >> (k - 1 - pos)) & 1:
                    idx |= masks[pos]
            return idx

        old = self.amplitudes
        new = list(old)
        for base in range(1 << self.n_qubits):
            if any(base & m for m in masks):
                continue                       # each involved subspace visited once
            base_idx = base & ~sum(masks)
            gathered = [old[base_idx | subspace_index(col)]
                        for col in range(sub_dim)]
            for row in range(sub_dim):
                acc = 0j
                mrow = matrix[row]
                for col in range(sub_dim):
                    coeff = mrow[col]
                    if abs(coeff) > _EPS:
                        acc += coeff * gathered[col]
                new[base_idx | subspace_index(row)] = acc
        return Statevector(tuple(new), self.n_qubits)

    def probabilities(self) -> tuple[float, ...]:
        probs = [abs(a) ** 2 for a in self.amplitudes]
        total = sum(probs)
        if total <= 0 or abs(total - 1.0) > 1e-6:
            raise SimulationError("state is not normalised (total=%.6f)" % total)
        scale = 1.0 / total
        return [p * scale for p in probs]

    def apply_circuit(self, ops: Iterable[tuple[str, tuple[float, ...], tuple[int, ...]]]) -> "Statevector":
        state = self
        for gate, params, qubits in ops:
            state = state.apply_gate(gate, params, qubits)
        return state


def run_circuit(circuit: Circuit, shots: int,
                rng: Optional[random.Random] = None) -> dict[str, int]:
    """Simulate and sample `circuit`; returns little-endian clbit-keyed counts.

    When the circuit declares no measurement we measure every qubit into
    clbit i implicitly — sampling then still yields a full distribution.
    """
    if shots <= 0:
        raise SimulationError("shots must be positive")
    measures = circuit.measures or [(i, i) for i in range(circuit.n_qubits)]
    state = Statevector.zero(circuit.n_qubits).apply_circuit(circuit.ops)
    probs = state.probabilities()

    outcomes: dict[int, int] = {}
    draw = (rng or random).choices
    for basis_index in draw(range(len(probs)), weights=probs, k=shots):
        outcomes[basis_index] = outcomes.get(basis_index, 0) + 1

    counts: dict[str, int] = {}
    for basis_index, hits in outcomes.items():
        bits = ["0"] * circuit.n_clbits
        for qubit, clbit in measures:
            if (basis_index >> qubit) & 1:
                if clbit >= circuit.n_clbits:
                    raise SimulationError("measure target c[%d] out of range" % clbit)
                bits[clbit] = "1"
        key = "".join(reversed(bits))
        counts[key] = counts.get(key, 0) + hits
    return counts


def circuit_depth(circuit: Circuit) -> int:
    frontier = [0] * max(circuit.n_qubits, 1)
    for _gate, _params, qubits in circuit.ops:
        layer = max(frontier[q] for q in qubits) + 1
        for q in qubits:
            frontier[q] = layer
    return max(frontier)


if __name__ == "__main__":
    bell = Circuit(2, 2,
                   [("h", (), (0,)), ("cx", (), (0, 1))],
                   [(0, 0), (1, 1)])
    print(run_circuit(bell, shots=8192, rng=random.Random(7)))
