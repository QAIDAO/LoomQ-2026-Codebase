"""Fork-compatible extension of the official TinyRISCVEmulator.

The original emulator remains untouched. This subclass reuses its loader and
register helpers, then adds the custom quantum instructions defined in SPEC.md.
"""

from __future__ import annotations

import cmath
import math
import random
from typing import Dict, Iterable, List, Tuple

from .encoding import decode_word, instruction_to_assembly

try:
    from ..riscv_emulator import TinyRISCVEmulator
except ImportError:
    from riscv_emulator import TinyRISCVEmulator


class QuantumRISCVEmulator(TinyRISCVEmulator):
    """Execute the official classical subset plus LoomQ quantum instructions."""

    QUANTUM_OPS = {
        "qinit",
        "qparam",
        "qx",
        "qh",
        "qs",
        "qsdg",
        "qt",
        "qtdg",
        "qrz",
        "qry",
        "qcx",
        "qcu1",
        "qswap",
        "qccx",
        "qmeasure",
    }

    def __init__(self, seed: int = 0, max_qubits: int = 12) -> None:
        super().__init__()
        if max_qubits < 1 or max_qubits > 31:
            raise ValueError("max_qubits must be in 1..31")
        self.max_qubits = max_qubits
        self._random = random.Random(seed)
        self._reset_quantum_runtime()

    def load_program(self, asm_code: str) -> None:
        super().load_program(asm_code)
        self._reset_quantum_runtime()

    def load_words(
        self, quantum_words: Iterable[int], classical_assembly: str = ""
    ) -> None:
        """Decode custom machine words, then append official classical text."""
        quantum_lines = [
            instruction_to_assembly(decode_word(word)) for word in quantum_words
        ]
        source = "\n".join(quantum_lines)
        if classical_assembly.strip():
            source += "\n" + classical_assembly
        self.load_program(source)

    def execute(self) -> Dict[str, int]:
        steps = 0
        num_instr = len(self.instructions)

        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("program exceeded maximum step count")

            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1

            if op == "li":
                self._expect_args(op, args, 2)
                self.set_register(args[0], int(args[1]))
            elif op == "add":
                self._expect_args(op, args, 3)
                self.set_register(
                    args[0],
                    self.get_register(args[1]) + self.get_register(args[2]),
                )
            elif op == "sub":
                self._expect_args(op, args, 3)
                self.set_register(
                    args[0],
                    self.get_register(args[1]) - self.get_register(args[2]),
                )
            elif op == "addi":
                self._expect_args(op, args, 3)
                self.set_register(
                    args[0], self.get_register(args[1]) + int(args[2])
                )
            elif op in {"beq", "bne"}:
                self._expect_args(op, args, 3)
                left = self.get_register(args[0])
                right = self.get_register(args[1])
                should_jump = left == right if op == "beq" else left != right
                if should_jump:
                    next_pc = self._label_pc(args[2])
            elif op == "j":
                self._expect_args(op, args, 1)
                next_pc = self._label_pc(args[0])
            elif op in self.QUANTUM_OPS:
                self._execute_quantum(op, args)
            else:
                raise ValueError("unsupported instruction operation: %s" % op)

            self.pc = next_pc

        return {
            "x%d" % index: value
            for index, value in enumerate(self.registers)
            if value != 0
        }

    def run_shots(self, shots: int, classical_bit_count: int) -> Dict[str, int]:
        """Repeat a loaded hybrid program and return c[n-1]...c[0] counts."""
        if shots <= 0:
            raise ValueError("shots must be positive")
        if classical_bit_count < 1 or classical_bit_count > 22:
            raise ValueError("classical_bit_count must be in 1..22")

        counts: Dict[str, int] = {}
        for _ in range(shots):
            self._reset_execution_runtime()
            self.execute()
            key = "".join(
                str(self.get_register("x%d" % (10 + index)))
                for index in reversed(range(classical_bit_count))
            )
            counts[key] = counts.get(key, 0) + 1
        return counts

    @property
    def quantum_state(self) -> Tuple[complex, ...]:
        return tuple(self._state)

    @property
    def measurement_log(self) -> Tuple[Tuple[int, int, int], ...]:
        return tuple(self._measurement_log)

    def _execute_quantum(self, op: str, args: List[str]) -> None:
        if op == "qinit":
            self._expect_args(op, args, 1)
            self._initialize_qubits(int(args[0]))
            return
        if op == "qparam":
            self._expect_args(op, args, 1)
            self._parameter = float(args[0])
            return

        self._require_initialized()
        if op in {"qx", "qh", "qs", "qsdg", "qt", "qtdg", "qrz", "qry"}:
            self._expect_args(op, args, 1)
            qubit = self._parse_qubit(args[0])
            self._apply_single(op, qubit)
            return
        if op in {"qcx", "qcu1", "qswap"}:
            self._expect_args(op, args, 2)
            q0, q1 = self._distinct_qubits(args)
            if op == "qcx":
                self._apply_cx(q0, q1)
            elif op == "qcu1":
                self._apply_cu1(q0, q1)
            else:
                self._apply_swap(q0, q1)
            return
        if op == "qccx":
            self._expect_args(op, args, 3)
            q0, q1, q2 = self._distinct_qubits(args)
            self._apply_ccx(q0, q1, q2)
            return
        if op == "qmeasure":
            self._expect_args(op, args, 2)
            qubit = self._parse_qubit(args[0])
            destination = self._parse_reg_idx(args[1])
            if destination < 10:
                raise ValueError("qmeasure destination must be x10..x31")
            value = self._measure(qubit)
            self.set_register("x%d" % destination, value)
            self._measurement_log.append((qubit, destination, value))
            return
        raise ValueError("unsupported quantum instruction: %s" % op)

    def _apply_single(self, op: str, qubit: int) -> None:
        parameter = self._parameter
        if op in {"qrz", "qry"} and parameter is None:
            raise ValueError("%s requires a preceding qparam" % op)

        if op == "qx":
            matrix = ((0, 1), (1, 0))
        elif op == "qh":
            factor = 1.0 / math.sqrt(2.0)
            matrix = ((factor, factor), (factor, -factor))
        elif op == "qs":
            matrix = ((1, 0), (0, 1j))
        elif op == "qsdg":
            matrix = ((1, 0), (0, -1j))
        elif op == "qt":
            matrix = ((1, 0), (0, cmath.exp(1j * math.pi / 4.0)))
        elif op == "qtdg":
            matrix = ((1, 0), (0, cmath.exp(-1j * math.pi / 4.0)))
        elif op == "qrz":
            matrix = (
                (cmath.exp(-0.5j * parameter), 0),
                (0, cmath.exp(0.5j * parameter)),
            )
        elif op == "qry":
            cosine = math.cos(parameter / 2.0)
            sine = math.sin(parameter / 2.0)
            matrix = ((cosine, -sine), (sine, cosine))
        else:
            raise ValueError("unsupported single-qubit instruction: %s" % op)

        mask = 1 << qubit
        for index in range(len(self._state)):
            if index & mask:
                continue
            paired = index | mask
            zero = self._state[index]
            one = self._state[paired]
            self._state[index] = matrix[0][0] * zero + matrix[0][1] * one
            self._state[paired] = matrix[1][0] * zero + matrix[1][1] * one

    def _apply_cx(self, control: int, target: int) -> None:
        control_mask = 1 << control
        target_mask = 1 << target
        for index in range(len(self._state)):
            if index & control_mask and not index & target_mask:
                paired = index | target_mask
                self._state[index], self._state[paired] = (
                    self._state[paired],
                    self._state[index],
                )

    def _apply_cu1(self, control: int, target: int) -> None:
        if self._parameter is None:
            raise ValueError("qcu1 requires a preceding qparam")
        phase = cmath.exp(1j * self._parameter)
        control_mask = 1 << control
        target_mask = 1 << target
        for index in range(len(self._state)):
            if index & control_mask and index & target_mask:
                self._state[index] *= phase

    def _apply_swap(self, first: int, second: int) -> None:
        first_mask = 1 << first
        second_mask = 1 << second
        for index in range(len(self._state)):
            if not index & first_mask and index & second_mask:
                paired = (index | first_mask) & ~second_mask
                self._state[index], self._state[paired] = (
                    self._state[paired],
                    self._state[index],
                )

    def _apply_ccx(self, first: int, second: int, target: int) -> None:
        first_mask = 1 << first
        second_mask = 1 << second
        target_mask = 1 << target
        for index in range(len(self._state)):
            if (
                index & first_mask
                and index & second_mask
                and not index & target_mask
            ):
                paired = index | target_mask
                self._state[index], self._state[paired] = (
                    self._state[paired],
                    self._state[index],
                )

    def _measure(self, qubit: int) -> int:
        mask = 1 << qubit
        probability_one = sum(
            abs(amplitude) ** 2
            for index, amplitude in enumerate(self._state)
            if index & mask
        )
        if probability_one <= 1e-15:
            outcome = 0
        elif probability_one >= 1.0 - 1e-15:
            outcome = 1
        else:
            outcome = 1 if self._random.random() < probability_one else 0

        probability = probability_one if outcome else 1.0 - probability_one
        norm = math.sqrt(max(probability, 1e-30))
        for index, amplitude in enumerate(self._state):
            if bool(index & mask) != bool(outcome):
                self._state[index] = 0j
            else:
                self._state[index] = amplitude / norm
        return outcome

    def _initialize_qubits(self, count: int) -> None:
        if count < 1 or count > self.max_qubits:
            raise ValueError(
                "qinit supports 1..%d qubits in this emulator" % self.max_qubits
            )
        self._qubit_count = count
        self._state = [0j] * (1 << count)
        self._state[0] = 1.0 + 0j
        self._parameter = None
        self._measurement_log = []

    def _parse_qubit(self, token: str) -> int:
        token = token.strip().lower().replace(",", "")
        if not token.startswith("q") or not token[1:].isdigit():
            raise ValueError("invalid quantum register: %s" % token)
        qubit = int(token[1:])
        if qubit < 0 or qubit >= self._qubit_count:
            raise ValueError("quantum register is out of range: %s" % token)
        return qubit

    def _distinct_qubits(self, tokens: List[str]) -> Tuple[int, ...]:
        qubits = tuple(self._parse_qubit(token) for token in tokens)
        if len(set(qubits)) != len(qubits):
            raise ValueError("multi-qubit instruction requires distinct qubits")
        return qubits

    def _require_initialized(self) -> None:
        if self._qubit_count == 0:
            raise ValueError("qinit must execute before quantum gates")

    def _label_pc(self, label: str) -> int:
        if label not in self.labels:
            raise ValueError("undefined jump label: %s" % label)
        return self.labels[label]

    @staticmethod
    def _expect_args(op: str, args: List[str], count: int) -> None:
        if len(args) != count:
            raise ValueError("%s expects %d operands" % (op, count))

    def _reset_quantum_runtime(self) -> None:
        self._qubit_count = 0
        self._state: List[complex] = []
        self._parameter = None
        self._measurement_log: List[Tuple[int, int, int]] = []

    def _reset_execution_runtime(self) -> None:
        self.pc = 0
        self.registers = [0] * 32
        self._reset_quantum_runtime()
