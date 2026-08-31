#!/usr/bin/env python3
"""
LoomQ 量子 RISC-V 扩展模拟器（fork 自官方 riscv_emulator.py）

在官方 TinyRISCVEmulator 的经典指令子集（li/add/sub/addi/beq/bne/j）之上，
增加自定义量子指令扩展（编码规格见 riscv_quantum_isa.md）：

    qinit n           初始化 n 比特到 |0...0>
    qh/qx/qrz/qry     单比特门（qrz/qry 带 Q14 定点角度参数）
    qcx/qswap         两比特门
    qm q<k>           测量 qubit k，Born 采样后坍缩，结果写 x10+k

测量写回位置与赛题 L3 契约（c[k] -> x10+k）一致，因此量子门、测量与
经典控制流可以在同一条指令流中混合执行。门语义与 starter_kit/simulator.py
（L1 中间层）保持一致。
"""

import cmath
import math
import random
from typing import Dict, List, Tuple

# 量子操作码（与规格文档 §2.1 一致）
QOP = {
    "qh": 0b0000,
    "qx": 0b0001,
    "qrz": 0b0010,
    "qry": 0b0011,
    "qcx": 0b0100,
    "qswap": 0b0101,
    "qm": 0b0110,
    "qinit": 0b0111,
}
QOP_NAME = {value: key for key, value in QOP.items()}
QUANTUM_OPCODE = 0xF  # [31:28]
Q14 = 14  # 定点小数位


def _to_q14(value: float) -> int:
    """Float -> Q14 signed fixed point (clamped to int16 range)."""
    raw = int(round(value * (1 << Q14)))
    return max(-32768, min(32767, raw))


def _from_q14(raw: int) -> float:
    return raw / (1 << Q14)


def encode_qinst(mnemonic: str, qa: int, qb: int = 0, theta: float = 0.0) -> int:
    """Assemble a quantum instruction word (see spec doc §2/§3)."""
    if mnemonic not in QOP:
        raise ValueError("unknown quantum mnemonic %r" % mnemonic)
    word = (QUANTUM_OPCODE << 28) | (QOP[mnemonic] << 24) | ((qa & 0xF) << 20) | ((qb & 0xF) << 16)
    word |= (_to_q14(theta) & 0xFFFF)
    return word


def decode_qinst(word: int) -> Tuple[str, int, int, float]:
    """Disassemble a quantum instruction word back to (mnemonic, qa, qb, theta)."""
    if (word >> 28) != QUANTUM_OPCODE:
        raise ValueError("not a quantum instruction word: 0x%08X" % word)
    qop = (word >> 24) & 0xF
    qa = (word >> 20) & 0xF
    qb = (word >> 16) & 0xF
    imm = word & 0xFFFF
    if imm >= 0x8000:
        imm -= 0x10000  # sign-extend
    return QOP_NAME[qop], qa, qb, _from_q14(imm)


class TinyRISCVQuantumEmulator:
    """Official TinyRISCVEmulator + quantum extension (backward compatible)."""

    def __init__(self, seed=None):
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 2000  # 防止死循环
        self.rng = random.Random(seed)  # None -> system entropy (nondeterministic)
        # 量子寄存器堆：状态向量（Qiskit 位序：index 的 bit k = qubit k）
        self.quantum_state: List[complex] = [1.0 + 0j]
        self.num_qubits = 0

    # -- 基础接口（与官方一致） ------------------------------------------------

    def set_register(self, reg: str, value: int):
        idx = self._parse_reg_idx(reg)
        if idx != 0:
            self.registers[idx] = value

    def get_register(self, reg: str) -> int:
        idx = self._parse_reg_idx(reg)
        return self.registers[idx]

    def _parse_reg_idx(self, reg: str) -> int:
        reg = reg.strip().replace(",", "")
        if not reg.startswith("x") and not reg.startswith("X"):
            raise ValueError(f"无效的寄存器名称: {reg}")
        idx = int(reg[1:])
        if idx < 0 or idx > 31:
            raise ValueError(f"寄存器索引超出范围 (x0-x31): {reg}")
        return idx

    def load_program(self, asm_code: str):
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32
        lines = asm_code.split("\n")
        temp_instructions = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if "#" in line:
                line = line.split("#")[0].strip()
            if line.endswith(":"):
                label_name = line[:-1].strip()
                self.labels[label_name] = len(temp_instructions)
                continue
            elif ":" in line:
                parts = line.split(":", 1)
                label_name = parts[0].strip()
                self.labels[label_name] = len(temp_instructions)
                line = parts[1].strip()
            tokens = line.replace(",", " ").split()
            op = tokens[0].lower()
            args = tokens[1:]
            temp_instructions.append((op, args))
        self.instructions = temp_instructions

    # -- 量子指令实现 ----------------------------------------------------------

    def _require_qubit(self, qa: int) -> None:
        if qa >= self.num_qubits:
            raise ValueError("qubit q%d accessed but qinit size is %d" % (qa, self.num_qubits))

    def _apply_single(self, qa: int, mat: List[List[complex]]) -> None:
        n = self.num_qubits
        m00, m01, m10, m11 = mat[0][0], mat[0][1], mat[1][0], mat[1][1]
        step = 1 << qa
        span = step << 1
        for base in range(0, 1 << n, span):
            for i in range(base, base + step):
                j = i + step
                a, b = self.quantum_state[i], self.quantum_state[j]
                self.quantum_state[i] = m00 * a + m01 * b
                self.quantum_state[j] = m10 * a + m11 * b

    def _apply_diagonal(self, qa: int, phase0: complex, phase1: complex) -> None:
        n = self.num_qubits
        step = 1 << qa
        span = step << 1
        for base in range(0, 1 << n, span):
            for i in range(base, base + step):
                j = i + step
                self.quantum_state[i] *= phase0
                self.quantum_state[j] *= phase1

    def _apply_cx(self, ctrl: int, tgt: int) -> None:
        n = self.num_qubits
        step_t = 1 << tgt
        mask_c = 1 << ctrl
        for i in range(1 << n):
            if (i & mask_c) and not (i & step_t):
                j = i | step_t
                self.quantum_state[i], self.quantum_state[j] = (
                    self.quantum_state[j],
                    self.quantum_state[i],
                )

    def _apply_swap(self, a: int, b: int) -> None:
        n = self.num_qubits
        step_a, step_b = 1 << a, 1 << b
        for i in range(1 << n):
            if (i & step_a) and not (i & step_b):
                j = (i ^ step_a) | step_b
                self.quantum_state[i], self.quantum_state[j] = (
                    self.quantum_state[j],
                    self.quantum_state[i],
                )

    def _qinit(self, n: int) -> None:
        self.num_qubits = n
        dim = 1 << n
        self.quantum_state = [0j] * dim
        self.quantum_state[0] = 1.0 + 0j

    def _measure(self, qa: int) -> int:
        """Born-rule sample of qubit qa, collapse the state, return 0/1."""
        self._require_qubit(qa)
        step = 1 << qa
        prob1 = 0.0
        for i in range(1 << self.num_qubits):
            if i & step:
                prob1 += (self.quantum_state[i].conjugate() * self.quantum_state[i]).real
        outcome = 1 if self.rng.random() < prob1 else 0
        # 投影坍缩：保留满足测量结果的分量并归一化
        mask = step if outcome else 0
        norm2 = 0.0
        for i in range(1 << self.num_qubits):
            if (i & step) == mask:
                norm2 += (self.quantum_state[i].conjugate() * self.quantum_state[i]).real
            else:
                self.quantum_state[i] = 0j
        scale = 1.0 / math.sqrt(norm2) if norm2 > 0 else 0.0
        for i in range(1 << self.num_qubits):
            self.quantum_state[i] *= scale
        return outcome

    # -- 执行循环 ---------------------------------------------------------------

    def execute(self) -> Dict[str, int]:
        steps = 0
        num_instr = len(self.instructions)
        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")
            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1

            # --- 经典指令（与官方一致） ---
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

            # --- 量子扩展指令 ---
            elif op == "qinit":
                self._qinit(int(args[0]))
            elif op in ("qh", "qx", "qrz", "qry", "qcx", "qswap", "qm"):
                self._exec_quantum(op, args)
            else:
                raise ValueError(f"不支持的指令操作: {op}")

            self.pc = next_pc

        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result

    def _exec_quantum(self, op: str, args: List[str]) -> None:
        if op == "qm":
            qa = int(args[0][1:])  # q<k>
            self._require_qubit(qa)
            self.set_register("x%d" % (10 + qa), self._measure(qa))
            return
        if op == "qcx":
            qa, qb = int(args[0][1:]), int(args[1][1:])
            self._require_qubit(max(qa, qb))
            self._apply_cx(qa, qb)
            return
        if op == "qswap":
            qa, qb = int(args[0][1:]), int(args[1][1:])
            self._require_qubit(max(qa, qb))
            self._apply_swap(qa, qb)
            return
        qa = int(args[0][1:])
        self._require_qubit(qa)
        if op == "qh":
            inv = 1.0 / math.sqrt(2.0)
            self._apply_single(qa, [[inv, inv], [inv, -inv]])
        elif op == "qx":
            self._apply_single(qa, [[0, 1], [1, 0]])
        elif op == "qrz":
            theta = float(args[1])
            self._apply_diagonal(qa, cmath.exp(-0.5j * theta), cmath.exp(0.5j * theta))
        elif op == "qry":
            theta = float(args[1])
            c, s = math.cos(theta / 2.0), math.sin(theta / 2.0)
            self._apply_single(qa, [[c, -s], [s, c]])
        else:  # pragma: no cover - guarded by dispatch
            raise ValueError("unknown quantum op %r" % op)


if __name__ == "__main__":
    # 简易演示：贝尔态 + 测量反馈分支
    code = """
    qinit 2
    qh q0
    qcx q0, q1
    qm q0
    qm q1
    beq x10, x11, ENTANGLED
    li x1, 0
    j END
    ENTANGLED:
    li x1, 1
    END:
    """
    emu = TinyRISCVQuantumEmulator()
    emu.load_program(code)
    state = emu.execute()
    print("寄存器执行最终状态:", state)
    assert state.get("x1") == 1, "贝尔态测量对应当相等"
    print("量子 RISC-V 扩展演示通过！")
