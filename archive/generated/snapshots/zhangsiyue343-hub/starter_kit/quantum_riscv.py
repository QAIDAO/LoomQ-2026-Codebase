#!/usr/bin/env python3
"""Custom quantum RISC-V extension — Bonus implementation (+8).

Fork-extension of the official TinyRISCVEmulator (starter_kit/riscv_emulator.py):
the classical core keeps identical semantics, while a new custom-0 opcode space
(0x0B) drives an embedded statevector so one program can mix register
arithmetic, branching and genuine quantum operations.

Encoding spec .............. docs/QUANTUM_RISCV_SPEC.md
End-to-end tests ........... tests/test_quantum_riscv.py

Instruction summary (operands are registers unless noted):

    qinit            reset quantum state to |00...0>
    qh   rs          Hadamard        on qubit  x[rs]
    qx   rs          Pauli-X         on qubit  x[rs]
    qz   rs          Pauli-Z         on qubit  x[rs]
    qrz  rs, imm     RZ(imm*pi/8)    on qubit  x[rs]   imm in [-16,15]
    qcx  ra, rb      CNOT ctrl=x[ra], tgt=x[rb]
    qmeas rs, rd     sample qubit x[rs], collapse, write 0/1 to x[rd]

Determinism: measurements draw from an injectable random.Random, so end-to-end
tests are reproducible without weakening the probabilistic model.
"""

from __future__ import annotations

import cmath
import math
from typing import Dict, List, Tuple

try:
    from .riscv_emulator import TinyRISCVEmulator
except ImportError:
    from riscv_emulator import TinyRISCVEmulator


CUSTOM_OPCODE = 0x0B                      # RISC-V custom-0 space

FUNCT7 = {"qh": 1, "qx": 2, "qz": 3, "qrz": 4, "qcx": 5,
          "qmeas": 6, "qinit": 7}
MNEMONIC_BY_FUNCT7 = {code: name for name, code in FUNCT7.items()}


# --------------------------------------------------------------------------
# encoding / decoding (pure, word-level)
# --------------------------------------------------------------------------

def _reg_num(token: str) -> int:
    token = token.strip().lower()
    if not token.startswith("x"):
        raise ValueError("expected register operand, got %r" % token)
    num = int(token[1:])
    if not 0 <= num <= 31:
        raise ValueError("register out of range: %r" % token)
    return num


def encode(mnemonic: str, *operands: str) -> int:
    """Assemble one quantum instruction into its 32-bit word."""
    op = mnemonic.strip().lower()
    if op not in FUNCT7:
        raise ValueError("unknown quantum mnemonic %r" % mnemonic)
    funct7 = FUNCT7[op]
    rs1 = rs2 = rd = 0
    if op == "qcx":
        rs1, rs2 = _reg_num(operands[0]), _reg_num(operands[1])
    elif op == "qmeas":
        rs1, rd = _reg_num(operands[0]), _reg_num(operands[1])
    elif op == "qrz":
        rs1 = _reg_num(operands[0])
        imm = int(operands[1])
        if not -16 <= imm <= 15:
            raise ValueError("qrz immediate must fit signed 5 bits [-16, 15]")
        rs2 = imm & 0x1F
    elif op != "qinit":
        rs1 = _reg_num(operands[0])
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (rd << 7) | CUSTOM_OPCODE


def decode(word: int) -> Tuple[str, List[str]]:
    """Disassemble one 32-bit quantum word back to (mnemonic, operands)."""
    if word & 0x7F != CUSTOM_OPCODE:
        raise ValueError("not a custom-0 quantum instruction")
    funct7 = (word >> 25) & 0x7F
    rs2 = (word >> 20) & 0x1F
    rs1 = (word >> 15) & 0x1F
    rd = (word >> 7) & 0x1F
    if funct7 not in MNEMONIC_BY_FUNCT7:
        raise ValueError("unknown quantum funct7 %d" % funct7)
    name = MNEMONIC_BY_FUNCT7[funct7]
    if name == "qcx":
        return name, ["x%d" % rs1, "x%d" % rs2]
    if name == "qmeas":
        return name, ["x%d" % rs1, "x%d" % rd]
    if name == "qrz":
        imm = rs2 - 32 if rs2 & 0x10 else rs2        # 5-bit two's complement
        return name, ["x%d" % rs1, str(imm)]
    if name == "qinit":
        return name, []
    return name, ["x%d" % rs1]


# --------------------------------------------------------------------------
# minimal statevector kernel (complex amplitudes, little-endian bit order)
# --------------------------------------------------------------------------

class _QuantumState:
    def __init__(self, n_qubits: int):
        if not 1 <= n_qubits <= 12:
            raise ValueError("quantum extension supports 1..12 qubits")
        self.n = n_qubits
        self.amplitudes = [0j] * (1 << n_qubits)
        self.amplitudes[0] = 1.0 + 0j

    def reset(self) -> None:
        self.amplitudes = [0j] * (1 << self.n)
        self.amplitudes[0] = 1.0 + 0j

    def _apply_1q(self, matrix, qubit: int) -> None:
        stride = 1 << qubit
        amps = self.amplitudes
        for base in range(0, len(amps), stride << 1):
            for offset in range(stride):
                i0, i1 = base + offset, base + offset + stride
                a0, a1 = amps[i0], amps[i1]
                amps[i0] = matrix[0][0] * a0 + matrix[0][1] * a1
                amps[i1] = matrix[1][0] * a0 + matrix[1][1] * a1

    def h(self, qubit: int) -> None:
        s = 1.0 / math.sqrt(2.0)
        self._apply_1q(((s, s), (s, -s)), qubit)

    def x(self, qubit: int) -> None:
        self._apply_1q(((0, 1), (1, 0)), qubit)

    def z(self, qubit: int) -> None:
        self._apply_1q(((1, 0), (0, -1)), qubit)

    def rz(self, qubit: int, units_of_pi_over_8: int) -> None:
        angle = units_of_pi_over_8 * math.pi / 8.0
        phase_pos = cmath.exp(-0.5j * angle)
        phase_neg = cmath.exp(+0.5j * angle)
        self._apply_1q(((phase_pos, 0), (0, phase_neg)), qubit)

    def cx(self, control: int, target: int) -> None:
        if control == target:
            raise ValueError("CNOT control and target must differ")
        amps = self.amplitudes
        c_bit, t_bit = 1 << control, 1 << target
        for index in range(len(amps)):
            if index & c_bit and not index & t_bit:
                twin = index | t_bit
                amps[index], amps[twin] = amps[twin], amps[index]

    def probabilities(self) -> List[float]:
        return [abs(a) ** 2 for a in self.amplitudes]

    def measure(self, qubit: int, rng) -> int:
        probs = self.probabilities()
        p_one = sum(p for i, p in enumerate(probs) if i >> qubit & 1)
        outcome = 1 if rng.random() < p_one else 0
        norm = p_one if outcome else (1.0 - p_one)
        if norm <= 0.0:
            outcome = 0 if p_one >= 1.0 else 1
            norm = p_one if outcome else (1.0 - p_one)
        keep = outcome << qubit
        amps = self.amplitudes
        for index in range(len(amps)):
            amps[index] = amps[index] if (index >> qubit & 1) == outcome else 0j
        inv = 1.0 / math.sqrt(norm)
        amps[:] = [(a * inv) for a in amps]
        return outcome


_QUANT_OPS = frozenset(FUNCT7)


# --------------------------------------------------------------------------
# extended emulator (fork of TinyRISCVEmulator with quantum dispatch)
# --------------------------------------------------------------------------

class QuantumTinyRISCVEmulator(TinyRISCVEmulator):
    """Drop-in replacement: everything the official emulator runs still runs;
    custom-0 mnemonics additionally manipulate a real statevector."""

    def __init__(self, n_qubits: int = 4, seed: int = 20260825):
        super().__init__()
        from random import Random
        self.qstate = _QuantumState(n_qubits)
        self.rng = Random(seed)

    def load_program(self, asm_code: str):
        self.qstate.reset()
        return super().load_program(asm_code)

    def execute(self) -> Dict[str, int]:
        steps = 0
        num_instr = len(self.instructions)
        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")
            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1
            if op in _QUANT_OPS:
                self._exec_quantum(op, args)
            elif op == "li":
                self.set_register(args[0], int(args[1]))
            elif op == "add":
                self.set_register(args[0], self.get_register(args[1])
                                  + self.get_register(args[2]))
            elif op == "sub":
                self.set_register(args[0], self.get_register(args[1])
                                  - self.get_register(args[2]))
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
            else:
                raise ValueError(f"不支持的指令操作: {op}")
            self.pc = next_pc
        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result

    def _label(self, label: str) -> int:
        if label not in self.labels:
            raise ValueError(f"未定义的跳转标签: {label}")
        return self.labels[label]

    def _exec_quantum(self, op: str, args: List[str]) -> None:
        qs = self.qstate
        if op == "qinit":
            qs.reset()
        elif op == "qh":
            qs.h(self._qubit_arg(args[0]))
        elif op == "qx":
            qs.x(self._qubit_arg(args[0]))
        elif op == "qz":
            qs.z(self._qubit_arg(args[0]))
        elif op == "qrz":
            qs.rz(self._qubit_arg(args[0]), int(args[1]))
        elif op == "qcx":
            qs.cx(self._qubit_arg(args[0]), self._qubit_arg(args[1]))
        elif op == "qmeas":
            qubit = self._qubit_arg(args[0])
            outcome = qs.measure(qubit, self.rng)
            self.set_register(args[1], outcome)

    def _qubit_arg(self, reg_name: str) -> int:
        index = self.get_register(reg_name)
        if not 0 <= index < self.qstate.n:
            raise ValueError(
                "qubit index %d out of range (n=%d)" % (index, self.qstate.n))
        return index


if __name__ == "__main__":
    emu = QuantumTinyRISCVEmulator(n_qubits=2, seed=42)
    emu.load_program("""
        li x5, 0
        qh x5
        li x6, 1
        qcx x5, x6
        qmeas x5, x10
        qmeas x6, x11
    """)
    print(emu.execute())
