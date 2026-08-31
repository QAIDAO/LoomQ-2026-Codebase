#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 轻量级 RISC-V 寄存器与控制流模拟器

本模拟器用于在本地评估和调试 L3 (量子-经典混合编程) 的经典部分代码。
支持基础的通用寄存器操作和控制流分支跳转指令，无需选手配置重型 QEMU。
"""

from typing import Dict, List, Tuple, Any

class TinyRISCVEmulator:
    def __init__(self):
        # 32个通用寄存器 x0 - x31，x0 恒为 0
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000  # 防止死循环
        # Bonus: 8-qubit custom quantum register (see QUANTUM_RISC_V.md)
        self.qnum = 8
        self.qstate = [0j] * (1 << self.qnum)
        self.qstate[0] = 1 + 0j

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
        self.qstate = [0j] * (1 << self.qnum)
        self.qstate[0] = 1 + 0j
        
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
                    
            elif op in ("j", "j"):
                # j / j label
                label = args[0]
                if label not in self.labels:
                    raise ValueError(f"未定义的跳转标签: {label}")
                next_pc = self.labels[label]

            elif op == "qh":
                self._apply_h(self.get_register(args[0]))
            elif op == "qx":
                self._apply_x(self.get_register(args[0]))
            elif op == "qcx":
                self._apply_cx(self.get_register(args[0]), self.get_register(args[1]))
            elif op == "qmeas":
                bit = self._measure(self.get_register(args[0]))
                self.set_register(args[1], bit)
                
            else:
                raise ValueError(f"不支持的指令操作: {op}")
                
            self.pc = next_pc
            
        # 返回非零寄存器的状态汇总
        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result

    def _apply_h(self, qubit: int) -> None:
        s = 2 ** -0.5
        size = 1 << self.qnum
        out = [0j] * size
        mask = 1 << qubit
        for i in range(size):
            if i & mask:
                continue
            j = i | mask
            a0, a1 = self.qstate[i], self.qstate[j]
            out[i] = s * (a0 + a1)
            out[j] = s * (a0 - a1)
        self.qstate = out

    def _apply_x(self, qubit: int) -> None:
        size = 1 << self.qnum
        out = [0j] * size
        for i in range(size):
            out[i ^ (1 << qubit)] = self.qstate[i]
        self.qstate = out

    def _apply_cx(self, control: int, target: int) -> None:
        size = 1 << self.qnum
        out = [0j] * size
        for i in range(size):
            j = i ^ (1 << target) if (i >> control) & 1 else i
            out[j] = self.qstate[i]
        self.qstate = out

    def _measure(self, qubit: int) -> int:
        prob1 = 0.0
        mask = 1 << qubit
        for i, amp in enumerate(self.qstate):
            if i & mask:
                prob1 += abs(amp) ** 2
        bit = 1 if prob1 >= 0.5 else 0
        kept = [amp if ((i & mask) != 0) == (bit == 1) else 0j for i, amp in enumerate(self.qstate)]
        norm = sum(abs(amp) ** 2 for amp in kept) ** 0.5
        if norm:
            self.qstate = [amp / norm for amp in kept]
        return bit

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


# Official evaluator aliases
TinyRISCVEmulator = TinyRISCVEmulator
TinyRISCVEmulator.load_program = TinyRISCVEmulator.load_program
TinyRISCVEmulator.set_register = TinyRISCVEmulator.set_register
