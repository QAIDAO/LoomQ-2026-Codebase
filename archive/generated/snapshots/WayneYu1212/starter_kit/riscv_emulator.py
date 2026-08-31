#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 轻量级 RISC-V 寄存器与控制流模拟器

本模拟器用于在本地评估和调试 L3 (量子-经典混合编程) 的经典部分代码。
支持基础的通用寄存器操作和控制流分支跳转指令，无需选手配置重型 QEMU。
"""

from typing import Dict, List, Tuple, Any


QUANTUM_CUSTOM_OPCODE = 0x0B  # RISC-V custom-0 opcode space
QUANTUM_FUNCT3 = {
    "qinit": 0,
    "qh": 1,
    "qx": 2,
    "qrz": 3,
    "qcx": 4,
    "qmeasure": 5,
}
_FUNCT3_QUANTUM = {value: key for key, value in QUANTUM_FUNCT3.items()}


def _bounded_integer(name: str, value: int, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ValueError(f"{name} must be an integer between {lower} and {upper}")
    return value


def encode_quantum_instruction(mnemonic: str, *operands: int) -> int:
    """Encode one deterministic LoomQ quantum-intent instruction as a 32-bit word."""

    if not isinstance(mnemonic, str) or mnemonic.lower() not in QUANTUM_FUNCT3:
        raise ValueError(f"unsupported quantum instruction: {mnemonic}")
    name = mnemonic.lower()
    funct3 = QUANTUM_FUNCT3[name]
    word = QUANTUM_CUSTOM_OPCODE | (funct3 << 12)
    if name in {"qinit", "qh", "qx"}:
        if len(operands) != 1:
            raise ValueError(f"{name} requires one qubit operand")
        qubit = _bounded_integer("qubit", operands[0], 0, 31)
        return word | (qubit << 7)
    if name == "qrz":
        if len(operands) != 2:
            raise ValueError("qrz requires a qubit and signed milliradian immediate")
        qubit = _bounded_integer("qubit", operands[0], 0, 31)
        angle = _bounded_integer("angle_milliradians", operands[1], -2048, 2047)
        return word | (qubit << 7) | ((angle & 0xFFF) << 20)
    if name == "qcx":
        if len(operands) != 2:
            raise ValueError("qcx requires control and target qubits")
        control = _bounded_integer("control qubit", operands[0], 0, 31)
        target = _bounded_integer("target qubit", operands[1], 0, 31)
        if control == target:
            raise ValueError("qcx control and target must differ")
        return word | (control << 15) | (target << 20)
    if len(operands) != 2:
        raise ValueError("qmeasure requires a qubit and result slot")
    qubit = _bounded_integer("qubit", operands[0], 0, 31)
    result_slot = _bounded_integer("result slot", operands[1], 0, 31)
    return word | (result_slot << 7) | (qubit << 15)


def decode_quantum_word(word: int) -> Tuple[str, List[int]]:
    """Decode and validate one LoomQ custom-0 quantum-intent instruction word."""

    value = _bounded_integer("instruction word", word, 0, 0xFFFFFFFF)
    if value & 0x7F != QUANTUM_CUSTOM_OPCODE:
        raise ValueError("instruction does not use the LoomQ custom-0 opcode")
    funct3 = (value >> 12) & 0x7
    mnemonic = _FUNCT3_QUANTUM.get(funct3)
    if mnemonic is None:
        raise ValueError(f"reserved LoomQ quantum funct3: {funct3}")
    rd = (value >> 7) & 0x1F
    rs1 = (value >> 15) & 0x1F
    rs2 = (value >> 20) & 0x1F
    funct7 = (value >> 25) & 0x7F
    if mnemonic in {"qinit", "qh", "qx"}:
        if rs1 or rs2 or funct7:
            raise ValueError(f"reserved fields must be zero for {mnemonic}")
        operands = [rd]
    elif mnemonic == "qrz":
        if rs1:
            raise ValueError("reserved rs1 field must be zero for qrz")
        immediate = (value >> 20) & 0xFFF
        if immediate & 0x800:
            immediate -= 0x1000
        operands = [rd, immediate]
    elif mnemonic == "qcx":
        if rd or funct7:
            raise ValueError("reserved rd/funct7 fields must be zero for qcx")
        if rs1 == rs2:
            raise ValueError("qcx control and target must differ")
        operands = [rs1, rs2]
    else:
        if rs2 or funct7:
            raise ValueError("reserved rs2/funct7 fields must be zero for qmeasure")
        operands = [rs1, rd]
    return mnemonic, operands

class TinyRISCVEmulator:
    def __init__(self):
        # 32个通用寄存器 x0 - x31，x0 恒为 0
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.quantum_trace: List[Dict[str, Any]] = []
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
        self.quantum_trace = []
        
        lines = asm_code.split("\n")
        temp_instructions: List[Tuple[str, List[str]]] = []
        
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
            if op == ".word":
                if len(args) != 1:
                    raise ValueError(".word requires exactly one 32-bit value")
                try:
                    word = int(args[0], 0)
                except ValueError as exc:
                    raise ValueError(f"invalid .word value: {args[0]}") from exc
                op, operands = decode_quantum_word(word)
                args = [str(operand) for operand in operands]
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

            elif op in QUANTUM_FUNCT3:
                try:
                    operands = [int(argument) for argument in args]
                except ValueError as exc:
                    raise ValueError(f"{op} operands must be integers") from exc
                encode_quantum_instruction(op, *operands)
                if op in {"qinit", "qh", "qx"}:
                    event = {"op": op, "qubit": operands[0]}
                elif op == "qrz":
                    event = {
                        "op": op,
                        "qubit": operands[0],
                        "angle_milliradians": operands[1],
                    }
                elif op == "qcx":
                    event = {"op": op, "control": operands[0], "target": operands[1]}
                else:
                    event = {
                        "op": op,
                        "qubit": operands[0],
                        "result_slot": operands[1],
                    }
                self.quantum_trace.append(event)
                
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
