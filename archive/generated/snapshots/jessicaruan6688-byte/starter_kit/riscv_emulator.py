#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 轻量级 RISC-V 寄存器与控制流模拟器

本模拟器用于在本地评估和调试 L3 (量子-经典混合编程) 的经典部分代码。
支持基础的通用寄存器操作和控制流分支跳转指令，无需选手配置重型 QEMU。

LoomQ QISA v1（自定义量子扩展，CUSTOM-0）：
  文本助记符 ``qinit`` / ``qh`` / ``qx`` / ``qcx`` / ``qmeas``
  以及 32-bit 编解码 ``assemble_quantum_word`` / ``decode_quantum_word`` /
  ``load_machine_words``（机器码进入执行链路，对齐主办方 Q3）。
  规格见 ``starter_kit/docs/LOOMQ_QISA_V1.md``。
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# LoomQ QISA v1 — 32-bit CUSTOM-0 encoding helpers
# ---------------------------------------------------------------------------

CUSTOM0_OPCODE = 0b0001011  # RISC-V custom-0

# funct3 -> mnemonic
QISA_FUNCT3 = {
    0b000: "qinit",
    0b001: "qh",
    0b010: "qx",
    0b011: "qcx",
    0b100: "qmeas",
}
QISA_MNEMONIC_TO_FUNCT3 = {v: k for k, v in QISA_FUNCT3.items()}

_SQRT1_2 = 1.0 / math.sqrt(2.0)
_H = (_SQRT1_2, _SQRT1_2, _SQRT1_2, -_SQRT1_2)
_X = (0.0 + 0j, 1.0 + 0j, 1.0 + 0j, 0.0 + 0j)


def assemble_quantum_word(
    mnemonic: str,
    *,
    qs1: int = 0,
    qs2: int = 0,
    rd: int = 0,
    funct7: int = 0,
) -> int:
    """Assemble one LoomQ QISA v1 instruction into a 32-bit word (CUSTOM-0).

    Bit fields (see LOOMQ_QISA_V1.md)::

        [31:25] funct7 (=0 for v1)
        [24:20] qs2   (qcx target; else 0)
        [19:15] qs1   (n / qubit / control)
        [14:12] funct3
        [11:7]  rd    (qmeas classical dest index; else 0)
        [6:0]   opcode = 0b0001011
    """
    op = mnemonic.strip().lower()
    if op not in QISA_MNEMONIC_TO_FUNCT3:
        raise ValueError(f"unknown QISA mnemonic: {mnemonic}")
    if not (0 <= qs1 <= 31 and 0 <= qs2 <= 31 and 0 <= rd <= 31):
        raise ValueError("qs1/qs2/rd must be in 0..31")
    if not (0 <= funct7 <= 0x7F):
        raise ValueError("funct7 must be in 0..127")
    funct3 = QISA_MNEMONIC_TO_FUNCT3[op]
    word = (
        ((funct7 & 0x7F) << 25)
        | ((qs2 & 0x1F) << 20)
        | ((qs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | (CUSTOM0_OPCODE & 0x7F)
    )
    return word & 0xFFFFFFFF


def decode_quantum_word(word: int) -> Dict[str, Any]:
    """Decode a 32-bit CUSTOM-0 word into LoomQ QISA v1 fields."""
    word &= 0xFFFFFFFF
    opcode = word & 0x7F
    if opcode != CUSTOM0_OPCODE:
        raise ValueError(f"not CUSTOM-0 opcode: 0b{opcode:07b}")
    rd = (word >> 7) & 0x1F
    funct3 = (word >> 12) & 0x7
    qs1 = (word >> 15) & 0x1F
    qs2 = (word >> 20) & 0x1F
    funct7 = (word >> 25) & 0x7F
    if funct3 not in QISA_FUNCT3:
        raise ValueError(f"unknown QISA funct3: {funct3}")
    return {
        "mnemonic": QISA_FUNCT3[funct3],
        "opcode": opcode,
        "funct3": funct3,
        "funct7": funct7,
        "qs1": qs1,
        "qs2": qs2,
        "rd": rd,
        "word": word,
    }


def decoded_to_op_args(decoded: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Lower a decoded CUSTOM-0 word to the emulator's ``(op, args)`` tuple.

    This is the bridge that puts binary encoding on the live execution path
    (organizer Q3 / direction 1): ``word → decode → (op, args) → execute``.
    """
    op = str(decoded["mnemonic"])
    qs1 = int(decoded["qs1"])
    qs2 = int(decoded["qs2"])
    rd = int(decoded["rd"])
    if op == "qinit":
        return op, [str(qs1)]
    if op in {"qh", "qx"}:
        return op, [str(qs1)]
    if op == "qcx":
        return op, [str(qs1), str(qs2)]
    if op == "qmeas":
        return op, [str(qs1), f"x{rd}"]
    raise ValueError(f"unsupported QISA mnemonic after decode: {op}")


def assemble_quantum_program_words(
    steps: List[Tuple[str, Dict[str, int]]],
) -> List[int]:
    """Assemble a list of ``(mnemonic, field_kwargs)`` into machine words."""
    return [
        assemble_quantum_word(mnemonic, **fields) for mnemonic, fields in steps
    ]


class _QuantumState:
    """Minimal statevector (pure Python complex list). Qubit k = bit k of index."""

    def __init__(self, n_qubits: int) -> None:
        if n_qubits < 1 or n_qubits > 8:
            raise ValueError(f"qinit n must be in 1..8, got {n_qubits}")
        self.n = n_qubits
        self.amps: List[complex] = [0j] * (1 << n_qubits)
        self.amps[0] = 1.0 + 0j

    def apply_1q(self, matrix: Tuple[complex, complex, complex, complex], qubit: int) -> None:
        a, b, c, d = matrix
        step = 1 << qubit
        amps = self.amps
        for base in range(0, len(amps), step << 1):
            for offset in range(base, base + step):
                i0 = offset
                i1 = offset + step
                x0 = amps[i0]
                x1 = amps[i1]
                amps[i0] = a * x0 + b * x1
                amps[i1] = c * x0 + d * x1

    def apply_cnot(self, control: int, target: int) -> None:
        amps = self.amps
        cmask = 1 << control
        tmask = 1 << target
        for i in range(len(amps)):
            if (i & cmask) and not (i & tmask):
                j = i | tmask
                amps[i], amps[j] = amps[j], amps[i]

    def measure_z(self, qubit: int, rng: random.Random) -> int:
        mask = 1 << qubit
        p1 = 0.0
        for i, amp in enumerate(self.amps):
            if i & mask:
                p1 += (amp.real * amp.real) + (amp.imag * amp.imag)
        p1 = max(0.0, min(1.0, p1))
        bit = 1 if rng.random() < p1 else 0
        keep = mask if bit == 1 else 0
        norm2 = 0.0
        for i, amp in enumerate(self.amps):
            if (i & mask) == keep:
                norm2 += (amp.real * amp.real) + (amp.imag * amp.imag)
            else:
                self.amps[i] = 0j
        if norm2 <= 0.0:
            self.amps = [0j] * len(self.amps)
            self.amps[keep] = 1.0 + 0j
            return bit
        inv = 1.0 / math.sqrt(norm2)
        for i, amp in enumerate(self.amps):
            if amp != 0j:
                self.amps[i] = amp * inv
        return bit


class TinyRISCVEmulator:
    def __init__(self, rng_seed: Optional[int] = None):
        # 32个通用寄存器 x0 - x31，x0 恒为 0
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000  # 防止死循环
        # Quantum extension state
        self.qstate: Optional[_QuantumState] = None
        self.rng_seed = 42 if rng_seed is None else rng_seed
        self.rng = random.Random(self.rng_seed)
        self.machine_words: List[int] = []

    def reset_rng(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            self.rng_seed = seed
        self.rng = random.Random(self.rng_seed)

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

    def _parse_qubit(self, token: str) -> int:
        token = token.strip().replace(",", "")
        idx = int(token)
        if idx < 0:
            raise ValueError(f"qubit index must be >= 0: {token}")
        return idx

    def load_program(self, asm_code: str):
        """
        解析汇编代码并建立标签索引
        """
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32
        self.qstate = None
        self.rng = random.Random(self.rng_seed)

        lines = asm_code.split("\n")
        temp_instructions = []

        # 第一次解析：过滤注释、空行并建立指令列表与 Label 映射
        for line in lines:
            line = line.strip()
            # 过滤注释和空行
            if not line or line.startswith("#") or line.startswith(";"):
                continue

            # 分割行内注释
            if "#" in line:
                line = line.split("#")[0].strip()
            if not line:
                continue

            # 提取标签，例如 "LABEL_A:"
            if line.endswith(":"):
                label_name = line[:-1].strip()
                self.labels[label_name] = len(temp_instructions)
                continue
            elif ":" in line:
                # 处理同行的标签，例如 "LOOP: li x1, 10"
                parts = line.split(":", 1)
                label_name = parts[0].strip()
                self.labels[label_name] = len(temp_instructions)
                line = parts[1].strip()
                if not line:
                    continue

            # 解析指令和参数
            tokens = line.replace(",", " ").split()
            op = tokens[0].lower()
            args = tokens[1:]
            temp_instructions.append((op, args))

        self.instructions = temp_instructions
        self.machine_words: List[int] = []

    def load_machine_words(self, words: List[int]) -> None:
        """Load a program from 32-bit CUSTOM-0 instruction words.

        Each word is decoded and lowered to ``(op, args)`` before ``execute``.
        Classical L3 text programs continue to use ``load_program``; this path
        is the Bonus closed loop required by organizer Q3 (encoding participates
        in a runnable pipeline, not documentation-only).
        """
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32
        self.qstate = None
        self.rng = random.Random(self.rng_seed)
        self.machine_words = [int(w) & 0xFFFFFFFF for w in words]
        for word in self.machine_words:
            decoded = decode_quantum_word(word)
            op, args = decoded_to_op_args(decoded)
            self.instructions.append((op, args))

    def _require_qstate(self) -> _QuantumState:
        if self.qstate is None:
            raise RuntimeError("quantum state not initialized; use qinit n first")
        return self.qstate

    def _exec_quantum(self, op: str, args: List[str]) -> None:
        if op == "qinit":
            n = int(args[0])
            self.qstate = _QuantumState(n)
            return
        qs = self._require_qstate()
        if op == "qh":
            q = self._parse_qubit(args[0])
            if q >= qs.n:
                raise ValueError(f"qh qubit {q} out of range for n={qs.n}")
            qs.apply_1q(_H, q)
        elif op == "qx":
            q = self._parse_qubit(args[0])
            if q >= qs.n:
                raise ValueError(f"qx qubit {q} out of range for n={qs.n}")
            qs.apply_1q(_X, q)
        elif op == "qcx":
            c = self._parse_qubit(args[0])
            t = self._parse_qubit(args[1])
            if c >= qs.n or t >= qs.n:
                raise ValueError(f"qcx qubits ({c},{t}) out of range for n={qs.n}")
            if c == t:
                raise ValueError("qcx control and target must differ")
            qs.apply_cnot(c, t)
        elif op == "qmeas":
            q = self._parse_qubit(args[0])
            rd = args[1]
            if q >= qs.n:
                raise ValueError(f"qmeas qubit {q} out of range for n={qs.n}")
            bit = qs.measure_z(q, self.rng)
            self.set_register(rd, bit)
        else:
            raise ValueError(f"不支持的指令操作: {op}")

    def execute(self) -> Dict[str, int]:
        """
        执行已载入的指令直到程序结束，返回所有寄存器状态字典
        """
        steps = 0
        num_instr = len(self.instructions)

        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")

            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1

            # --- classical ---
            if op == "li":
                # li rd, imm
                rd, imm = args[0], int(args[1])
                self.set_register(rd, imm)

            elif op == "add":
                # add rd, rs1, rs2
                rd, rs1, rs2 = args[0], args[1], args[2]
                self.set_register(rd, self.get_register(rs1) + self.get_register(rs2))

            elif op == "sub":
                # sub rd, rs1, rs2
                rd, rs1, rs2 = args[0], args[1], args[2]
                self.set_register(rd, self.get_register(rs1) - self.get_register(rs2))

            elif op == "addi":
                # addi rd, rs1, imm
                rd, rs1, imm = args[0], args[1], int(args[2])
                self.set_register(rd, self.get_register(rs1) + imm)

            elif op == "mv":
                # mv rd, rs  =>  addi rd, rs, 0
                rd, rs = args[0], args[1]
                self.set_register(rd, self.get_register(rs))

            elif op == "beq":
                # beq rs1, rs2, label
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) == self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]

            elif op == "bne":
                # bne rs1, rs2, label
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) != self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]

            elif op == "blt":
                # blt rs1, rs2, label  (signed)
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) < self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]

            elif op == "bge":
                # bge rs1, rs2, label  (signed)
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) >= self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]

            elif op == "j":
                # j label
                label = args[0]
                if label not in self.labels:
                    raise ValueError(f"未定义的跳转标签: {label}")
                next_pc = self.labels[label]

            elif op == "jal":
                # jal rd, label  (or jal label -> rd=x1)
                if len(args) == 1:
                    rd, label = "x1", args[0]
                else:
                    rd, label = args[0], args[1]
                if label not in self.labels:
                    raise ValueError(f"未定义的跳转标签: {label}")
                self.set_register(rd, self.pc + 1)
                next_pc = self.labels[label]

            elif op == "jalr":
                # jalr rd, rs, imm
                rd, rs, imm = args[0], args[1], int(args[2])
                target = self.get_register(rs) + imm
                self.set_register(rd, self.pc + 1)
                next_pc = target

            elif op in QISA_MNEMONIC_TO_FUNCT3:
                self._exec_quantum(op, args)

            else:
                raise ValueError(f"不支持的指令操作: {op}")

            self.pc = next_pc

        # 返回非零寄存器的状态汇总
        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result


# 简易功能测试
if __name__ == "__main__":
    code = """
    li x1, 5
    li x2, 10
    beq x1, x2, EQUAL
    add x3, x1, x2       # x3 = 15
    j END
    EQUAL:
    sub x3, x2, x1
    END:
    addi x3, x3, 1       # x3 = 16
    """
    emu = TinyRISCVEmulator()
    emu.load_program(code)
    state = emu.execute()
    print("寄存器执行最终状态:", state)
    assert state.get("x3") == 16, "测试失败！"

    # Binary roundtrip smoke
    w = assemble_quantum_word("qcx", qs1=0, qs2=1)
    d = decode_quantum_word(w)
    assert d["mnemonic"] == "qcx" and d["qs1"] == 0 and d["qs2"] == 1

    # Bell smoke (seeded)
    bell = """
    qinit 2
    qh 0
    qcx 0, 1
    qmeas 0, x10
    qmeas 1, x11
    """
    emu2 = TinyRISCVEmulator(rng_seed=42)
    emu2.load_program(bell)
    st = emu2.execute()
    assert st.get("x10", 0) == st.get("x11", 0)
    print("Tiny RISC-V 模拟器核心测试通过！")
