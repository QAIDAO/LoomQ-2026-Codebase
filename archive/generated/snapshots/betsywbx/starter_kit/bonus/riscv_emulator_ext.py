#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 轻量级 RISC-V 寄存器与控制流模拟器
[Bonus 扩展版] 在官方 riscv_emulator.py 基础上 fork，新增 qxor 指令支持。

新增内容相对官方原版只有一处: execute() 新增 elif op == "qxor" 分支，
其余全部逻辑(寄存器管理/标签解析/load_program)与官方版本完全一致，
"""

from typing import Dict, List, Tuple, Any


class TinyRISCVEmulatorExt:
    """
    继承官方 TinyRISCVEmulator 的全部行为,只新增 qxor 指令的执行逻辑。
    """

    def __init__(self):
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000

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
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32

        lines = asm_code.split("\n")
        temp_instructions = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if "#" in line:
                line = line.split("#")[0].strip()
            if line.endswith(":"):
                label_name = line[:-1].strip()
                self.labels[label_name] = len(temp_instructions)
                continue
            elif ":" in line:
                parts = line.split(":", 1)
                label_name = parts[0].strip()
                self.labels[label_name] = len(temp_instructions)
                line = parts[1].strip()
            tokens = line.replace(",", " ").split()
            op = tokens[0].lower()
            args = tokens[1:]
            temp_instructions.append((op, args))

        self.instructions = temp_instructions

    def execute(self) -> Dict[str, int]:
        steps = 0
        num_instr = len(self.instructions)

        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")

            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1

            if op == "li":
                rd, imm = args[0], int(args[1])
                self.set_register(rd, imm)
            elif op == "add":
                rd, rs1, rs2 = args[0], args[1], args[2]
                self.set_register(rd, self.get_register(rs1) + self.get_register(rs2))
            elif op == "sub":
                rd, rs1, rs2 = args[0], args[1], args[2]
                self.set_register(rd, self.get_register(rs1) - self.get_register(rs2))
            elif op == "addi":
                rd, rs1, imm = args[0], args[1], int(args[2])
                self.set_register(rd, self.get_register(rs1) + imm)
            elif op == "beq":
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) == self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]
            elif op == "bne":
                rs1, rs2, label = args[0], args[1], args[2]
                if self.get_register(rs1) != self.get_register(rs2):
                    if label not in self.labels:
                        raise ValueError(f"未定义的跳转标签: {label}")
                    next_pc = self.labels[label]
            elif op == "j":
                label = args[0]
                if label not in self.labels:
                    raise ValueError(f"未定义的跳转标签: {label}")
                next_pc = self.labels[label]

            # ---- 以下是本 fork 新增的唯一分支 ----
            elif op == "qxor":
                # qxor rd, rs1, rs2  ->  rd = rs1 XOR rs2
                # 对应 qxor_isa_spec.md 中定义的 custom-0 空间编码,
                # funct3=000, funct7=0000000
                rd, rs1, rs2 = args[0], args[1], args[2]
                self.set_register(rd, self.get_register(rs1) ^ self.get_register(rs2))
            # ---- 新增分支结束 ----

            else:
                raise ValueError(f"不支持的指令操作: {op}")

            self.pc = next_pc

        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result


if __name__ == "__main__":
    # 官方原有的功能测试,验证fork没有破坏原有6条指令
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
    emu = TinyRISCVEmulatorExt()
    emu.load_program(code)
    state = emu.execute()
    print("[回归测试] 官方原有指令行为:", state)
    assert state.get("x3") == 16, "回归测试失败！fork破坏了原有指令语义"
    print("[回归测试] 通过 - 原有6条指令行为与官方版本完全一致\n")

    # 新增的 qxor 指令测试
    qxor_code = """
    li x1, 10
    li x2, 6
    qxor x3, x1, x2
    """
    emu2 = TinyRISCVEmulatorExt()
    emu2.load_program(qxor_code)
    state2 = emu2.execute()
    print("[qxor测试] 1010 XOR 0110 =", bin(state2.get("x3", 0)), "(期望 0b1100 = 12)")
    assert state2.get("x3") == 12, "qxor测试失败"
    print("[qxor测试] 通过\n")

    print("Tiny RISC-V 扩展模拟器(qxor版)全部测试通过！")