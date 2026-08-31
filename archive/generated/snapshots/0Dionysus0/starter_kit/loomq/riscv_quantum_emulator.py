#!/usr/bin/env python3
"""量子 RISC-V 扩展模拟器（Bonus，+8）。

fork 自官方 `starter_kit/riscv_emulator.py`：保留原有的 32 个通用寄存器
和 li/add/sub/addi/beq/bne/j 七条基础指令的执行语义（逐行照抄），在此
基础上新增 qinit/qh/qx/qcx/qrz/qmeasure 六条量子指令。编码规格见
`starter_kit/loomq/quantum_riscv_spec.md`。

量子门的酉矩阵和态矢量施加逻辑直接复用 loomq/simulate.py、loomq/gates.py
里 L1 已经写好并测试过的实现，这里不重新实现一遍线性代数——只新增
"这些指令怎么解析、怎么坍缩测量"这部分。
"""

import math
from typing import Dict, List, Tuple

import numpy as np

from .gates import single_qubit_matrix
from .simulate import _apply_cx, _apply_single


class QuantumRISCVEmulator:
    def __init__(self):
        # 32 个通用寄存器 x0-x31，x0 恒为 0 —— 跟官方模拟器完全一致
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000

        # 新增：量子态。qstate 为 None 表示还没执行过 qinit。
        self.qstate: "np.ndarray | None" = None
        self.n_qubits = 0
        self._rng = np.random.default_rng()

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
        """解析汇编代码并建立标签索引（跟官方模拟器同一套逻辑）。"""
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32
        self.qstate = None
        self.n_qubits = 0

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

    # -- 量子指令的具体执行 -------------------------------------------------

    def _require_qstate(self, op: str) -> np.ndarray:
        if self.qstate is None:
            raise RuntimeError(f"'{op}' 之前必须先执行 qinit 初始化量子寄存器")
        return self.qstate

    def _op_qinit(self, args: List[str]) -> None:
        n = int(args[0])
        self.n_qubits = n
        self.qstate = np.zeros(1 << n, dtype=complex)
        self.qstate[0] = 1.0

    def _op_qh(self, args: List[str]) -> None:
        state = self._require_qstate("qh")
        qubit = int(args[0])
        self.qstate = _apply_single(state, qubit, single_qubit_matrix("h", ()))

    def _op_qx(self, args: List[str]) -> None:
        state = self._require_qstate("qx")
        qubit = int(args[0])
        self.qstate = _apply_single(state, qubit, single_qubit_matrix("x", ()))

    def _op_qcx(self, args: List[str]) -> None:
        state = self._require_qstate("qcx")
        control, target = int(args[0]), int(args[1])
        self.qstate = _apply_cx(state, control, target)

    def _op_qrz(self, args: List[str]) -> None:
        state = self._require_qstate("qrz")
        qubit, angle_code = int(args[0]), int(args[1]) % 8
        theta = angle_code * math.pi / 4
        self.qstate = _apply_single(state, qubit, single_qubit_matrix("rz", (theta,)))

    def _op_qmeasure(self, args: List[str]) -> None:
        state = self._require_qstate("qmeasure")
        qubit, dest_reg = int(args[0]), args[1]
        bit = 1 << qubit
        idx = np.arange(state.shape[0])
        mask1 = (idx & bit) != 0
        p1 = float(np.sum(np.abs(state[mask1]) ** 2))
        p1 = min(1.0, max(0.0, p1))  # 防止浮点误差把概率推出 [0,1]
        outcome = 1 if self._rng.random() < p1 else 0
        keep_mask = mask1 if outcome == 1 else ~mask1
        new_state = np.zeros_like(state)
        new_state[keep_mask] = state[keep_mask]
        norm = np.linalg.norm(new_state)
        if norm > 0:
            new_state = new_state / norm
        self.qstate = new_state
        self.set_register(dest_reg, outcome)

    _QUANTUM_OPS = {
        "qinit": _op_qinit,
        "qh": _op_qh,
        "qx": _op_qx,
        "qcx": _op_qcx,
        "qrz": _op_qrz,
        "qmeasure": _op_qmeasure,
    }

    def execute(self) -> Dict[str, int]:
        """执行已载入的指令直到程序结束，返回所有非零寄存器状态字典。"""
        steps = 0
        num_instr = len(self.instructions)

        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")

            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1

            if op in self._QUANTUM_OPS:
                self._QUANTUM_OPS[op](self, args)

            elif op == "li":
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

            else:
                raise ValueError(f"不支持的指令操作: {op}")

            self.pc = next_pc

        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result


# 端到端自测：见 quantum_riscv_spec.md 第五节的完整说明。
if __name__ == "__main__":
    program = """
    qinit 2
    qh 0
    qmeasure 0, x1
    beq x1, x0, SKIP
    qx 1
    SKIP:
    qmeasure 1, x2
    """

    trials = 2000
    ones = 0
    for _ in range(trials):
        emu = QuantumRISCVEmulator()
        emu.load_program(program)
        state = emu.execute()
        x1 = state.get("x1", 0)
        x2 = state.get("x2", 0)
        assert x1 == x2, f"恒等关系被打破: x1={x1}, x2={x2}"
        ones += x1

    ratio = ones / trials
    print(f"{trials} 次运行，x1==x2 全部成立；x1=1 的比例 {ratio:.3f}（应接近 0.5）")
    assert 0.4 < ratio < 0.6, "测量分布明显偏离 50/50，可能有 bug"
    print("量子 RISC-V 扩展指令端到端自测通过！")
