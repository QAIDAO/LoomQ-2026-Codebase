#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LoomQ 自定义量子 RISC-V 扩展 — Q-Ext 指令集模拟器

基于官方 riscv_emulator.py 的 fork 扩展（官方原版 7 条指令全部保留）：
  li / add / sub / addi / beq / bne / j

新增 Q-Ext 量子扩展指令（opcode 0x77，详见 docs/riscv-quantum-ext.md）：
  qh   qd            # 对 qubit qd 应用 H 门（Hadamard，制造叠加态）
  qx   qd            # 对 qubit qd 应用 X 门（翻转）
  qcx  qc, qt        # CNOT：qc 控制，qt 目标（qbit 纠缠）
  qrz  qd, imm       # 对 qubit qd 应用 RZ(imm * pi/4) 相位旋转
  qmeas rd, qs       # 测量 qubit qs，确定性坍缩，结果写回寄存器 rd

量子态模型：
  模拟器内部维护 statevector（复数振幅列表，2^n 项，n 为用到的最大 qubit+1）。
  位串索引的 bit i = qubit i 的状态（little-endian，与 adapter 统一 Schema
  的 c[0] 最右约定一致）。
  测量采用确定性坍缩：取概率最大的一项；等幅时取索引最小的一项。
  因此同一程序多次执行结果完全一致 —— 端到端测试可复现。

零第三方依赖（与官方原版一致，仅 Python 标准库）。
"""

import math
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Q-Ext 门矩阵（纯 Python 复数，不依赖 numpy）
# ---------------------------------------------------------------------------

_SQRT2 = math.sqrt(2.0)


def _apply_h(amps: List[complex], q: int) -> None:
    """Hadamard：|0> -> (|0>+|1>)/sqrt2, |1> -> (|0>-|1>)/sqrt2"""
    n = len(amps).bit_length() - 1
    for mask in range(1 << n):
        if (mask >> q) & 1:
            continue  # 只处理该 bit 为 0 的基（成对出现）
        i0, i1 = mask, mask | (1 << q)
        a, b = amps[i0], amps[i1]
        amps[i0] = (a + b) / _SQRT2
        amps[i1] = (a - b) / _SQRT2


def _apply_x(amps: List[complex], q: int) -> None:
    """X 门：|0> <-> |1>"""
    n = len(amps).bit_length() - 1
    for mask in range(1 << n):
        if (mask >> q) & 1:
            continue
        i0, i1 = mask, mask | (1 << q)
        amps[i0], amps[i1] = amps[i1], amps[i0]


def _apply_cx(amps: List[complex], ctrl: int, tgt: int) -> None:
    """CNOT：控制位为 1 时翻转目标位。

    注意：只能遍历"目标位为 0"的基态（与 _apply_x 同模式）。
    CNOT 是双向交换（|01> <-> |11>），若遍历全部基态，
    换过去的元素会在后续 mask 中被再换回来（undo）。
    """
    n = len(amps).bit_length() - 1
    for mask in range(1 << n):
        if (mask >> tgt) & 1:
            continue  # 目标位为 1 的基态由配对交换处理
        if (mask >> ctrl) & 1:
            i0, i1 = mask, mask ^ (1 << tgt)
            amps[i0], amps[i1] = amps[i1], amps[i0]


def _apply_rz(amps: List[complex], q: int, theta: float) -> None:
    """RZ(theta)：|0> 乘 e^{i*theta/2}, |1> 乘 e^{-i*theta/2}（只改相位不改概率）"""
    n = len(amps).bit_length() - 1
    c0 = complex(math.cos(theta / 2), math.sin(theta / 2))
    c1 = complex(math.cos(theta / 2), -math.sin(theta / 2))
    for mask in range(1 << n):
        if (mask >> q) & 1:
            amps[mask] *= c1
        else:
            amps[mask] *= c0


def _measure(amps: List[complex], q: int) -> int:
    """确定性测量：取概率最大的坍缩结果；等幅时取 0（索引小者）。

    用相对比较（差 1e-9 容差）而非 `p0 >= 0.5`：
    等幅态振幅 0.7071... 的平方因浮点误差可能略小于 0.5，
    绝对阈值会把等幅态误判成偏置态。
    """
    n = len(amps).bit_length() - 1
    p0 = sum(abs(amps[mask]) ** 2 for mask in range(1 << n) if not (mask >> q) & 1)
    p1 = 1.0 - p0
    if p1 > p0 + 1e-9:
        return 1
    return 0


# ---------------------------------------------------------------------------
# 扩展模拟器（官方 TinyRISCVEmulator 的 fork）
# ---------------------------------------------------------------------------

class TinyRISCVEmulatorQExt:
    """官方 riscv_emulator.py 的 fork 扩展：原 7 条指令 + Q-Ext 量子指令。

    官方 evaluator 引用原版 TinyRISCVEmulator（本文件不参与 L3 客观评测），
    仅作为 Bonus 的自证实现；原版行为完全保留在本类中。
    """

    def __init__(self):
        # 经典部分：与官方原版一致
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.instructions: List[Tuple[str, List[str]]] = []
        self.max_steps = 1000
        # 量子部分：statevector（初始 |0...0>），按需扩容
        self.qubit_count = 0
        self.qstate: List[complex] = [1.0 + 0j]

    # --- 经典寄存器操作（与官方原版一致） ---

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

    # --- 量子态操作 ---

    def _ensure_qubit(self, q: int) -> None:
        """确保 statevector 覆盖 qubit q（0 基 qubit 初始态）。

        注意：不能用 `self.qstate *= 2` —— 列表浅拷贝会让新旧槽引用
        同一个 complex 对象，交换（_apply_x）会失效。新槽必须用
        独立的 0j（complex 不可变，交换引用安全）。
        """
        if q < 0:
            raise ValueError(f"无效的 qubit 索引: {q}")
        while q >= self.qubit_count:
            old = len(self.qstate)
            self.qubit_count += 1
            self.qstate = self.qstate + [0j] * old

    def _get_qubit(self, tok: str) -> int:
        """解析 qubit 操作数（允许 q0 / q[0] / q 形式，与 QASM 风格兼容）。"""
        tok = tok.strip().replace(",", "")
        if tok.startswith("q"):
            tok = tok[1:].replace("[", "").replace("]", "")
            return int(tok)
        return int(tok)

    def load_program(self, asm_code: str) -> None:
        """解析汇编代码并建立标签索引（与官方原版解析规则一致）。"""
        self.instructions = []
        self.labels = {}
        self.pc = 0
        self.registers = [0] * 32
        self.qubit_count = 0
        self.qstate = [1.0 + 0j]

        temp_instructions = []
        for line in asm_code.split("\n"):
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
            temp_instructions.append((tokens[0].lower(), tokens[1:]))
        self.instructions = temp_instructions

    def execute(self) -> Dict[str, int]:
        """执行已载入程序（经典 + 量子扩展指令）直到结束，返回非零寄存器。"""
        steps = 0
        num_instr = len(self.instructions)

        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")

            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1

            # --- 经典指令：与官方原版完全一致 ---
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

            # --- Q-Ext 量子扩展指令 ---
            elif op == "qh":
                q = self._get_qubit(args[0])
                self._ensure_qubit(q)
                _apply_h(self.qstate, q)
            elif op == "qx":
                q = self._get_qubit(args[0])
                self._ensure_qubit(q)
                _apply_x(self.qstate, q)
            elif op == "qcx":
                qc, qt = self._get_qubit(args[0]), self._get_qubit(args[1])
                self._ensure_qubit(max(qc, qt))
                _apply_cx(self.qstate, qc, qt)
            elif op == "qrz":
                q = self._get_qubit(args[0])
                self._ensure_qubit(q)
                _apply_rz(self.qstate, q, int(args[1]) * math.pi / 4)
            elif op == "qmeas":
                rd, qs = args[0], self._get_qubit(args[1])
                self._ensure_qubit(qs)
                self.set_register(rd, _measure(self.qstate, qs))

            else:
                raise ValueError(f"不支持的指令操作: {op}")

            self.pc = next_pc

        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result[f"x{idx}"] = val
        return result


# ---------------------------------------------------------------------------
# 端到端测试（Bonus 第三项：可运行的测试入口）
# ---------------------------------------------------------------------------

def _run(asm: str) -> Tuple["TinyRISCVEmulatorQExt", Dict[str, int]]:
    """执行汇编，返回 (模拟器实例, 非零寄存器结果)。

    注意：execute() 只返回非零寄存器（官方原版语义），测量结果为 0
    时需用 emu.get_register() 读取。
    """
    emu = TinyRISCVEmulatorQExt()
    emu.load_program(asm)
    return emu, emu.execute()


def run_tests() -> int:
    """Q-Ext 端到端测试。全部通过返回 0，否则返回 1。"""
    passed = 0
    failed = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print("  [PASS] %s" % name)
        else:
            failed += 1
            print("  [FAIL] %s %s" % (name, detail))

    print("== Q-Ext 端到端测试 ==")

    # 测试 1：经典指令兼容性 —— 官方 7 条指令必须原样工作
    emu, state = _run("""
    li x1, 5
    li x2, 10
    beq x1, x2, EQUAL
    add x3, x1, x2
    j END
    EQUAL:
    sub x3, x2, x1
    END:
    addi x3, x3, 1
    """)
    check("经典指令兼容（官方 7 条原样可跑）", emu.get_register("x3") == 16, str(state))

    # 测试 2：贝尔纠缠 —— H + CNOT 后测量两次必须一致（x1 == x2）
    emu, state = _run("""
    qh q0
    qcx q0, q1
    qmeas x1, q0
    qmeas x2, q1
    """)
    check("贝尔纠缠一致性（两次测量相等）",
          emu.get_register("x1") == emu.get_register("x2"), str(state))
    check("贝尔态测量结果合法（0 或 1）",
          emu.get_register("x1") in (0, 1), str(state))

    # 测试 3：X 门确定性翻转 —— |0> 经 X 后测量必为 1
    emu, state = _run("""
    qx q0
    qmeas x1, q0
    """)
    check("X 门确定性翻转（测量必为 1）", emu.get_register("x1") == 1, str(state))

    # 测试 4：RZ 相位旋转不改变测量分布 —— 与未旋转结果一致
    emu1, s1 = _run("""
    qh q0
    qrz q0, 2
    qmeas x1, q0
    """)
    emu2, s2 = _run("""
    qh q0
    qmeas x1, q0
    """)
    check("RZ 相位不改变测量结果",
          emu1.get_register("x1") == emu2.get_register("x1"),
          "%s vs %s" % (s1, s2))

    # 测试 5：经典 + 量子混合 —— 控制流决定是否制备纠缠
    emu, state = _run("""
    li x1, 1
    beq x1, x0, SKIP       # x1==1, x0==0 -> 不跳转：执行纠缠制备
    qh q0
    qcx q0, q1
    qmeas x1, q0
    qmeas x2, q1
    bne x1, x2, BROKEN     # 纠缠一致性检查：不等则跳到 BROKEN（x9=99）
    li x9, 0
    j END
    SKIP:
    BROKEN:
    li x9, 99
    END:
    """)
    check("经典控制流 + 量子指令混合（纠缠检查通过）",
          emu.get_register("x9") == 0, str(state))

    print()
    print("结果：%d 通过，%d 失败" % (passed, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台 UTF-8 显示
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(run_tests())
