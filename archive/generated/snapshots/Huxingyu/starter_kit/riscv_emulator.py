#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 轻量级 RISC-V 寄存器与控制流模拟器

本模拟器用于在本地评估和调试 L3 (量子-经典混合编程) 的经典部分代码。
支持基础的通用寄存器操作和控制流分支跳转指令，无需选手配置重型 QEMU。
"""

import math
import random
import re
from typing import Dict, List, Tuple, Any


QUANTUM_OPCODE = 0x0B  # RISC-V custom-0 opcode
QUANTUM_FUNCT3 = {
    "qinit": 0,
    "qh": 1,
    "qx": 2,
    "qcx": 3,
    "qmeasure": 4,
}
QUANTUM_FUNCT3_REVERSE = {value: key for key, value in QUANTUM_FUNCT3.items()}


def _register_number(value: Any) -> int:
    if isinstance(value, int):
        number = value
    else:
        text = str(value).strip().lower()
        if not re.fullmatch(r"x\d+", text):
            raise ValueError(f"invalid RISC-V register: {value}")
        number = int(text[1:])
    if not 0 <= number <= 31:
        raise ValueError(f"RISC-V register out of range: {value}")
    return number


def _five_bit(value: Any, label: str) -> int:
    number = int(value)
    if not 0 <= number <= 31:
        raise ValueError(f"{label} must fit in five bits")
    return number


def encode_quantum_instruction(mnemonic: str, *operands: Any) -> int:
    """Encode one LoomQ quantum instruction as a custom-0 RISC-V word."""
    name = mnemonic.strip().lower()
    if name not in QUANTUM_FUNCT3:
        raise ValueError(f"unsupported quantum instruction: {mnemonic}")
    rd = rs1 = rs2 = 0
    if name == "qinit" and len(operands) == 1:
        rs1 = _five_bit(operands[0], "qubit count")
        if rs1 == 0:
            raise ValueError("qinit requires at least one qubit")
    elif name in {"qh", "qx"} and len(operands) == 1:
        rs1 = _five_bit(operands[0], "qubit index")
    elif name == "qcx" and len(operands) == 2:
        rs1 = _five_bit(operands[0], "control qubit")
        rs2 = _five_bit(operands[1], "target qubit")
    elif name == "qmeasure" and len(operands) == 2:
        rd = _register_number(operands[0])
        rs1 = _five_bit(operands[1], "qubit index")
    else:
        raise ValueError(f"wrong operand count for {name}")
    return (
        (rs2 << 20)
        | (rs1 << 15)
        | (QUANTUM_FUNCT3[name] << 12)
        | (rd << 7)
        | QUANTUM_OPCODE
    )


def decode_quantum_instruction(word: int) -> Tuple[str, List[str]]:
    """Decode a LoomQ custom-0 word into the emulator's textual operands."""
    if not isinstance(word, int) or not 0 <= word <= 0xFFFFFFFF:
        raise ValueError("instruction word must be an unsigned 32-bit integer")
    if word & 0x7F != QUANTUM_OPCODE or word >> 25:
        raise ValueError("not a canonical LoomQ quantum instruction")
    funct3 = (word >> 12) & 0x7
    if funct3 not in QUANTUM_FUNCT3_REVERSE:
        raise ValueError("unknown LoomQ quantum funct3")
    name = QUANTUM_FUNCT3_REVERSE[funct3]
    rd, rs1, rs2 = (word >> 7) & 0x1F, (word >> 15) & 0x1F, (word >> 20) & 0x1F
    if name == "qinit":
        if rd or rs2 or rs1 == 0:
            raise ValueError("non-canonical qinit encoding")
        args = [str(rs1)]
    elif name in {"qh", "qx"}:
        if rd or rs2:
            raise ValueError(f"non-canonical {name} encoding")
        args = [str(rs1)]
    elif name == "qcx":
        if rd:
            raise ValueError("non-canonical qcx encoding")
        args = [str(rs1), str(rs2)]
    else:
        if rs2:
            raise ValueError("non-canonical qmeasure encoding")
        args = [f"x{rd}", str(rs1)]
    return name, args

class TinyRISCVEmulator:
    def __init__(self, quantum_seed: int = 0):
        # 32个通用寄存器 x0 - x31，x0 恒为 0
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000  # 防止死循环
        self.quantum_seed = quantum_seed
        self.quantum_rng = random.Random(quantum_seed)
        self.quantum_qubits = 0
        self.quantum_state: List[complex] = []

    def set_register(self, reg: str, value: int):
        idx = self._parse_reg_idx(reg)
        if idx != 0:
            self.registers[idx] = value

    def get_register(self, reg: str) -> int:
        idx = self._parse_reg_idx(reg)
        return self.registers[idx]

    def _parse_reg_idx(self, reg: str) -> int:
        return _register_number(reg.strip().replace(",", ""))

    def _qinit(self, qubits: int):
        if not 1 <= qubits <= 20:
            raise ValueError("qinit supports 1-20 qubits in the lightweight emulator")
        self.quantum_qubits = qubits
        self.quantum_state = [0j] * (1 << qubits)
        self.quantum_state[0] = 1 + 0j

    def _require_qubit(self, qubit: int):
        if not self.quantum_state:
            raise RuntimeError("qinit must execute before quantum gates")
        if not 0 <= qubit < self.quantum_qubits:
            raise ValueError(f"quantum bit index out of range: {qubit}")

    def _q_single(self, name: str, qubit: int):
        self._require_qubit(qubit)
        mask = 1 << qubit
        scale = 1 / math.sqrt(2)
        matrix = ((scale, scale), (scale, -scale)) if name == "qh" else ((0, 1), (1, 0))
        for index in range(len(self.quantum_state)):
            if index & mask:
                continue
            other = index | mask
            zero, one = self.quantum_state[index], self.quantum_state[other]
            self.quantum_state[index] = matrix[0][0] * zero + matrix[0][1] * one
            self.quantum_state[other] = matrix[1][0] * zero + matrix[1][1] * one

    def _qcx(self, control: int, target: int):
        self._require_qubit(control)
        self._require_qubit(target)
        if control == target:
            raise ValueError("qcx control and target must differ")
        control_mask, target_mask = 1 << control, 1 << target
        for index in range(len(self.quantum_state)):
            if index & control_mask and not index & target_mask:
                other = index | target_mask
                self.quantum_state[index], self.quantum_state[other] = (
                    self.quantum_state[other], self.quantum_state[index]
                )

    def _qmeasure(self, destination: str, qubit: int):
        self._require_qubit(qubit)
        mask = 1 << qubit
        probability_one = sum(
            abs(amplitude) ** 2
            for index, amplitude in enumerate(self.quantum_state)
            if index & mask
        )
        bit = 1 if self.quantum_rng.random() < probability_one else 0
        probability = probability_one if bit else 1 - probability_one
        if probability <= 1e-15:
            raise RuntimeError("quantum measurement selected a zero-probability state")
        norm = math.sqrt(probability)
        for index in range(len(self.quantum_state)):
            if bool(index & mask) != bool(bit):
                self.quantum_state[index] = 0j
            else:
                self.quantum_state[index] /= norm
        self.set_register(destination, bit)

    def load_program(self, asm_code: str):
        """
        解析汇编代码并建立标签索引
        """
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32
        self.quantum_rng = random.Random(self.quantum_seed)
        self.quantum_qubits = 0
        self.quantum_state = []
        
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
            
            # A raw hexadecimal word exercises the documented binary encoding.
            if re.fullmatch(r"0x[0-9a-fA-F]{1,8}", line):
                op, args = decode_quantum_instruction(int(line, 16))
            else:
                tokens = line.replace(",", " ").split()
                op = tokens[0].lower()
                args = tokens[1:]
            temp_instructions.append((op, args))
            
        self.instructions = temp_instructions

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
            
            # 模拟执行各指令
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
                    
            elif op == "j":
                # j label
                label = args[0]
                if label not in self.labels:
                    raise ValueError(f"未定义的跳转标签: {label}")
                next_pc = self.labels[label]

            elif op == "qinit":
                self._qinit(int(args[0]))

            elif op in {"qh", "qx"}:
                self._q_single(op, int(args[0]))

            elif op == "qcx":
                self._qcx(int(args[0]), int(args[1]))

            elif op == "qmeasure":
                self._qmeasure(args[0], int(args[1]))
                
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
    print("Tiny RISC-V 模拟器核心测试通过！")
