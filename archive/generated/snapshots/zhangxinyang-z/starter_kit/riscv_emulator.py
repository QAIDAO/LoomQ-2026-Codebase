#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 轻量级 RISC-V 寄存器与控制流模拟器

本模拟器用于在本地评估和调试 L3 (量子-经典混合编程) 的经典部分代码。
支持基础的通用寄存器操作和控制流分支跳转指令，无需选手配置重型 QEMU。
"""

from typing import Dict, List, Tuple, Any
import math


QUANTUM_CUSTOM_OPCODE = 0b0001011  # RISC-V custom-0 opcode space
QUANTUM_GATES = {"qh": 0, "qx": 1, "qcx": 2, "qmeas": 3}


def encode_quantum_instruction(gate: str, q1: int, q2: int = 0, rd: int = 0) -> int:
    """Encode a LoomQ custom-0 quantum instruction into one RISC-V word."""
    gate_code = QUANTUM_GATES.get(gate.lower())
    if gate_code is None:
        raise ValueError(f"不支持的量子指令: {gate}")
    if not all(isinstance(value, int) and 0 <= value < 8 for value in (q1, q2)):
        raise ValueError("量子比特索引必须在 q0-q7 范围内")
    if not isinstance(rd, int) or not 0 <= rd < 32:
        raise ValueError("目标寄存器必须在 x0-x31 范围内")
    return (gate_code << 25) | (q2 << 20) | (q1 << 15) | (rd << 7) | QUANTUM_CUSTOM_OPCODE

class TinyRISCVEmulator:
    def __init__(self):
        # 32个通用寄存器 x0 - x31，x0 恒为 0
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000  # 防止死循环
        self.quantum_qubits = 8
        self.quantum_state = [0j] * (1 << self.quantum_qubits)
        self.quantum_state[0] = 1 + 0j
        self.quantum_trace: List[str] = []

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
        """
        解析汇编代码并建立标签索引
        """
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32
        self.quantum_state = [0j] * (1 << self.quantum_qubits)
        self.quantum_state[0] = 1 + 0j
        self.quantum_trace = []
        
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
            
            # 解析指令和参数
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

            elif op == "qword":
                # qword <32-bit custom-0 instruction>, see RISCV_QUANTUM_EXTENSION.md
                if len(args) != 1:
                    raise ValueError("qword 需要一个 32 位指令字")
                self._execute_quantum_word(int(args[0], 0))
                
            else:
                raise ValueError(f"不支持的指令操作: {op}")
                
            self.pc = next_pc
            
        # 返回非零寄存器的状态汇总
        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result

    def _apply_single_qubit(self, qubit: int, matrix: List[List[complex]]):
        for index in range(1 << self.quantum_qubits):
            if not ((index >> qubit) & 1):
                paired = index | (1 << qubit)
                low, high = self.quantum_state[index], self.quantum_state[paired]
                self.quantum_state[index] = matrix[0][0] * low + matrix[0][1] * high
                self.quantum_state[paired] = matrix[1][0] * low + matrix[1][1] * high

    def _measure(self, qubit: int) -> int:
        probability_one = sum(
            abs(amplitude) ** 2
            for index, amplitude in enumerate(self.quantum_state)
            if (index >> qubit) & 1
        )
        # Deterministic tie-breaking makes extension tests reproducible.
        outcome = 1 if probability_one > 0.5 else 0
        probability = probability_one if outcome else 1 - probability_one
        if probability <= 1e-15:
            raise RuntimeError("量子测量得到不可能的状态")
        for index, amplitude in enumerate(self.quantum_state):
            if ((index >> qubit) & 1) != outcome:
                self.quantum_state[index] = 0j
            else:
                self.quantum_state[index] = amplitude / math.sqrt(probability)
        return outcome

    def _execute_quantum_word(self, word: int):
        if word < 0 or word > 0xFFFFFFFF or (word & 0x7F) != QUANTUM_CUSTOM_OPCODE:
            raise ValueError("不是 LoomQ custom-0 量子指令")
        funct3 = (word >> 12) & 0x7
        gate_code = (word >> 25) & 0x7F
        q1, q2, rd = (word >> 15) & 0x1F, (word >> 20) & 0x1F, (word >> 7) & 0x1F
        if funct3 != 0 or q1 >= self.quantum_qubits or q2 >= self.quantum_qubits:
            raise ValueError("无效的 LoomQ 量子指令编码")
        if gate_code == QUANTUM_GATES["qh"]:
            root_half = 1 / math.sqrt(2)
            self._apply_single_qubit(q1, [[root_half, root_half], [root_half, -root_half]])
            self.quantum_trace.append(f"qh q[{q1}]")
        elif gate_code == QUANTUM_GATES["qx"]:
            self._apply_single_qubit(q1, [[0, 1], [1, 0]])
            self.quantum_trace.append(f"qx q[{q1}]")
        elif gate_code == QUANTUM_GATES["qcx"]:
            for index in range(1 << self.quantum_qubits):
                if ((index >> q1) & 1) and not ((index >> q2) & 1):
                    paired = index | (1 << q2)
                    self.quantum_state[index], self.quantum_state[paired] = self.quantum_state[paired], self.quantum_state[index]
            self.quantum_trace.append(f"qcx q[{q1}], q[{q2}]")
        elif gate_code == QUANTUM_GATES["qmeas"]:
            self.set_register(f"x{rd}", self._measure(q1))
            self.quantum_trace.append(f"qmeas q[{q1}], x{rd}")
        else:
            raise ValueError("未定义的 LoomQ 量子指令 funct7")

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
