#!/usr/bin/env python3
"""LoomQ-Q quantum RISC-V extension (Bonus deliverable 2).

Extends the official TinyRISCVEmulator with the custom quantum instructions
specified in quantum_riscv_spec.md (custom-0 opcode family):

    qinit rs1          allocate x[rs1] qubits, reset to |0...0>
    qh    rs1          Hadamard on qubit x[rs1]
    qx    rs1          Pauli-X on qubit x[rs1]
    qcx   rs1, rs2     CNOT control=x[rs1], target=x[rs2]
    qmeas rd, rs1      measure qubit x[rs1], 0/1 -> x[rd], state collapses
    qprob rd, rs1      P(qubit x[rs1] = 1) * 1000 -> x[rd] (no side effect)

All base instructions (li/add/sub/addi/beq/bne/j) behave exactly as upstream;
this file only adds the quantum opcode family and never modifies the official
emulator.
"""

from __future__ import annotations

import cmath
import math
import os
import random
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from riscv_emulator import TinyRISCVEmulator  # noqa: E402

_MAX_QUBITS = 12


class QuantumRISCVEmulator(TinyRISCVEmulator):
    """TinyRISCVEmulator + LoomQ-Q custom quantum opcode family."""

    def __init__(self, rng: Optional[random.Random] = None):
        super().__init__()
        self.rng = rng or random.Random()
        self.qstate: List[complex] = []
        self.num_qubits = 0

    # -- quantum internals -------------------------------------------------

    def _require_qubit(self, index: int) -> None:
        if index < 0 or index >= self.num_qubits:
            raise RuntimeError(
                "量子比特索引越界: %d (已分配 %d)" % (index, self.num_qubits)
            )

    def _apply_single(self, matrix, target: int) -> None:
        step = 1 << target
        size = 1 << self.num_qubits
        (m00, m01), (m10, m11) = matrix
        for base in range(0, size, step << 1):
            for off in range(base, base + step):
                i1 = off | step
                a0, a1 = self.qstate[off], self.qstate[i1]
                self.qstate[off] = m00 * a0 + m01 * a1
                self.qstate[i1] = m10 * a0 + m11 * a1

    def _qinit(self, n: int) -> None:
        if not 1 <= n <= _MAX_QUBITS:
            raise RuntimeError("qinit 支持 1..%d 比特，收到 %d" % (_MAX_QUBITS, n))
        self.num_qubits = n
        self.qstate = [0j] * (1 << n)
        self.qstate[0] = 1.0 + 0j

    def _qprob_milli(self, target: int) -> int:
        self._require_qubit(target)
        step = 1 << target
        prob = 0.0
        for i, amp in enumerate(self.qstate):
            if i & step:
                prob += abs(amp) ** 2
        return int(round(prob * 1000))

    def _qmeas(self, target: int) -> int:
        self._require_qubit(target)
        step = 1 << target
        prob_one = 0.0
        for i, amp in enumerate(self.qstate):
            if i & step:
                prob_one += abs(amp) ** 2
        outcome = 1 if self.rng.random() < prob_one else 0
        # collapse and renormalize
        norm = math.sqrt(prob_one if outcome else (1.0 - prob_one))
        if norm == 0:
            raise RuntimeError("测量到零概率结果，量子态异常")
        for i in range(len(self.qstate)):
            if bool(i & step) != bool(outcome):
                self.qstate[i] = 0j
            else:
                self.qstate[i] /= norm
        return outcome

    # -- instruction dispatch ------------------------------------------------

    def execute(self) -> Dict[str, int]:
        steps = 0
        num_instr = len(self.instructions)
        sqrt1_2 = 1.0 / math.sqrt(2.0)

        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")
            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1

            if op == "li":
                self.set_register(args[0], int(args[1]))
            elif op == "add":
                self.set_register(args[0], self.get_register(args[1]) + self.get_register(args[2]))
            elif op == "sub":
                self.set_register(args[0], self.get_register(args[1]) - self.get_register(args[2]))
            elif op == "addi":
                self.set_register(args[0], self.get_register(args[1]) + int(args[2]))
            elif op == "beq":
                if self.get_register(args[0]) == self.get_register(args[1]):
                    next_pc = self._label(args[2])
            elif op == "bne":
                if self.get_register(args[0]) != self.get_register(args[1]):
                    next_pc = self._label(args[2])
            elif op == "j":
                next_pc = self._label(args[0])
            # --- LoomQ-Q custom quantum opcode family ----------------------
            elif op == "qinit":
                self._qinit(self.get_register(args[0]))
            elif op == "qh":
                target = self.get_register(args[0])
                self._require_qubit(target)
                self._apply_single(
                    [[sqrt1_2, sqrt1_2], [sqrt1_2, -sqrt1_2]], target
                )
            elif op == "qx":
                target = self.get_register(args[0])
                self._require_qubit(target)
                self._apply_single([[0, 1], [1, 0]], target)
            elif op == "qcx":
                control, target = self.get_register(args[0]), self.get_register(args[1])
                self._require_qubit(control)
                self._require_qubit(target)
                cm, tm = 1 << control, 1 << target
                for i in range(len(self.qstate)):
                    if (i & cm) and not (i & tm):
                        j = i | tm
                        self.qstate[i], self.qstate[j] = self.qstate[j], self.qstate[i]
            elif op == "qmeas":
                self.set_register(args[0], self._qmeas(self.get_register(args[1])))
            elif op == "qprob":
                self.set_register(args[0], self._qprob_milli(self.get_register(args[1])))
            else:
                raise ValueError("不支持的指令操作: %s" % op)
            self.pc = next_pc

        return {"x%d" % i: v for i, v in enumerate(self.registers) if v != 0}

    def _label(self, label: str) -> int:
        if label not in self.labels:
            raise ValueError("未定义的跳转标签: %s" % label)
        return self.labels[label]


if __name__ == "__main__":
    # Smoke test: Bell pair prepared and measured inside the processor.
    program = """
    li x1, 2          # 2 qubits
    qinit x1
    li x1, 0          # qubit 0
    li x2, 1          # qubit 1
    qh x1             # H on q0
    qcx x1, x2        # CNOT q0 -> q1
    qmeas x3, x1      # measure q0 -> x3
    qmeas x4, x2      # measure q1 -> x4
    """
    emu = QuantumRISCVEmulator()
    emu.load_program(program)
    state = emu.execute()
    print("Bell pair registers:", state)
    assert state.get("x3") == state.get("x4"), "Bell correlation broken"
    print("QuantumRISCVEmulator smoke test passed.")
