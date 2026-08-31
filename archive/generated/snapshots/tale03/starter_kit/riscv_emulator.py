#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 轻量级 RISC-V 寄存器与控制流模拟器
 
本模拟器用于在本地评估和调试 L3 (量子-经典混合编程) 的经典部分代码。
支持基础的通用寄存器操作和控制流分支跳转指令，无需选手配置重型 QEMU。
 
量子扩展：支持自定义量子指令（opcode 0001011），将量子门操作编码为
RISC-V 原生指令，实现量子-经典统一指令流。
详见 quantum_riscv_spec.md。
"""
 
from typing import Dict, List, Tuple, Any
 
# ===== 量子指令编码常量 =====
CUSTOM_OPCODE = 0b0001011  # RISC-V custom-0 操作码，用于量子指令
 
# funct3 → 量子门映射
GATE_ENCODING = {
    0b000: "h",
    0b001: "x",
    0b010: "cx",
    0b011: "measure",
    0b100: "s",
    0b101: "t",
    0b110: "swap",
    0b111: "ccx",
}
 
# 汇编助记符 → funct3
MNEMONIC_TO_FUNCT3 = {
    "qh": 0b000,
    "qx": 0b001,
    "qcx": 0b010,
    "qmeasure": 0b011,
    "qs": 0b100,
    "qt": 0b101,
    "qswap": 0b110,
    "qccx": 0b111,
}
 
# 所有量子指令的助记符集合
QUANTUM_OPS = set(MNEMONIC_TO_FUNCT3.keys())
 
 
def encode_quantum_instruction(mnemonic: str, qubit1: int = 0, qubit2: int = 0,
                                rd: int = 0, qubit3: int = 0) -> int:
    """将量子汇编指令编码为 32 位 RISC-V 二进制字。
 
    参数:
        mnemonic: 指令助记符，如 "qh", "qcx", "qmeasure"
        qubit1: 目标量子比特索引 (rs1)
        qubit2: 控制量子比特索引 (rs2)
        rd: 经典目标寄存器索引（仅 qmeasure 使用）
        qubit3: 第三量子比特索引（仅 qccx 使用，编码在 funct7 低 5 位）
    """
    funct3 = MNEMONIC_TO_FUNCT3[mnemonic]
    funct7 = qubit3 & 0x1F
    return (funct7 << 25) | (qubit2 << 20) | (qubit1 << 15) | (funct3 << 12) | (rd << 7) | CUSTOM_OPCODE
 
 
def decode_quantum_instruction(word: int) -> dict:
    """将 32 位 RISC-V 二进制字解码为量子指令字段。"""
    opcode = word & 0x7F
    if opcode != CUSTOM_OPCODE:
        raise ValueError(f"不是量子指令：opcode={bin(opcode)}")
    rd = (word >> 7) & 0x1F
    funct3 = (word >> 12) & 0x7
    rs1 = (word >> 15) & 0x1F
    rs2 = (word >> 20) & 0x1F
    funct7 = (word >> 25) & 0x7F
    gate = GATE_ENCODING.get(funct3, "unknown")
    return {
        "gate": gate,
        "funct3": funct3,
        "target_qubit": rs1,
        "control_qubit": rs2,
        "classical_reg": rd,
        "third_qubit": funct7 & 0x1F,
        "binary": format(word, '032b'),
        "hex": hex(word),
    }
 
 
class TinyRISCVEmulator:
    def __init__(self):
        # 32个通用寄存器 x0 - x31，x0 恒为 0
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000  # 防止死循环
 
        # 量子扩展状态
        self.quantum_trace: List[str] = []          # 量子操作追踪记录
        self.measurement_table: Dict[int, int] = {} # 预注入的测量结果（量子比特索引 → 经典值）
 
    def set_measurement(self, qubit: int, value: int):
        """预注入测量结果，用于确定性测试。
 
        参数:
            qubit: 量子比特索引
            value: 测量结果（0 或 1）
        """
        self.measurement_table[qubit] = value
 
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
 
    def _parse_qubit_idx(self, q: str) -> int:
        """解析量子比特操作数，支持 'q0', 'q1', 'q[0]', 'q[1]' 等格式。"""
        q = q.strip().replace(",", "")
        if q.startswith("q[") and q.endswith("]"):
            return int(q[2:-1])
        elif q.startswith("q"):
            return int(q[1:])
        raise ValueError(f"无效的量子比特操作数: {q}")
 
    def load_program(self, asm_code: str):
        """
        解析汇编代码并建立标签索引（支持经典指令和量子指令）
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
        执行已载入的指令直到程序结束，返回所有寄存器状态字典。
        同时记录量子操作到 self.quantum_trace。
        """
        steps = 0
        num_instr = len(self.instructions)
        
        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")
                
            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1
            
            # ===== 经典指令 =====
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
 
            # ===== 量子扩展指令 =====
            elif op == "qh":
                # qh q0 — 对量子比特施加 Hadamard 门
                q = self._parse_qubit_idx(args[0])
                self.quantum_trace.append(f"h q[{q}]")
 
            elif op == "qx":
                # qx q0 — 对量子比特施加 Pauli-X 门
                q = self._parse_qubit_idx(args[0])
                self.quantum_trace.append(f"x q[{q}]")
 
            elif op == "qcx":
                # qcx q0, q1 — 受控非门（CNOT）
                ctrl = self._parse_qubit_idx(args[0])
                tgt = self._parse_qubit_idx(args[1])
                self.quantum_trace.append(f"cx q[{ctrl}], q[{tgt}]")
 
            elif op == "qmeasure":
                # qmeasure q0, x10 — 测量量子比特，结果写入经典寄存器
                q = self._parse_qubit_idx(args[0])
                rd = args[1]
                value = self.measurement_table.get(q, 0)
                self.set_register(rd, value)
                self.quantum_trace.append(f"measure q[{q}] -> {rd}")
 
            elif op == "qs":
                # qs q0 — S 门
                q = self._parse_qubit_idx(args[0])
                self.quantum_trace.append(f"s q[{q}]")
 
            elif op == "qt":
                # qt q0 — T 门
                q = self._parse_qubit_idx(args[0])
                self.quantum_trace.append(f"t q[{q}]")
 
            elif op == "qswap":
                # qswap q0, q1 — 交换两个量子比特
                q1 = self._parse_qubit_idx(args[0])
                q2 = self._parse_qubit_idx(args[1])
                self.quantum_trace.append(f"swap q[{q1}], q[{q2}]")
 
            elif op == "qccx":
                # qccx q0, q1, q2 — Toffoli 门（三量子比特）
                ctrl1 = self._parse_qubit_idx(args[0])
                ctrl2 = self._parse_qubit_idx(args[1])
                tgt = self._parse_qubit_idx(args[2])
                self.quantum_trace.append(f"ccx q[{ctrl1}], q[{ctrl2}], q[{tgt}]")
                
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
 
    # 测试 1：纯经典指令（向后兼容）
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
 
    # 测试 2：量子-经典混合指令流（测量到 |11⟩）
    hybrid_code = """
    qh       q0
    qcx      q0, q1
    qmeasure q0, x10
    qmeasure q1, x11
    li       x20, 1
    beq      x10, x20, EXCITED
    li       x1, 10
    j        END
    EXCITED:
    li       x1, 100
    END:
    addi     x1, x1, 5
    """
    emu = TinyRISCVEmulator()
    emu.set_measurement(0, 1)
    emu.set_measurement(1, 1)
    emu.load_program(hybrid_code)
    state = emu.execute()
    print("混合指令流寄存器状态（q0=1, q1=1）:", state)
    print("量子操作追踪:", emu.quantum_trace)
    assert state.get("x1") == 105, "测试失败！"
    print("量子-经典混合测试通过！（测量 |11⟩ 路径）")
 
    # 测试 2b：测量到 |00⟩
    emu = TinyRISCVEmulator()
    emu.set_measurement(0, 0)
    emu.set_measurement(1, 0)
    emu.load_program(hybrid_code)
    state = emu.execute()
    print("混合指令流寄存器状态（q0=0, q1=0）:", state)
    assert state.get("x1") == 15, "测试失败！"
    print("量子-经典混合测试通过！（测量 |00⟩ 路径）")
 
    # 测试 3：量子指令二进制编码与解码
    word = encode_quantum_instruction("qh", qubit1=0)
    decoded = decode_quantum_instruction(word)
    print("qh q0 编码:", decoded["binary"], decoded["hex"])
    assert decoded["gate"] == "h" and decoded["target_qubit"] == 0, "编码测试失败！"
 
    word = encode_quantum_instruction("qcx", qubit1=1, qubit2=0)
    decoded = decode_quantum_instruction(word)
    print("qcx q0,q1 编码:", decoded["binary"], decoded["hex"])
    assert decoded["gate"] == "cx", "编码测试失败！"
 
    word = encode_quantum_instruction("qmeasure", qubit1=0, rd=10)
    decoded = decode_quantum_instruction(word)
    print("qmeasure q0,x10 编码:", decoded["binary"], decoded["hex"])
    assert decoded["gate"] == "measure" and decoded["classical_reg"] == 10, "编码测试失败！"
 
    print("二进制编码/解码测试全部通过！")
    print("=" * 40)
    print("全部测试通过！量子扩展 RISC-V 模拟器就绪。")