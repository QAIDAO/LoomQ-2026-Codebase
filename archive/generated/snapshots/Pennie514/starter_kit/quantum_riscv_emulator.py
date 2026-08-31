#!/usr/bin/env python3
"""LoomQ Quantum RISC-V 扩展模拟器 (LQ-Q Extension v1.0)

fork 官方 starter_kit/riscv_emulator.py，在 RISC-V custom-0 opcode 空间上增加
量子指令支持。编码规格见 quantum_riscv_isa.md，端到端测试见 test_quantum_riscv.py。

设计要点：量子助记符先被**汇编为真实的 32 位机器码**，执行时再解码。
编码规格因此是承载执行的必要路径，而不是旁置文档。
"""

from __future__ import annotations

import cmath
import math
import random
import re
from typing import Dict, List, Optional, Tuple

try:
    from .riscv_emulator import TinyRISCVEmulator
except ImportError:
    from riscv_emulator import TinyRISCVEmulator


# --- 编码常量（见 quantum_riscv_isa.md §2） ---------------------------------

QUANTUM_OPCODE = 0b0001011  # RISC-V custom-0

F3_GATE1 = 0b000   # 单比特无参
F3_ROT = 0b001     # 单比特含参
F3_GATE2 = 0b010   # 两比特
F3_CCX = 0b011     # 三比特
F3_MEAS = 0b100    # 测量
F3_INIT = 0b101    # 初始化
F3_SETP = 0b110    # 设置参数

GATE1_CODES = {"h": 0, "x": 1, "s": 2, "sdg": 3, "t": 4, "tdg": 5}
ROT_CODES = {"rz": 0, "ry": 1}
GATE2_CODES = {"cx": 0, "swap": 1, "cu1": 2}

QUANTUM_MNEMONICS = ("qinit", "qgate", "qgate2", "qccx", "qmeas", "qsetp", "qrot")


# --- 汇编与解码 -------------------------------------------------------------

def encode(funct7: int, rs2: int, rs1: int, funct3: int, rd: int) -> int:
    """按 R-type 布局打包成 32 位机器码。"""
    for name, value, width in (
        ("funct7", funct7, 7), ("rs2", rs2, 5), ("rs1", rs1, 5),
        ("funct3", funct3, 3), ("rd", rd, 5),
    ):
        if not 0 <= value < (1 << width):
            raise ValueError(f"{name} 超出 {width} bit 范围: {value}")
    return (
        (funct7 << 25) | (rs2 << 20) | (rs1 << 15)
        | (funct3 << 12) | (rd << 7) | QUANTUM_OPCODE
    )


def decode(word: int) -> Tuple[int, int, int, int, int]:
    """解码 32 位机器码，返回 (funct3, funct7, rs1, rs2, rd)。"""
    if word & 0x7F != QUANTUM_OPCODE:
        raise ValueError(f"不是 LQ-Q 量子指令 (opcode != 0x0B): 0x{word:08X}")
    return (
        (word >> 12) & 0b111,     # funct3
        (word >> 25) & 0b1111111,  # funct7
        (word >> 15) & 0b11111,    # rs1
        (word >> 20) & 0b11111,    # rs2
        (word >> 7) & 0b11111,     # rd
    )


def _reg_index(token: str) -> int:
    token = token.strip().replace(",", "")
    if not token.lower().startswith("x"):
        raise ValueError(f"期望寄存器名 (x0-x31)，得到: {token}")
    index = int(token[1:])
    if not 0 <= index <= 31:
        raise ValueError(f"寄存器索引超出 x0-x31: {token}")
    return index


def _qubit_index(token: str) -> int:
    index = int(token.strip().replace(",", ""))
    if not 0 <= index <= 31:
        raise ValueError(f"量子比特索引超出 0-31: {index}")
    return index


def assemble(mnemonic: str, args: List[str]) -> int:
    """将一条量子汇编助记符汇编为 32 位机器码。"""
    mnemonic = mnemonic.lower()

    if mnemonic == "qinit":
        return encode(0, 0, _qubit_index(args[0]), F3_INIT, 0)

    if mnemonic == "qgate":
        gate = args[0].strip().replace(",", "").lower()
        if gate not in GATE1_CODES:
            raise ValueError(f"未知单比特门: {gate}")
        return encode(GATE1_CODES[gate], 0, _qubit_index(args[1]), F3_GATE1, 0)

    if mnemonic == "qrot":
        gate = args[0].strip().replace(",", "").lower()
        if gate not in ROT_CODES:
            raise ValueError(f"未知旋转门: {gate}")
        return encode(ROT_CODES[gate], 0, _qubit_index(args[1]), F3_ROT, 0)

    if mnemonic == "qgate2":
        gate = args[0].strip().replace(",", "").lower()
        if gate not in GATE2_CODES:
            raise ValueError(f"未知两比特门: {gate}")
        return encode(
            GATE2_CODES[gate], _qubit_index(args[2]), _qubit_index(args[1]), F3_GATE2, 0
        )

    if mnemonic == "qccx":
        # 目标位编码在 funct7（见 ISA §3.4）
        return encode(
            _qubit_index(args[2]), _qubit_index(args[1]), _qubit_index(args[0]), F3_CCX, 0
        )

    if mnemonic == "qmeas":
        return encode(0, 0, _qubit_index(args[1]), F3_MEAS, _reg_index(args[0]))

    if mnemonic == "qsetp":
        return encode(0, 0, _reg_index(args[0]), F3_SETP, 0)

    raise ValueError(f"未知量子助记符: {mnemonic}")


# --- 量子态矢 ---------------------------------------------------------------

class QuantumState:
    """小端约定的态矢模拟器：q[0] 为基态索引的最低位。"""

    def __init__(self, n_qubits: int, rng: Optional[random.Random] = None):
        if not 0 < n_qubits <= 20:
            raise ValueError(f"量子比特数须在 1-20 之间，得到 {n_qubits}")
        self.n_qubits = n_qubits
        self.amplitudes: List[complex] = [0j] * (1 << n_qubits)
        self.amplitudes[0] = 1.0 + 0j
        self.rng = rng or random.Random()

    def _check(self, *qubits: int) -> None:
        for qubit in qubits:
            if not 0 <= qubit < self.n_qubits:
                raise ValueError(f"量子比特 {qubit} 超出已分配范围 0-{self.n_qubits - 1}")

    def apply_1q(self, matrix: Tuple[complex, complex, complex, complex], qubit: int) -> None:
        """对单个比特施加 2x2 矩阵 (m00, m01, m10, m11)。"""
        self._check(qubit)
        m00, m01, m10, m11 = matrix
        bit = 1 << qubit
        for index in range(len(self.amplitudes)):
            if index & bit:
                continue
            partner = index | bit
            a0, a1 = self.amplitudes[index], self.amplitudes[partner]
            self.amplitudes[index] = m00 * a0 + m01 * a1
            self.amplitudes[partner] = m10 * a0 + m11 * a1

    def apply_cx(self, control: int, target: int) -> None:
        self._check(control, target)
        if control == target:
            raise ValueError("CNOT 的控制位与目标位不能相同")
        cbit, tbit = 1 << control, 1 << target
        for index in range(len(self.amplitudes)):
            if (index & cbit) and not (index & tbit):
                partner = index | tbit
                self.amplitudes[index], self.amplitudes[partner] = (
                    self.amplitudes[partner], self.amplitudes[index]
                )

    def apply_swap(self, first: int, second: int) -> None:
        self._check(first, second)
        if first == second:
            return
        fbit, sbit = 1 << first, 1 << second
        for index in range(len(self.amplitudes)):
            if bool(index & fbit) and not (index & sbit):
                partner = (index & ~fbit) | sbit
                self.amplitudes[index], self.amplitudes[partner] = (
                    self.amplitudes[partner], self.amplitudes[index]
                )

    def apply_cphase(self, control: int, target: int, theta: float) -> None:
        """CU1：仅当控制位与目标位同为 1 时施加相位 e^{i theta}。"""
        self._check(control, target)
        if control == target:
            raise ValueError("CU1 的控制位与目标位不能相同")
        mask = (1 << control) | (1 << target)
        phase = cmath.exp(1j * theta)
        for index in range(len(self.amplitudes)):
            if index & mask == mask:
                self.amplitudes[index] *= phase

    def apply_ccx(self, control1: int, control2: int, target: int) -> None:
        self._check(control1, control2, target)
        if len({control1, control2, target}) != 3:
            raise ValueError("Toffoli 的三个比特必须互不相同")
        cmask = (1 << control1) | (1 << control2)
        tbit = 1 << target
        for index in range(len(self.amplitudes)):
            if index & cmask == cmask and not (index & tbit):
                partner = index | tbit
                self.amplitudes[index], self.amplitudes[partner] = (
                    self.amplitudes[partner], self.amplitudes[index]
                )

    def measure(self, qubit: int, forced: Optional[int] = None) -> int:
        """按 Born 规则测量并令态矢塌缩。forced 用于确定性测试。"""
        self._check(qubit)
        bit = 1 << qubit
        prob_one = sum(
            abs(amp) ** 2 for index, amp in enumerate(self.amplitudes) if index & bit
        )
        if forced is None:
            outcome = 1 if self.rng.random() < prob_one else 0
        else:
            outcome = 1 if forced else 0
            reachable = prob_one if outcome else 1.0 - prob_one
            if reachable < 1e-12:
                raise ValueError(
                    f"无法强制 q[{qubit}] 测得 {outcome}：该结果概率为 0"
                )
        norm = math.sqrt(prob_one if outcome else 1.0 - prob_one)
        for index in range(len(self.amplitudes)):
            if bool(index & bit) != bool(outcome):
                self.amplitudes[index] = 0j
            else:
                self.amplitudes[index] /= norm
        return outcome

    def probabilities(self) -> Dict[str, float]:
        """返回非零基态的概率，key 为最右字符是 q[0] 的位串（与大赛约定一致）。"""
        result: Dict[str, float] = {}
        for index, amp in enumerate(self.amplitudes):
            probability = abs(amp) ** 2
            if probability > 1e-12:
                result[format(index, "0%db" % self.n_qubits)] = probability
        return result


# 单比特门矩阵 (m00, m01, m10, m11)
_SQRT1_2 = 1.0 / math.sqrt(2.0)
GATE1_MATRICES = {
    0: (_SQRT1_2 + 0j, _SQRT1_2 + 0j, _SQRT1_2 + 0j, -_SQRT1_2 + 0j),   # h
    1: (0j, 1 + 0j, 1 + 0j, 0j),                                        # x
    2: (1 + 0j, 0j, 0j, 1j),                                            # s
    3: (1 + 0j, 0j, 0j, -1j),                                           # sdg
    4: (1 + 0j, 0j, 0j, cmath.exp(1j * math.pi / 4)),                   # t
    5: (1 + 0j, 0j, 0j, cmath.exp(-1j * math.pi / 4)),                  # tdg
}


def _rz_matrix(theta: float):
    return (cmath.exp(-1j * theta / 2), 0j, 0j, cmath.exp(1j * theta / 2))


def _ry_matrix(theta: float):
    cos, sin = math.cos(theta / 2), math.sin(theta / 2)
    return (cos + 0j, -sin + 0j, sin + 0j, cos + 0j)


# --- 扩展模拟器 -------------------------------------------------------------

class QuantumRISCVEmulator(TinyRISCVEmulator):
    """在官方 TinyRISCVEmulator 之上增加 LQ-Q 量子指令。

    经典指令 (li, add, sub, addi, beq, bne, j) 语义与官方完全一致；
    量子指令为纯增量。量子助记符在 load_program 阶段被汇编为 32 位机器码，
    execute 阶段再解码执行——编码规格因此处于执行的必要路径上。
    """

    def __init__(self, seed: Optional[int] = None):
        super().__init__()
        self.quantum: Optional[QuantumState] = None
        self.qparam_milliradians = 0
        self.rng = random.Random(seed)
        self.forced_measurements: Dict[int, int] = {}
        self.measurement_log: List[Tuple[int, int]] = []

    def set_forced_measurements(self, forced: Dict[int, int]) -> None:
        """指定每个比特的测量结果，用于确定性/穷举验证。"""
        self.forced_measurements = dict(forced)

    @property
    def theta(self) -> float:
        """QPARAM 由毫弧度换算为弧度（见 ISA §3.7）。"""
        return self.qparam_milliradians / 1000.0

    def load_program(self, asm_code: str) -> None:
        """解析汇编；量子助记符汇编为 32 位机器码后以 ('.lqq', [word]) 存放。"""
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32
        self.quantum = None
        self.qparam_milliradians = 0
        self.measurement_log = []

        parsed: List[Tuple[str, List[str]]] = []
        for raw in asm_code.split("\n"):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if "#" in line:
                line = line.split("#")[0].strip()
            if not line:
                continue
            if line.endswith(":"):
                self.labels[line[:-1].strip()] = len(parsed)
                continue
            if ":" in line:
                label, _, line = line.partition(":")
                self.labels[label.strip()] = len(parsed)
                line = line.strip()
                if not line:
                    continue
            tokens = line.replace(",", " ").split()
            op, args = tokens[0].lower(), tokens[1:]
            if op in QUANTUM_MNEMONICS:
                parsed.append((".lqq", [str(assemble(op, args))]))
            else:
                parsed.append((op, args))
        self.instructions = parsed

    def _execute_quantum(self, word: int) -> None:
        """解码并执行一条 LQ-Q 指令。"""
        funct3, funct7, rs1, rs2, rd = decode(word)

        if funct3 == F3_INIT:
            self.quantum = QuantumState(rs1, self.rng)
            return
        if funct3 == F3_SETP:
            self.qparam_milliradians = self.registers[rs1]
            return
        if self.quantum is None:
            raise RuntimeError("量子指令执行前必须先 qinit 分配量子比特")

        if funct3 == F3_GATE1:
            if funct7 not in GATE1_MATRICES:
                raise ValueError(f"未定义的单比特门编号 funct7={funct7}")
            self.quantum.apply_1q(GATE1_MATRICES[funct7], rs1)
        elif funct3 == F3_ROT:
            matrix = _rz_matrix(self.theta) if funct7 == 0 else _ry_matrix(self.theta)
            if funct7 not in (0, 1):
                raise ValueError(f"未定义的旋转门编号 funct7={funct7}")
            self.quantum.apply_1q(matrix, rs1)
        elif funct3 == F3_GATE2:
            if funct7 == 0:
                self.quantum.apply_cx(rs1, rs2)
            elif funct7 == 1:
                self.quantum.apply_swap(rs1, rs2)
            elif funct7 == 2:
                self.quantum.apply_cphase(rs1, rs2, self.theta)
            else:
                raise ValueError(f"未定义的两比特门编号 funct7={funct7}")
        elif funct3 == F3_CCX:
            self.quantum.apply_ccx(rs1, rs2, funct7)
        elif funct3 == F3_MEAS:
            outcome = self.quantum.measure(rs1, self.forced_measurements.get(rs1))
            self.measurement_log.append((rs1, outcome))
            if rd != 0:
                self.registers[rd] = outcome
        else:
            raise ValueError(f"未定义的 LQ-Q 指令类别 funct3={funct3}")

    def execute(self) -> Dict[str, int]:
        """执行指令流。经典指令语义与官方 TinyRISCVEmulator 逐条一致。"""
        steps = 0
        count = len(self.instructions)

        while 0 <= self.pc < count:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")

            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1

            if op == ".lqq":
                self._execute_quantum(int(args[0]))
            elif op == "li":
                self.set_register(args[0], int(args[1]))
            elif op == "add":
                self.set_register(
                    args[0], self.get_register(args[1]) + self.get_register(args[2])
                )
            elif op == "sub":
                self.set_register(
                    args[0], self.get_register(args[1]) - self.get_register(args[2])
                )
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

        return {f"x{i}": v for i, v in enumerate(self.registers) if v != 0}

    def _label(self, name: str) -> int:
        if name not in self.labels:
            raise ValueError(f"未定义的跳转标签: {name}")
        return self.labels[name]
