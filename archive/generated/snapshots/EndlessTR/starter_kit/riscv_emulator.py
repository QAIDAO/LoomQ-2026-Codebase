#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 轻量级 RISC-V 寄存器与控制流模拟器

本模拟器用于在本地评估和调试 L3 (量子-经典混合编程) 的经典部分代码。
支持基础的通用寄存器操作和控制流分支跳转指令，无需选手配置重型 QEMU。
"""

import copy
import math
import struct
from typing import Dict, List, Tuple, Any


# LoomQ Quantum RISC-V extension v1. The opcode is in the standard RISC-V
# custom-0 space, so the extension does not collide with the classic L3 ISA.
QUANTUM_CUSTOM_OPCODE = 0x0B
QUANTUM_EXTENSION_VERSION = 1
QUANTUM_GATE_NAMES = {
    1: "h",
    2: "x",
    3: "s",
    4: "sdg",
    5: "t",
    6: "tdg",
    7: "rz",
    8: "ry",
    9: "cx",
    10: "swap",
    11: "ccx",
    12: "cu1",
    13: "measure",
}
QUANTUM_GATE_SIGNATURES = {
    "h": (1, False),
    "x": (1, False),
    "s": (1, False),
    "sdg": (1, False),
    "t": (1, False),
    "tdg": (1, False),
    "rz": (1, True),
    "ry": (1, True),
    "cx": (2, False),
    "swap": (2, False),
    "ccx": (3, False),
    "cu1": (2, True),
    "measure": (2, False),
}

class TinyRISCVEmulator:
    def __init__(self):
        # 32个通用寄存器 x0 - x31，x0 恒为 0
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.quantum_operations: List[Dict[str, Any]] = []
        self.max_steps = 1000  # 防止死循环

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
        self.quantum_operations = []
        
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

    @staticmethod
    def _parse_u32(text: str, description: str) -> int:
        try:
            value = int(text, 0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"无效的{description}: {text}") from exc
        if value < 0 or value > 0xFFFFFFFF:
            raise ValueError(f"{description}超出 32 位无符号范围: {text}")
        return value

    @classmethod
    def decode_quantum_instruction(cls, args: List[str]) -> Dict[str, Any]:
        """Decode and strictly validate one LoomQ custom-0 instruction."""
        if len(args) not in {1, 2}:
            raise ValueError("qinst 需要一个指令字和可选的一个参数字")
        word = cls._parse_u32(args[0], "量子指令字")
        if word & 0x7F != QUANTUM_CUSTOM_OPCODE:
            raise ValueError("量子指令不是 RISC-V custom-0 opcode 0x0b")
        version = (word >> 28) & 0xF
        if version != QUANTUM_EXTENSION_VERSION:
            raise ValueError(f"不支持的量子扩展版本: {version}")

        q0 = (word >> 7) & 0x1F
        q1 = (word >> 12) & 0x1F
        q2 = (word >> 17) & 0x1F
        gate_id = (word >> 22) & 0x1F
        has_parameter = bool((word >> 27) & 1)
        name = QUANTUM_GATE_NAMES.get(gate_id)
        if name is None:
            raise ValueError(f"未知的量子门编号: {gate_id}")
        arity, expects_parameter = QUANTUM_GATE_SIGNATURES[name]
        if has_parameter != expects_parameter:
            raise ValueError(f"量子门 {name} 的参数标志不合法")
        if len(args) != 1 + int(has_parameter):
            raise ValueError(f"量子门 {name} 的参数载荷数量不合法")

        fields = [q0, q1, q2]
        if any(fields[arity:]):
            raise ValueError(f"量子门 {name} 的未使用量子位字段必须为 0")
        operands = fields[:arity]
        if name != "measure" and len(set(operands)) != len(operands):
            raise ValueError(f"量子门 {name} 的量子位操作数不能重复")

        decoded: Dict[str, Any] = {
            "word": word,
            "gate": name,
            "qubits": [q0] if name == "measure" else operands,
        }
        if name == "measure":
            decoded["clbits"] = [q1]
        if has_parameter:
            parameter_word = cls._parse_u32(args[1], "量子参数字")
            parameter = struct.unpack(">f", struct.pack(">I", parameter_word))[0]
            if not math.isfinite(parameter):
                raise ValueError("量子门参数必须是有限 IEEE-754 binary32 数")
            decoded["parameter_word"] = parameter_word
            decoded["parameter"] = parameter
        return decoded

    def get_quantum_operations(self) -> List[Dict[str, Any]]:
        """Return a deep copy of quantum operations executed so far."""
        return copy.deepcopy(self.quantum_operations)

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

            elif op == "qinst":
                # Decode and record atomically; invalid words never create a
                # partial operation. Quantum-state evolution belongs to the
                # backend consuming this validated instruction stream.
                decoded = self.decode_quantum_instruction(args)
                self.quantum_operations.append(decoded)
                
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
