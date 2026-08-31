#!/usr/bin/env python3
"""Q-extension 扩展的 RISC-V 模拟器。

基于官方 riscv_emulator.py 的 TinyRISCVEmulator 扩展，新增自定义量子指令
qh / qx / qcx / qmeasure（见 QISA_SPEC.md），并维护量子操作轨迹 quantum_trace。
"""

import random
from typing import Dict, List, Tuple


class QuantumRISCVEmulator:
    def __init__(self):
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000
        self.quantum_trace: List[str] = []
        self.measurement_inputs: List[int] = []

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
            raise ValueError("无效的寄存器名称: %s" % reg)
        idx = int(reg[1:])
        if idx < 0 or idx > 31:
            raise ValueError("寄存器索引超出范围 (x0-x31): %s" % reg)
        return idx

    def load_program(self, asm_code: str):
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32
        self.quantum_trace = []

        lines = asm_code.split("\n")
        temp_instructions = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if "#" in line:
                line = line.split("#")[0].strip()
            if line.endswith(":"):
                self.labels[line[:-1].strip()] = len(temp_instructions)
                continue
            elif ":" in line:
                parts = line.split(":", 1)
                self.labels[parts[0].strip()] = len(temp_instructions)
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
                self.set_register(args[0], int(args[1]))
            elif op == "add":
                self.set_register(args[0], self.get_register(args[1]) + self.get_register(args[2]))
            elif op == "sub":
                self.set_register(args[0], self.get_register(args[1]) - self.get_register(args[2]))
            elif op == "addi":
                self.set_register(args[0], self.get_register(args[1]) + int(args[2]))
            elif op == "beq":
                if self.get_register(args[0]) == self.get_register(args[1]):
                    if args[2] not in self.labels:
                        raise ValueError("未定义的跳转标签: %s" % args[2])
                    next_pc = self.labels[args[2]]
            elif op == "bne":
                if self.get_register(args[0]) != self.get_register(args[1]):
                    if args[2] not in self.labels:
                        raise ValueError("未定义的跳转标签: %s" % args[2])
                    next_pc = self.labels[args[2]]
            elif op == "j":
                if args[0] not in self.labels:
                    raise ValueError("未定义的跳转标签: %s" % args[0])
                next_pc = self.labels[args[0]]

            # ---- Q-extension 量子指令 ----
            elif op == "qh":
                rd = self._parse_reg_idx(args[0])
                self.quantum_trace.append("h q[%d]" % rd)
            elif op == "qx":
                rd = self._parse_reg_idx(args[0])
                self.quantum_trace.append("x q[%d]" % rd)
            elif op == "qcx":
                rd = self._parse_reg_idx(args[0])
                rs1 = self._parse_reg_idx(args[1])
                self.quantum_trace.append("cx q[%d],q[%d]" % (rs1, rd))
            elif op == "qmeasure":
                rd = self._parse_reg_idx(args[0])
                cbit = self._parse_reg_idx(args[1])
                self.quantum_trace.append("measure q[%d] -> c[%d]" % (rd, cbit))
                if self.measurement_inputs:
                    bit = self.measurement_inputs.pop(0)
                else:
                    bit = random.randint(0, 1)
                self.set_register("x%d" % (10 + cbit), bit)
            else:
                raise ValueError("不支持的指令操作: %s" % op)

            self.pc = next_pc

        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result["x%d" % idx] = val
        return result


if __name__ == "__main__":
    code = """
    qh x0
    qcx x1, x0
    qmeasure x0, x0
    qmeasure x1, x1
    li x1, 5
    addi x1, x1, 1
    """
    emu = QuantumRISCVEmulator()
    emu.load_program(code)
    state = emu.execute()
    print("量子操作轨迹:", emu.quantum_trace)
    print("寄存器终态:", state)
    assert emu.quantum_trace == [
        "h q[0]",
        "cx q[0],q[1]",
        "measure q[0] -> c[0]",
        "measure q[1] -> c[1]",
    ], "量子轨迹不符"
    assert state.get("x1") == 6, "经典后处理结果不符"
    print("Q-extension 核心测试通过！")
