"""Small deterministic state-vector used only by the Bonus ISA demonstrator."""

from __future__ import annotations

import math
import random
from typing import Dict, Iterable, List, Sequence, Tuple


class QuantumStateError(ValueError):
    """Raised for invalid qubit operands or unsupported simulator sizes."""


class BonusStatevector:
    """A bounded, little-endian state-vector with projective measurement."""

    def __init__(self, *, seed: int = 0, max_qubits: int = 12) -> None:
        if isinstance(max_qubits, bool) or not isinstance(max_qubits, int) or max_qubits < 1:
            raise QuantumStateError("max_qubits must be a positive integer")
        self.max_qubits = max_qubits
        self.num_qubits = 0
        self.amplitudes: List[complex] = [1.0 + 0.0j]
        self._rng = random.Random(seed)

    def _check_qubit(self, qubit: object) -> int:
        if isinstance(qubit, bool) or not isinstance(qubit, int):
            raise QuantumStateError("qubit index from GPR must be an integer")
        if qubit < 0 or qubit >= self.max_qubits:
            raise QuantumStateError(
                f"qubit index {qubit} is outside 0..{self.max_qubits - 1}"
            )
        while self.num_qubits <= qubit:
            self.amplitudes.extend([0.0j] * len(self.amplitudes))
            self.num_qubits += 1
        return qubit

    def initialize(self, num_qubits: object) -> None:
        """Reset the whole quantum state to ``|0...0>`` without reseeding RNG."""

        if isinstance(num_qubits, bool) or not isinstance(num_qubits, int):
            raise QuantumStateError("qinit qubit count from GPR must be an integer")
        if num_qubits < 1 or num_qubits > self.max_qubits:
            raise QuantumStateError(
                f"qinit count {num_qubits} is outside 1..{self.max_qubits}"
            )
        self.num_qubits = num_qubits
        self.amplitudes = [1.0 + 0.0j] + [0.0j] * ((1 << num_qubits) - 1)

    def _single(self, qubit: int, matrix: Sequence[Sequence[complex]]) -> None:
        bit = 1 << qubit
        for base in range(0, len(self.amplitudes), bit << 1):
            for offset in range(bit):
                zero = base + offset
                one = zero + bit
                a0, a1 = self.amplitudes[zero], self.amplitudes[one]
                self.amplitudes[zero] = matrix[0][0] * a0 + matrix[0][1] * a1
                self.amplitudes[one] = matrix[1][0] * a0 + matrix[1][1] * a1

    def apply_single(self, mnemonic: str, qubit: object) -> None:
        q = self._check_qubit(qubit)
        inv_sqrt_2 = 1.0 / math.sqrt(2.0)
        matrices = {
            "qh": ((inv_sqrt_2, inv_sqrt_2), (inv_sqrt_2, -inv_sqrt_2)),
            "qx": ((0.0, 1.0), (1.0, 0.0)),
            "qs": ((1.0, 0.0), (0.0, 1.0j)),
            "qt": ((1.0, 0.0), (0.0, complex(inv_sqrt_2, inv_sqrt_2))),
        }
        try:
            matrix = matrices[mnemonic]
        except KeyError as exc:
            raise QuantumStateError(f"unsupported single-qubit gate: {mnemonic}") from exc
        self._single(q, matrix)

    def apply_rotation(self, mnemonic: str, qubit: object, angle: object) -> None:
        q = self._check_qubit(qubit)
        if isinstance(angle, bool) or not isinstance(angle, (int, float)):
            raise QuantumStateError("rotation angle must be a finite number")
        theta = float(angle)
        if not math.isfinite(theta):
            raise QuantumStateError("rotation angle must be a finite number")
        half = theta / 2.0
        if mnemonic == "qry":
            cosine, sine = math.cos(half), math.sin(half)
            matrix = ((cosine, -sine), (sine, cosine))
        elif mnemonic == "qrz":
            negative = complex(math.cos(-half), math.sin(-half))
            positive = complex(math.cos(half), math.sin(half))
            matrix = ((negative, 0.0), (0.0, positive))
        else:
            raise QuantumStateError(f"unsupported rotation gate: {mnemonic}")
        self._single(q, matrix)

    def apply_double(self, mnemonic: str, first: object, second: object) -> None:
        q0, q1 = self._check_qubit(first), self._check_qubit(second)
        if q0 == q1:
            raise QuantumStateError(f"{mnemonic} requires two distinct qubits")
        bit0, bit1 = 1 << q0, 1 << q1
        if mnemonic == "qcx":
            for index in range(len(self.amplitudes)):
                if index & bit0 and not index & bit1:
                    partner = index | bit1
                    self.amplitudes[index], self.amplitudes[partner] = (
                        self.amplitudes[partner],
                        self.amplitudes[index],
                    )
            return
        if mnemonic == "qswap":
            for index in range(len(self.amplitudes)):
                if not index & bit0 and index & bit1:
                    partner = (index | bit0) & ~bit1
                    self.amplitudes[index], self.amplitudes[partner] = (
                        self.amplitudes[partner],
                        self.amplitudes[index],
                    )
            return
        raise QuantumStateError(f"unsupported two-qubit gate: {mnemonic}")

    def apply_triple(
        self, mnemonic: str, first: object, second: object, third: object
    ) -> None:
        q0 = self._check_qubit(first)
        q1 = self._check_qubit(second)
        q2 = self._check_qubit(third)
        if len({q0, q1, q2}) != 3:
            raise QuantumStateError(f"{mnemonic} requires three distinct qubits")
        if mnemonic != "qccx":
            raise QuantumStateError(f"unsupported three-qubit gate: {mnemonic}")
        bit0, bit1, target = 1 << q0, 1 << q1, 1 << q2
        for index in range(len(self.amplitudes)):
            if index & bit0 and index & bit1 and not index & target:
                partner = index | target
                self.amplitudes[index], self.amplitudes[partner] = (
                    self.amplitudes[partner],
                    self.amplitudes[index],
                )

    def measure(self, qubit: object) -> int:
        q = self._check_qubit(qubit)
        bit = 1 << q
        probability_one = sum(
            abs(amplitude) ** 2
            for index, amplitude in enumerate(self.amplitudes)
            if index & bit
        )
        probability_one = min(1.0, max(0.0, probability_one))
        result = 1 if self._rng.random() < probability_one else 0
        probability_result = probability_one if result else 1.0 - probability_one
        if probability_result <= 1e-15:
            result = 1 - result
            probability_result = 1.0 - probability_result
        inverse_norm = 1.0 / math.sqrt(probability_result)
        for index, amplitude in enumerate(self.amplitudes):
            if bool(index & bit) == bool(result):
                self.amplitudes[index] = amplitude * inverse_norm
            else:
                self.amplitudes[index] = 0.0j
        return result

    def probabilities(self, *, tolerance: float = 1e-12) -> Dict[str, float]:
        """Return non-negligible basis probabilities, highest qubit on the left."""

        width = max(1, self.num_qubits)
        output: Dict[str, float] = {}
        for index, amplitude in enumerate(self.amplitudes):
            probability = abs(amplitude) ** 2
            if probability > tolerance:
                output[format(index, f"0{width}b")] = probability
        return output
