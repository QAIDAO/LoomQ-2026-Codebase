#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 轻量级 RISC-V 寄存器与控制流模拟器

本模拟器用于在本地评估和调试 L3 (量子-经典混合编程) 的经典部分代码。
支持基础的通用寄存器操作和控制流分支跳转指令，无需选手配置重型 QEMU。
"""

import math
import random
from typing import Dict, List, Tuple, Any, Optional

QUANTUM_CUSTOM_OPCODE = 0b0001011
QUANTUM_FUNCT3 = {
    "qinit": 0b000,
    "qh": 0b001,
    "qx": 0b010,
    "qcx": 0b011,
    "qmeasure": 0b100,
}
QUANTUM_FUNCT3_TO_OP = {value: key for key, value in QUANTUM_FUNCT3.items()}


def encode_quantum_instruction(op: str, *, qubit: int = 0, target: int = 0, rd: int = 0, size: int = 0) -> int:
    """Encode a LoomQ quantum extension instruction into a 32-bit custom-0 word."""
    op = op.lower()
    if op not in QUANTUM_FUNCT3:
        raise ValueError(f"unsupported quantum opcode: {op}")
    for name, value in {"qubit": qubit, "target": target, "rd": rd, "size": size}.items():
        if value < 0 or value > 31:
            raise ValueError(f"{name} field out of 5-bit range: {value}")

    if op == "qinit":
        rs1, rs2, rd_field = size, 0, 0
    elif op == "qcx":
        rs1, rs2, rd_field = qubit, target, 0
    elif op == "qmeasure":
        rs1, rs2, rd_field = qubit, 0, rd
    else:
        rs1, rs2, rd_field = qubit, 0, 0

    return (
        (0 << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (QUANTUM_FUNCT3[op] << 12)
        | (rd_field << 7)
        | QUANTUM_CUSTOM_OPCODE
    )


def decode_quantum_instruction(word: int) -> Dict[str, int | str]:
    """Decode a 32-bit LoomQ quantum custom-0 instruction into fields."""
    if word < 0 or word > 0xFFFFFFFF:
        raise ValueError(f"instruction word out of 32-bit range: {word}")
    opcode = word & 0x7F
    if opcode != QUANTUM_CUSTOM_OPCODE:
        raise ValueError(f"not a LoomQ quantum custom-0 instruction: opcode={opcode:#x}")
    rd = (word >> 7) & 0x1F
    funct3 = (word >> 12) & 0x7
    rs1 = (word >> 15) & 0x1F
    rs2 = (word >> 20) & 0x1F
    funct7 = (word >> 25) & 0x7F
    if funct7 != 0:
        raise ValueError(f"unsupported quantum funct7: {funct7}")
    if funct3 not in QUANTUM_FUNCT3_TO_OP:
        raise ValueError(f"unsupported quantum funct3: {funct3}")
    op = QUANTUM_FUNCT3_TO_OP[funct3]
    decoded: Dict[str, int | str] = {"op": op, "opcode": opcode, "funct3": funct3, "funct7": funct7}
    if op == "qinit":
        decoded["size"] = rs1
    elif op == "qcx":
        decoded["qubit"] = rs1
        decoded["target"] = rs2
    elif op == "qmeasure":
        decoded["qubit"] = rs1
        decoded["rd"] = rd
    else:
        decoded["qubit"] = rs1
    return decoded


class TinyRISCVEmulator:
    def __init__(self):
        # 32个通用寄存器 x0 - x31，x0 恒为 0
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000  # 防止死循环
        self.quantum_num_qubits = 0
        self.quantum_state: List[complex] = [1.0 + 0.0j]
        self.rng = random.Random(0)

    def set_quantum_seed(self, seed: int):
        self.rng.seed(seed)

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
        self.quantum_num_qubits = 0
        self.quantum_state = [1.0 + 0.0j]
        
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

            elif op == "qinit":
                # qinit n
                self._quantum_init(int(args[0]))

            elif op == "qh":
                # qh q0
                self._apply_single_qubit_gate(self._parse_qubit_idx(args[0]), "h")

            elif op == "qx":
                # qx q0
                self._apply_single_qubit_gate(self._parse_qubit_idx(args[0]), "x")

            elif op == "qcx":
                # qcx q0, q1
                control = self._parse_qubit_idx(args[0])
                target = self._parse_qubit_idx(args[1])
                self._apply_cx(control, target)

            elif op == "qmeasure":
                # qmeasure q0, x1
                qubit = self._parse_qubit_idx(args[0])
                rd = args[1]
                self.set_register(rd, self._measure_qubit(qubit))
                
            else:
                raise ValueError(f"不支持的指令操作: {op}")
                
            self.pc = next_pc
            
        # 返回非零寄存器的状态汇总
        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result

    def _parse_qubit_idx(self, qubit: str) -> int:
        qubit = qubit.strip().replace(",", "")
        if qubit.startswith("q[") and qubit.endswith("]"):
            idx = int(qubit[2:-1])
        elif qubit.startswith("q") or qubit.startswith("Q"):
            idx = int(qubit[1:])
        else:
            raise ValueError(f"无效的量子位名称: {qubit}")
        if idx < 0:
            raise ValueError(f"量子位索引不能为负数: {qubit}")
        return idx

    def _quantum_init(self, num_qubits: int):
        if num_qubits <= 0:
            raise ValueError("qinit 至少需要 1 个量子位")
        if num_qubits > 8:
            raise ValueError("轻量量子扩展最多支持 8 个量子位")
        self.quantum_num_qubits = num_qubits
        self.quantum_state = [0.0 + 0.0j] * (1 << num_qubits)
        self.quantum_state[0] = 1.0 + 0.0j

    def _require_quantum_state(self, qubit: int):
        if self.quantum_num_qubits <= 0:
            raise ValueError("使用量子指令前必须先执行 qinit")
        if qubit >= self.quantum_num_qubits:
            raise ValueError(f"量子位 q{qubit} 超出 qinit 范围")

    def _apply_single_qubit_gate(self, qubit: int, gate: str):
        self._require_quantum_state(qubit)
        bit = 1 << qubit
        new_state = self.quantum_state[:]
        inv_sqrt2 = 1 / math.sqrt(2)
        for basis in range(len(self.quantum_state)):
            if basis & bit:
                continue
            paired = basis | bit
            zero_amp = self.quantum_state[basis]
            one_amp = self.quantum_state[paired]
            if gate == "h":
                new_state[basis] = (zero_amp + one_amp) * inv_sqrt2
                new_state[paired] = (zero_amp - one_amp) * inv_sqrt2
            elif gate == "x":
                new_state[basis] = one_amp
                new_state[paired] = zero_amp
            else:
                raise ValueError(f"不支持的量子单比特门: {gate}")
        self.quantum_state = new_state

    def _apply_cx(self, control: int, target: int):
        self._require_quantum_state(control)
        self._require_quantum_state(target)
        if control == target:
            raise ValueError("qcx 的控制位和目标位不能相同")
        control_bit = 1 << control
        target_bit = 1 << target
        new_state = self.quantum_state[:]
        visited = set()
        for basis in range(len(self.quantum_state)):
            if basis in visited or not (basis & control_bit):
                continue
            flipped = basis ^ target_bit
            new_state[basis] = self.quantum_state[flipped]
            new_state[flipped] = self.quantum_state[basis]
            visited.add(basis)
            visited.add(flipped)
        self.quantum_state = new_state

    def _measure_qubit(self, qubit: int) -> int:
        self._require_quantum_state(qubit)
        bit = 1 << qubit
        probability_one = sum(abs(amplitude) ** 2 for basis, amplitude in enumerate(self.quantum_state) if basis & bit)
        result = 1 if self.rng.random() < probability_one else 0
        keep_bit = bit if result else 0
        norm = math.sqrt(probability_one if result else 1 - probability_one)
        if norm == 0:
            raise RuntimeError("量子测量遇到零概率归一化状态")
        for basis, amplitude in enumerate(self.quantum_state):
            if basis & bit == keep_bit:
                self.quantum_state[basis] = amplitude / norm
            else:
                self.quantum_state[basis] = 0.0 + 0.0j
        return result


def run_quantum_riscv_shots(asm_code: str, shots: int, readout_registers: Optional[List[str]] = None) -> Dict[str, int]:
    """Run a quantum-extended Tiny RISC-V program repeatedly and return bitstring counts."""
    if shots <= 0:
        raise ValueError("shots must be positive")
    registers = readout_registers or ["x1"]
    counts: Dict[str, int] = {}
    for shot in range(shots):
        emulator = TinyRISCVEmulator()
        emulator.set_quantum_seed(shot)
        emulator.load_program(asm_code)
        final_state = emulator.execute()
        bitstring = "".join(str(final_state.get(register, 0)) for register in registers)
        counts[bitstring] = counts.get(bitstring, 0) + 1
    return counts

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
