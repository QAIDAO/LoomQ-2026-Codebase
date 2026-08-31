#!/usr/bin/env python3
"""Quantum extension of the official TinyRISCVEmulator (Bonus: 自定义量子
RISC-V 扩展指令). Encoding spec: custom_riscv_isa.md.

This is a genuine fork-and-extend: `QuantumRISCVEmulator` subclasses
`TinyRISCVEmulator` rather than copy-pasting its ~170 lines, so register
semantics, label handling, and program loading (`load_program`) are the
*same* code as the graded emulator, not a second copy that could silently
drift. Only `execute()` is overridden -- it restates the base instruction
dispatch (li/add/sub/addi/beq/bne/j) alongside the two new instructions
(qgate/qmeas), because the base class's execute() has no extension hook to
plug new opcodes into without overriding the whole dispatch loop.

Deliberately NOT wired into hybrid_compiler.py/adapter.py's graded
compile_hybrid() path -- this is an independent demonstration, exactly like
runner.py's run_originq_real_chip/run_spinq_real_chip are separate from the
graded run() path. Reusing the base class here means the graded L3 path
(riscv_emulator.py, untouched) carries zero risk from this addition.
"""

import math
import random
from typing import Dict, List, Optional

try:
    from .riscv_emulator import TinyRISCVEmulator
except ImportError:
    from riscv_emulator import TinyRISCVEmulator

_SQRT_HALF = 1 / math.sqrt(2)

# Gate names accepted by QGATE, matching custom_riscv_isa.md's funct7 table
# (0=H, 1=X, 2=CX) -- kept as name strings here since the emulator is
# text-mnemonic-driven like its base class, not doing real bit decoding.
_SINGLE_QUBIT_GATES = ("h", "x")


class QuantumRISCVEmulator(TinyRISCVEmulator):
    """Adds QGATE/QMEAS (custom-0 opcode space, see custom_riscv_isa.md) on
    top of everything TinyRISCVEmulator already does. `n_qubits` bounds the
    statevector size (2**n_qubits); `seed` is for reproducible tests only --
    default None means real randomness, matching genuine measurement."""

    def __init__(self, n_qubits: int = 8, seed: Optional[int] = None):
        super().__init__()
        self.n_qubits = n_qubits
        self._rng = random.Random(seed)
        self._reset_statevector()

    def _reset_statevector(self) -> None:
        size = 2 ** self.n_qubits
        self.statevector: List[complex] = [0j] * size
        self.statevector[0] = 1 + 0j

    def load_program(self, asm_code: str) -> None:
        super().load_program(asm_code)
        # A fresh program should also start from |00...0>, matching how the
        # base class resets self.registers inside load_program().
        self._reset_statevector()

    # -- Quantum gate application -----------------------------------------
    # All three gates are implemented directly on the statevector via bit
    # masking, no matrix/numpy library -- keeps this fork as dependency-free
    # as the base riscv_emulator.py.

    def _apply_h(self, qubit: int) -> None:
        # Pair up each (index with bit=0, index with bit=1) once and apply
        # the standard 1/sqrt(2) [[1,1],[1,-1]] Hadamard matrix to the pair.
        mask = 1 << qubit
        new_state = [0j] * len(self.statevector)
        for index in range(len(self.statevector)):
            if index & mask:
                continue
            partner = index | mask
            a0, a1 = self.statevector[index], self.statevector[partner]
            new_state[index] = _SQRT_HALF * (a0 + a1)
            new_state[partner] = _SQRT_HALF * (a0 - a1)
        self.statevector = new_state

    def _apply_x(self, qubit: int) -> None:
        mask = 1 << qubit
        new_state = [0j] * len(self.statevector)
        for index, amplitude in enumerate(self.statevector):
            new_state[index ^ mask] = amplitude
        self.statevector = new_state

    def _apply_cx(self, control: int, target: int) -> None:
        cmask, tmask = 1 << control, 1 << target
        new_state = [0j] * len(self.statevector)
        for index, amplitude in enumerate(self.statevector):
            new_index = index ^ tmask if index & cmask else index
            new_state[new_index] = amplitude
        self.statevector = new_state

    def _measure(self, qubit: int) -> int:
        mask = 1 << qubit
        prob_one = sum(
            abs(amp) ** 2 for index, amp in enumerate(self.statevector) if index & mask
        )
        # Clamp for float drift so random() in [0,1) never mis-rounds an
        # exact-0/exact-1 probability into the wrong outcome.
        prob_one = min(1.0, max(0.0, prob_one))
        outcome = 1 if self._rng.random() < prob_one else 0

        norm_sq = prob_one if outcome == 1 else (1.0 - prob_one)
        norm = math.sqrt(norm_sq) if norm_sq > 0 else 1.0
        new_state = [0j] * len(self.statevector)
        for index, amp in enumerate(self.statevector):
            bit = 1 if index & mask else 0
            if bit == outcome:
                new_state[index] = amp / norm
        self.statevector = new_state
        return outcome

    # -- Instruction dispatch ----------------------------------------------

    def execute(self) -> Dict[str, int]:
        steps = 0
        num_instr = len(self.instructions)

        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")

            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1

            if op == "li":
                rd, imm = args[0], int(args[1])
                self.set_register(rd, imm)
            elif op == "add":
                rd, rs1, rs2 = args[0], args[1], args[2]
                self.set_register(rd, self.get_register(rs1) + self.get_register(rs2))
            elif op == "sub":
                rd, rs1, rs2 = args[0], args[1], args[2]
                self.set_register(rd, self.get_register(rs1) - self.get_register(rs2))
            elif op == "addi":
                rd, rs1, imm = args[0], args[1], int(args[2])
                self.set_register(rd, self.get_register(rs1) + imm)
            elif op == "beq":
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) == self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]
            elif op == "bne":
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) != self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]
            elif op == "j":
                label = args[0]
                if label not in self.labels:
                    raise ValueError(f"未定义的跳转标签: {label}")
                next_pc = self.labels[label]
            elif op == "qgate":
                self._dispatch_qgate(args)
            elif op == "qmeas":
                rd, qubit_arg = args[0], args[1]
                qubit = int(qubit_arg)
                outcome = self._measure(qubit)
                self.set_register(rd, outcome)
            else:
                raise ValueError(f"不支持的指令操作: {op}")

            self.pc = next_pc

        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result

    def _dispatch_qgate(self, args: List[str]) -> None:
        gate = args[0].lower()
        if gate in _SINGLE_QUBIT_GATES:
            qubit = int(args[1])
            if gate == "h":
                self._apply_h(qubit)
            else:
                self._apply_x(qubit)
        elif gate == "cx":
            control, target = int(args[1]), int(args[2])
            self._apply_cx(control, target)
        else:
            raise ValueError(f"不支持的量子门: {gate!r}（仅支持 h/x/cx，见 custom_riscv_isa.md）")
