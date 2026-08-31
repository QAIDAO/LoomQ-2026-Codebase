#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 轻量级 RISC-V 寄存器与控制流模拟器

本模拟器用于在本地评估和调试 L3 (量子-经典混合编程) 的经典部分代码。
支持基础的通用寄存器操作和控制流分支跳转指令，无需选手配置重型 QEMU。
"""

from typing import Dict, List, Tuple, Any


CUSTOM0_OPCODE = 0x0B
QGATE_FUNCT3 = 0
QMEASURE_FUNCT3 = 1
GATE_IDS = {"h": 1, "x": 2, "s": 3, "sdg": 4, "t": 5, "tdg": 6,
            "cx": 7, "swap": 8, "ccx": 9}
ID_GATES = {value: name for name, value in GATE_IDS.items()}
GATE_ARITY = {"h": 1, "x": 1, "s": 1, "sdg": 1, "t": 1, "tdg": 1,
              "cx": 2, "swap": 2, "ccx": 3}


def _index(value: int, label: str) -> int:
    value = int(value)
    if value < 0 or value > 31:
        raise ValueError(f"{label} index must be in 0..31")
    return value


def encode_quantum_instruction(operation: Dict[str, Any]) -> int:
    """Encode one qgate/qmeasure operation as a 32-bit custom-0 word."""
    kind = operation.get("op")
    if kind == "gate":
        gate = str(operation.get("gate", "")).lower()
        if gate not in GATE_IDS:
            raise ValueError(f"unsupported quantum gate: {gate}")
        qubits = [_index(value, "qubit") for value in operation.get("qubits", [])]
        if len(qubits) != GATE_ARITY[gate]:
            raise ValueError(f"{gate} requires {GATE_ARITY[gate]} qubit operand(s)")
        fields = qubits + [0] * (3 - len(qubits))
        qd, qs1, qs2 = fields
        return (GATE_IDS[gate] << 25) | (qs2 << 20) | (qs1 << 15) | (qd << 7) | CUSTOM0_OPCODE
    if kind == "measure":
        qubit = _index(operation.get("qubit"), "qubit")
        bit = _index(operation.get("bit"), "classical bit")
        return (bit << 15) | (QMEASURE_FUNCT3 << 12) | (qubit << 7) | CUSTOM0_OPCODE
    raise ValueError(f"unsupported quantum operation: {kind}")


def decode_quantum_instruction(word: int) -> Dict[str, Any]:
    """Decode and strictly validate one 32-bit LoomQ custom-0 word."""
    word = int(word)
    if word < 0 or word > 0xFFFFFFFF:
        raise ValueError("instruction word must be an unsigned 32-bit integer")
    if word & 0x7F != CUSTOM0_OPCODE:
        raise ValueError("instruction does not use the custom-0 opcode")
    funct3 = (word >> 12) & 0x7
    qd, qs1, qs2 = (word >> 7) & 0x1F, (word >> 15) & 0x1F, (word >> 20) & 0x1F
    funct7 = (word >> 25) & 0x7F
    if funct3 == QMEASURE_FUNCT3:
        if funct7 or qs2:
            raise ValueError("qmeasure reserves funct7 and qs2 as zero")
        return {"op": "measure", "qubit": qd, "bit": qs1}
    if funct3 != QGATE_FUNCT3:
        raise ValueError(f"unsupported quantum funct3: {funct3}")
    gate = ID_GATES.get(funct7)
    if gate is None:
        raise ValueError(f"unsupported qgate funct7: {funct7}")
    fields = [qd, qs1, qs2]
    arity = GATE_ARITY[gate]
    if any(fields[arity:]):
        raise ValueError(f"unused operands for {gate} must be zero")
    return {"op": "gate", "gate": gate, "qubits": fields[:arity]}

class TinyRISCVEmulator:
    def __init__(self):
        # 32个通用寄存器 x0 - x31，x0 恒为 0
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000  # 防止死循环
        self.quantum_trace: List[Dict[str, Any]] = []

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

            elif op == "qgate":
                # qgate gate, qd[, qs[, qt]] -- LoomQ custom-0 extension.
                if len(args) < 2 or len(args) > 4:
                    raise ValueError("qgate requires a gate and one to three qubits")
                gate = args[0].lower()
                qubits = [int(value) for value in args[1:]]
                word = encode_quantum_instruction(
                    {"op": "gate", "gate": gate, "qubits": qubits}
                )
                self.quantum_trace.append(decode_quantum_instruction(word))

            elif op == "qmeasure":
                # qmeasure qubit, cbit -- records a quantum/classical mapping.
                if len(args) != 2:
                    raise ValueError("qmeasure requires a qubit and classical bit")
                qubit, bit = (int(value) for value in args)
                word = encode_quantum_instruction(
                    {"op": "measure", "qubit": qubit, "bit": bit}
                )
                self.quantum_trace.append(decode_quantum_instruction(word))

            elif op == ".word":
                if len(args) != 1:
                    raise ValueError(".word requires exactly one 32-bit value")
                self.quantum_trace.append(decode_quantum_instruction(int(args[0], 0)))
                
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
