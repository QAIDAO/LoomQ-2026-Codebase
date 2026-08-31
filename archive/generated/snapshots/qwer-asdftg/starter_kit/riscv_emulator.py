#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 轻量级 RISC-V 寄存器与控制流模拟器

本模拟器用于在本地评估和调试 L3 (量子-经典混合编程) 的经典部分代码。
支持基础的通用寄存器操作和控制流分支跳转指令，无需选手配置重型 QEMU。
"""

import math
import random
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union


CUSTOM_0_OPCODE = 0x0B
MAX_QUANTUM_BITS = 8
_FUNCT3_TO_MNEMONIC = {0: "qh", 1: "qcx", 2: "qmeas"}


def _validate_quantum_bit(bit: int) -> int:
    if not isinstance(bit, int) or not 0 <= bit < MAX_QUANTUM_BITS:
        raise ValueError("量子位索引超出范围 (q0-q%d)" % (MAX_QUANTUM_BITS - 1))
    return bit


def _validate_classical_register(register: int) -> int:
    if not isinstance(register, int) or not 0 <= register <= 31:
        raise ValueError("经典寄存器索引超出范围 (x0-x31)")
    return register


def _encode_custom0(funct3: int, rd: int = 0, rs1: int = 0, rs2: int = 0) -> int:
    _validate_classical_register(rd)
    _validate_classical_register(rs1)
    _validate_classical_register(rs2)
    if funct3 not in _FUNCT3_TO_MNEMONIC:
        raise ValueError("不支持的 Custom-0 funct3: %r" % funct3)
    return (funct3 << 12) | (rs2 << 20) | (rs1 << 15) | (rd << 7) | CUSTOM_0_OPCODE


def encode_qh(quantum_bit: int) -> int:
    """Encode ``qh qd`` as a Custom-0 v1 32-bit instruction word."""
    return _encode_custom0(0, rd=_validate_quantum_bit(quantum_bit))


def encode_qcx(control: int, target: int) -> int:
    """Encode ``qcx qc, qt`` as a Custom-0 v1 32-bit instruction word."""
    control = _validate_quantum_bit(control)
    target = _validate_quantum_bit(target)
    if control == target:
        raise ValueError("qcx 的控制位和目标位必须不同")
    return _encode_custom0(1, rs1=control, rs2=target)


def encode_qmeas(classical_register: int, quantum_bit: int) -> int:
    """Encode ``qmeas rd, qs`` as a Custom-0 v1 32-bit instruction word."""
    return _encode_custom0(
        2,
        rd=_validate_classical_register(classical_register),
        rs1=_validate_quantum_bit(quantum_bit),
    )


def decode_custom0_instruction(word: int) -> Tuple[str, Tuple[int, ...]]:
    """Decode and validate one Custom-0 v1 word into its mnemonic operands."""
    if not isinstance(word, int) or not 0 <= word <= 0xFFFFFFFF:
        raise ValueError("Custom-0 指令必须是 32 位无符号整数")
    if word & 0x7F != CUSTOM_0_OPCODE:
        raise ValueError("不是 Custom-0 指令")
    if (word >> 25) & 0x7F:
        raise ValueError("Custom-0 v1 要求 funct7 为零")

    rd = (word >> 7) & 0x1F
    funct3 = (word >> 12) & 0x7
    rs1 = (word >> 15) & 0x1F
    rs2 = (word >> 20) & 0x1F
    mnemonic = _FUNCT3_TO_MNEMONIC.get(funct3)
    if mnemonic is None:
        raise ValueError("不支持的 Custom-0 funct3: %d" % funct3)
    if mnemonic == "qh":
        if rs1 or rs2:
            raise ValueError("qh 要求 rs1 和 rs2 为零")
        return mnemonic, (_validate_quantum_bit(rd),)
    if mnemonic == "qcx":
        if rd:
            raise ValueError("qcx 要求 rd 为零")
        control = _validate_quantum_bit(rs1)
        target = _validate_quantum_bit(rs2)
        if control == target:
            raise ValueError("qcx 的控制位和目标位必须不同")
        return mnemonic, (control, target)

    if rs2:
        raise ValueError("qmeas 要求 rs2 为零")
    return mnemonic, (_validate_classical_register(rd), _validate_quantum_bit(rs1))

class TinyRISCVEmulator:
    def __init__(self, random_seed: Optional[int] = None):
        # 32个通用寄存器 x0 - x31，x0 恒为 0
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[Any]]] = []
        self.max_steps = 1000  # 防止死循环
        self.random_seed = random_seed
        self._reset_quantum_state()

    def _reset_quantum_state(self):
        self.quantum_state = [0j] * (1 << MAX_QUANTUM_BITS)
        self.quantum_state[0] = 1 + 0j
        self._quantum_rng = random.Random(self.random_seed)

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

    def _parse_quantum_bit(self, quantum_reg: str) -> int:
        quantum_reg = quantum_reg.strip().replace(",", "")
        if not quantum_reg.startswith("q") and not quantum_reg.startswith("Q"):
            raise ValueError("无效的量子位名称: %s" % quantum_reg)
        try:
            return _validate_quantum_bit(int(quantum_reg[1:]))
        except ValueError:
            raise
        except (TypeError, IndexError):
            raise ValueError("无效的量子位名称: %s" % quantum_reg)

    def _append_assembly_line(self, line: str, instructions: List[Tuple[str, List[Any]]]):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            return
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if not line:
            return
        if line.endswith(":"):
            self.labels[line[:-1].strip()] = len(instructions)
            return
        if ":" in line:
            label_name, line = line.split(":", 1)
            self.labels[label_name.strip()] = len(instructions)
            line = line.strip()
            if not line:
                return
        tokens = line.replace(",", " ").split()
        if len(tokens) == 1:
            try:
                instructions.append(("raw", [int(tokens[0], 0)]))
                return
            except ValueError:
                pass
        if tokens[0].lower() == ".word":
            if len(tokens) != 2:
                raise ValueError(".word 必须包含一个 32 位指令")
            instructions.append(("raw", [int(tokens[1], 0)]))
            return
        instructions.append((tokens[0].lower(), tokens[1:]))

    def load_program(self, asm_code: Union[str, Iterable[Union[str, int]]]):
        """
        解析汇编代码并建立标签索引
        """
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32
        self._reset_quantum_state()
        temp_instructions = []
        if isinstance(asm_code, str):
            for line in asm_code.split("\n"):
                self._append_assembly_line(line, temp_instructions)
        else:
            for item in asm_code:
                if isinstance(item, int):
                    temp_instructions.append(("raw", [item]))
                elif isinstance(item, str):
                    self._append_assembly_line(item, temp_instructions)
                else:
                    raise TypeError("程序元素必须是汇编字符串或 32 位指令整数")
        self.instructions = temp_instructions

    def _apply_h(self, quantum_bit: int):
        step = 1 << quantum_bit
        scale = 1 / math.sqrt(2)
        for base in range(0, len(self.quantum_state), step * 2):
            for offset in range(step):
                zero_index = base + offset
                one_index = zero_index + step
                zero, one = self.quantum_state[zero_index], self.quantum_state[one_index]
                self.quantum_state[zero_index] = (zero + one) * scale
                self.quantum_state[one_index] = (zero - one) * scale

    def _apply_qcx(self, control: int, target: int):
        for index in range(len(self.quantum_state)):
            if ((index >> control) & 1) and not ((index >> target) & 1):
                swapped_index = index | (1 << target)
                self.quantum_state[index], self.quantum_state[swapped_index] = (
                    self.quantum_state[swapped_index],
                    self.quantum_state[index],
                )

    def _measure_quantum_bit(self, quantum_bit: int) -> int:
        probability_one = sum(
            abs(amplitude) ** 2
            for index, amplitude in enumerate(self.quantum_state)
            if (index >> quantum_bit) & 1
        )
        if probability_one <= 1e-12:
            outcome = 0
        elif probability_one >= 1 - 1e-12:
            outcome = 1
        else:
            outcome = int(self._quantum_rng.random() < probability_one)
        probability = probability_one if outcome else 1 - probability_one
        normalization = 1 / math.sqrt(probability)
        for index, amplitude in enumerate(self.quantum_state):
            self.quantum_state[index] = (
                amplitude * normalization if ((index >> quantum_bit) & 1) == outcome else 0j
            )
        return outcome

    def _execute_quantum_instruction(self, op: str, args: List[Any]):
        if op == "raw":
            op, decoded_args = decode_custom0_instruction(args[0])
            args = list(decoded_args)
        if op == "qh":
            if len(args) != 1:
                raise ValueError("qh 需要一个量子位操作数")
            quantum_bit = args[0] if isinstance(args[0], int) else self._parse_quantum_bit(args[0])
            self._apply_h(_validate_quantum_bit(quantum_bit))
        elif op == "qcx":
            if len(args) != 2:
                raise ValueError("qcx 需要控制位和目标位")
            control = args[0] if isinstance(args[0], int) else self._parse_quantum_bit(args[0])
            target = args[1] if isinstance(args[1], int) else self._parse_quantum_bit(args[1])
            control, target = _validate_quantum_bit(control), _validate_quantum_bit(target)
            if control == target:
                raise ValueError("qcx 的控制位和目标位必须不同")
            self._apply_qcx(control, target)
        elif op == "qmeas":
            if len(args) != 2:
                raise ValueError("qmeas 需要经典目标寄存器和量子位")
            classical_register = (
                args[0] if isinstance(args[0], int) else self._parse_reg_idx(args[0])
            )
            quantum_bit = args[1] if isinstance(args[1], int) else self._parse_quantum_bit(args[1])
            self.set_register("x%d" % _validate_classical_register(classical_register), self._measure_quantum_bit(_validate_quantum_bit(quantum_bit)))
        else:
            return False
        return True

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
            if self._execute_quantum_instruction(op, args):
                pass
            elif op == "li":
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
