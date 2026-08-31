"""Statevector used by the optional quantum RISC-V emulator."""

from __future__ import annotations

import cmath
import math
import random
from typing import Callable, List, Sequence, Tuple

from .isa import MAX_SIMULATED_QUBITS


class QuantumState:
    def __init__(self, qubit_count: int, rng: random.Random):
        if not 1 <= qubit_count <= MAX_SIMULATED_QUBITS:
            raise ValueError(
                f"QINIT supports 1..{MAX_SIMULATED_QUBITS} qubits in the reference emulator"
            )
        self.qubit_count = qubit_count
        self.rng = rng
        self.amplitudes = [0j] * (1 << qubit_count)
        self.amplitudes[0] = 1 + 0j

    def apply(self, mnemonic: str, qubits: Tuple[int, ...], angle: float | None) -> None:
        self._validate_qubits(qubits)
        state = self.amplitudes
        if mnemonic == "qh":
            scale = 1 / math.sqrt(2)
            _single(state, qubits[0], (scale, scale, scale, -scale))
        elif mnemonic == "qx":
            _single(state, qubits[0], (0, 1, 1, 0))
        elif mnemonic == "qs":
            _single(state, qubits[0], (1, 0, 0, 1j))
        elif mnemonic == "qsdg":
            _single(state, qubits[0], (1, 0, 0, -1j))
        elif mnemonic == "qt":
            _single(state, qubits[0], (1, 0, 0, cmath.exp(1j * math.pi / 4)))
        elif mnemonic == "qtdg":
            _single(state, qubits[0], (1, 0, 0, cmath.exp(-1j * math.pi / 4)))
        elif mnemonic == "qry":
            theta = _angle(angle, mnemonic)
            cosine, sine = math.cos(theta / 2), math.sin(theta / 2)
            _single(state, qubits[0], (cosine, -sine, sine, cosine))
        elif mnemonic == "qrz":
            theta = _angle(angle, mnemonic)
            _single(
                state,
                qubits[0],
                (cmath.exp(-0.5j * theta), 0, 0, cmath.exp(0.5j * theta)),
            )
        elif mnemonic == "qcx":
            control, target = qubits
            _permute(
                state,
                lambda basis: basis ^ (1 << target) if (basis >> control) & 1 else basis,
            )
        elif mnemonic == "qcu1":
            theta = _angle(angle, mnemonic)
            control, target = qubits
            phase = cmath.exp(1j * theta)
            for basis in range(len(state)):
                if (basis >> control) & 1 and (basis >> target) & 1:
                    state[basis] *= phase
        elif mnemonic == "qswap":
            first, second = qubits
            _permute(state, lambda basis: _swap_bits(basis, first, second))
        elif mnemonic == "qccx":
            first, second, target = qubits
            _permute(
                state,
                lambda basis: basis ^ (1 << target)
                if (basis >> first) & 1 and (basis >> second) & 1
                else basis,
            )
        else:
            raise ValueError(f"Unsupported quantum state operation: {mnemonic}")

    def measure(self, qubit: int) -> int:
        self._validate_qubits((qubit,))
        probability_one = sum(
            amplitude.real * amplitude.real + amplitude.imag * amplitude.imag
            for basis, amplitude in enumerate(self.amplitudes)
            if (basis >> qubit) & 1
        )
        probability_one = max(0.0, min(1.0, probability_one))
        if probability_one <= 1e-15:
            outcome = 0
        elif probability_one >= 1 - 1e-15:
            outcome = 1
        else:
            outcome = int(self.rng.random() < probability_one)
        probability = probability_one if outcome else 1 - probability_one
        scale = math.sqrt(probability)
        for basis, amplitude in enumerate(self.amplitudes):
            if ((basis >> qubit) & 1) != outcome:
                self.amplitudes[basis] = 0j
            else:
                self.amplitudes[basis] = amplitude / scale
        return outcome

    def _validate_qubits(self, qubits: Tuple[int, ...]) -> None:
        if len(set(qubits)) != len(qubits):
            raise ValueError("Quantum gate operands must be distinct")
        for qubit in qubits:
            if not 0 <= qubit < self.qubit_count:
                raise ValueError(f"Quantum qubit index is outside QINIT range: {qubit}")


def _angle(value: float | None, mnemonic: str) -> float:
    if value is None:
        raise ValueError(f"{mnemonic.upper()} requires QPARAM")
    return value


def _single(state: List[complex], qubit: int, matrix: Sequence[complex]) -> None:
    mask = 1 << qubit
    for zero in range(len(state)):
        if zero & mask:
            continue
        one = zero | mask
        zero_value, one_value = state[zero], state[one]
        state[zero] = matrix[0] * zero_value + matrix[1] * one_value
        state[one] = matrix[2] * zero_value + matrix[3] * one_value


def _permute(state: List[complex], destination: Callable[[int], int]) -> None:
    updated = [0j] * len(state)
    for basis, amplitude in enumerate(state):
        updated[destination(basis)] = amplitude
    state[:] = updated


def _swap_bits(basis: int, first: int, second: int) -> int:
    if ((basis >> first) & 1) == ((basis >> second) & 1):
        return basis
    return basis ^ (1 << first) ^ (1 << second)
