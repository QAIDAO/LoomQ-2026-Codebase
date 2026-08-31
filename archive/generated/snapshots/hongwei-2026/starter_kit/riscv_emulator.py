#!/usr/bin/env python3
"""
LoomQ 量子接入平权计划 - 轻量级 RISC-V 寄存器与控制流模拟器

本模拟器用于在本地评估和调试 L3 (量子-经典混合编程) 的经典部分代码。
支持基础的通用寄存器操作和控制流分支跳转指令，无需选手配置重型 QEMU。
"""

from typing import Dict, List, Tuple, Any

# LoomQ custom-0 opcode (RISC-V custom-0): 0b0001011 == 0x0B
LOOMQ_CUSTOM0_OPCODE = 0x0B
LOOMQ_FUNCT3 = {
    "qinit": 0b000,
    "qh": 0b001,
    "qx": 0b010,
    "qcx": 0b011,
    "qmeas": 0b100,
}


class TinyRISCVEmulator:
    def __init__(self):
        # 32个通用寄存器 x0 - x31，x0 恒为 0
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000  # 防止死循环
        # Optional quantum coprocessor (custom-0). Disabled until qinit.
        self.n_qubits = 0
        self._qstate: List[complex] = []
        self.rng_seed = 1
        self._rng_i = 0

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
        self.n_qubits = 0
        self._qstate = []
        
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
                n = int(args[0])
                if n < 1 or n > 16:
                    raise ValueError("qinit qubit count must be 1..16")
                self.n_qubits = n
                self._qstate = [0j] * (1 << n)
                self._qstate[0] = 1 + 0j

            elif op == "qh":
                self._apply_h(self._qubit_idx(args[0]))
            elif op == "qx":
                self._apply_x(self._qubit_idx(args[0]))
            elif op == "qcx":
                self._apply_cx(self._qubit_idx(args[0]), self._qubit_idx(args[1]))
            elif op == "qmeas":
                q = self._qubit_idx(args[0])
                rd = args[1]
                bit = self._measure_qubit(q)
                self.set_register(rd, bit)
            else:
                raise ValueError(f"不支持的指令操作: {op}")
                
            self.pc = next_pc
            
        # 返回非零寄存器的状态汇总
        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result

    def _qubit_idx(self, token: str) -> int:
        token = token.strip().replace(",", "")
        if token.startswith("x") or token.startswith("X"):
            return self._parse_reg_idx(token)
        return int(token)

    def _apply_h(self, q: int) -> None:
        import math
        s = 1 / math.sqrt(2)
        self._apply_1q(q, [[s, s], [s, -s]])

    def _apply_x(self, q: int) -> None:
        self._apply_1q(q, [[0, 1], [1, 0]])

    def _apply_1q(self, q: int, mat) -> None:
        n = self.n_qubits
        if n <= 0:
            raise RuntimeError("qinit required before quantum ops")
        step = 1 << q
        state = self._qstate
        for base in range(1 << n):
            if base & step:
                continue
            i0, i1 = base, base | step
            a0, a1 = state[i0], state[i1]
            state[i0] = mat[0][0] * a0 + mat[0][1] * a1
            state[i1] = mat[1][0] * a0 + mat[1][1] * a1

    def _apply_cx(self, control: int, target: int) -> None:
        n = self.n_qubits
        if n <= 0:
            raise RuntimeError("qinit required before quantum ops")
        cbit, tbit = 1 << control, 1 << target
        state = self._qstate
        for i in range(1 << n):
            if (i & cbit) and not (i & tbit):
                j = i | tbit
                state[i], state[j] = state[j], state[i]

    def _measure_qubit(self, q: int) -> int:
        n = self.n_qubits
        if n <= 0:
            raise RuntimeError("qinit required before quantum ops")
        mask = 1 << q
        p1 = sum(abs(amp) ** 2 for i, amp in enumerate(self._qstate) if i & mask)
        self._rng_i += 1
        # Deterministic LCG so tests are reproducible without extra deps.
        self.rng_seed = (1103515245 * self.rng_seed + 12345 + self._rng_i) & 0x7FFFFFFF
        r = (self.rng_seed % 1000000) / 1000000.0
        bit = 1 if r < p1 else 0
        # Collapse
        new = [0j] * (1 << n)
        norm = 0.0
        for i, amp in enumerate(self._qstate):
            if ((i & mask) != 0) == (bit == 1):
                new[i] = amp
                norm += abs(amp) ** 2
        if norm <= 0:
            return bit
        scale = norm ** 0.5
        self._qstate = [a / scale for a in new]
        return bit

    @staticmethod
    def encode_custom(op: str, rd: int = 0, rs1: int = 0, rs2: int = 0) -> int:
        """Encode a LoomQ custom-0 word (little-endian RISC-V 32-bit)."""
        funct3 = LOOMQ_FUNCT3[op]
        word = LOOMQ_CUSTOM0_OPCODE
        word |= (rd & 0x1F) << 7
        word |= (funct3 & 0x7) << 12
        word |= (rs1 & 0x1F) << 15
        word |= (rs2 & 0x1F) << 20
        return word

    def load_and_shot(self, asm_code: str, shots: int) -> Dict[str, int]:
        """Run a program `shots` times; collect qmeas destinations as a bitstring.

        Measurement order is the sequence of qmeas destinations x10, x11, ...
        Key is little-endian: rightmost bit is first measured cbit (x10).
        """
        counts: Dict[str, int] = {}
        for shot in range(shots):
            self.rng_seed = 1 + shot * 9973
            self._rng_i = 0
            self.load_program(asm_code)
            self.execute()
            bits = []
            # cbits mapped to x10+
            for idx in range(10, 10 + max(self.n_qubits, 1)):
                bits.append(str(self.registers[idx] & 1))
            key = "".join(reversed(bits[: self.n_qubits]))
            counts[key] = counts.get(key, 0) + 1
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
