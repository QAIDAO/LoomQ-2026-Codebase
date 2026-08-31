#!/usr/bin/env python3
"""LoomQ Quantum RISC-V 扩展端到端测试。

运行：python3 starter_kit/test_quantum_riscv.py

覆盖：官方经典指令回归、编码往返、Bell 态、中路测量反馈、参数门、Toffoli。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quantum_riscv_emulator import (  # noqa: E402
    QuantumRISCVEmulator,
    assemble,
    decode,
    encode,
)
from riscv_emulator import TinyRISCVEmulator  # noqa: E402

PASSED = 0
FAILED = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] {label}")
    else:
        FAILED += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


def approx(actual: float, expected: float, tolerance: float = 1e-9) -> bool:
    return abs(actual - expected) <= tolerance


# --- §1 官方经典指令回归 ----------------------------------------------------

def test_classical_regression() -> None:
    print("\n§1 官方经典指令回归（扩展模拟器不得改变原有语义）")
    program = """
    li x1, 5
    li x2, 10
    beq x1, x2, EQUAL
    add x3, x1, x2
    j END
    EQUAL:
    sub x3, x2, x1
    END:
    addi x3, x3, 1
    """
    official = TinyRISCVEmulator()
    official.load_program(program)
    official_state = official.execute()

    extended = QuantumRISCVEmulator()
    extended.load_program(program)
    extended_state = extended.execute()

    check("官方模拟器结果 x3 == 16", official_state.get("x3") == 16, str(official_state))
    check(
        "扩展模拟器与官方逐寄存器一致",
        official_state == extended_state,
        f"official={official_state} extended={extended_state}",
    )


# --- §2 编码往返 ------------------------------------------------------------

def test_encoding() -> None:
    print("\n§2 编码往返与规格文档示例一致性")

    # ISA §4 示例一：qgate2 cx, 0, 1
    word = assemble("qgate2", ["cx", "0", "1"])
    check("qgate2 cx,0,1 编码 == 0x0010200B", word == 0x0010200B, f"got 0x{word:08X}")
    funct3, funct7, rs1, rs2, rd = decode(word)
    check(
        "解码字段正确 (funct3=2, funct7=0, rs1=0, rs2=1)",
        (funct3, funct7, rs1, rs2, rd) == (0b010, 0, 0, 1, 0),
        str((funct3, funct7, rs1, rs2, rd)),
    )

    # ISA §4 示例二：qmeas x10, 0
    word = assemble("qmeas", ["x10", "0"])
    check("qmeas x10,0 编码 == 0x0000450B", word == 0x0000450B, f"got 0x{word:08X}")
    funct3, funct7, rs1, rs2, rd = decode(word)
    check("解码 rd == 10 且 funct3 == 4", (rd, funct3) == (10, 0b100), str((rd, funct3)))

    # opcode 必须落在 custom-0，不与标准指令冲突
    for mnemonic, args in (
        ("qinit", ["3"]), ("qgate", ["h", "0"]), ("qccx", ["0", "1", "2"]),
        ("qsetp", ["x5"]), ("qrot", ["rz", "1"]),
    ):
        code = assemble(mnemonic, args)
        check(f"{mnemonic} opcode == 0x0B", code & 0x7F == 0x0B, f"0x{code:08X}")

    # 全字段往返
    original = (0b1010101, 17, 9, 0b011, 22)
    check("encode/decode 全字段往返", decode(encode(*original))
          == (original[3], original[0], original[2], original[1], original[4]))

    # 非法输入必须报错
    try:
        assemble("qgate", ["nosuchgate", "0"])
        check("未知门名应报错", False, "未抛异常")
    except ValueError:
        check("未知门名应报错", True)
    try:
        decode(0x00000013)  # addi x0,x0,0 — 标准 RV32I
        check("标准指令应被拒绝", False, "未抛异常")
    except ValueError:
        check("标准指令应被拒绝", True)


# --- §3 Bell 态 -------------------------------------------------------------

def test_bell_state() -> None:
    print("\n§3 Bell 态：量子门在指令流中执行")
    emulator = QuantumRISCVEmulator(seed=7)
    emulator.load_program("""
    qinit  2
    qgate  h, 0
    qgate2 cx, 0, 1
    """)
    emulator.execute()
    probabilities = emulator.quantum.probabilities()
    check("仅 |00> 与 |11> 有幅值", set(probabilities) == {"00", "11"}, str(probabilities))
    check("P(00) == 0.5", approx(probabilities.get("00", 0), 0.5), str(probabilities))
    check("P(11) == 0.5", approx(probabilities.get("11", 0), 0.5), str(probabilities))


# --- §4 中路测量反馈（本扩展的核心能力）------------------------------------

def test_midcircuit_feedback() -> None:
    print("\n§4 中路测量反馈：测量结果驱动经典分支，再驱动量子门")
    program = """
    qinit  2
    qgate  h, 0
    qmeas  x10, 0
    bne    x10, x0, RESET
    j      DONE
    RESET:
    qgate  x, 0
    DONE:
    qgate2 cx, 0, 1
    qmeas  x11, 1
    """
    # 无论 q[0] 测得 0 还是 1，RESET 分支都应把它带回 |0>，
    # 因此 q[1] 经 CNOT 后必然测得 0 —— 确定性结果。
    for forced in (0, 1):
        emulator = QuantumRISCVEmulator(seed=1)
        emulator.load_program(program)
        emulator.set_forced_measurements({0: forced})
        state = emulator.execute()
        check(
            f"q[0] 测得 {forced} 时 x10 == {forced}",
            state.get("x10", 0) == forced,
            str(state),
        )
        check(
            f"q[0] 测得 {forced} 后经反馈校正，q[1] 必为 0",
            state.get("x11", 0) == 0,
            f"x11={state.get('x11', 0)} log={emulator.measurement_log}",
        )


# --- §5 参数门 --------------------------------------------------------------

def test_parametric() -> None:
    print("\n§5 参数门：经典寄存器运算产生旋转角（毫弧度）")
    # ry(pi) 把 |0> 完全翻到 |1>；pi ≈ 3142 毫弧度。
    # 角度由经典算术在运行时算出：3000 + 142。
    emulator = QuantumRISCVEmulator(seed=3)
    emulator.load_program("""
    qinit  1
    li     x5, 3000
    addi   x5, x5, 142
    qsetp  x5
    qrot   ry, 0
    qmeas  x10, 0
    """)
    state = emulator.execute()
    check("QPARAM 由经典算术得到 3142", emulator.qparam_milliradians == 3142,
          str(emulator.qparam_milliradians))
    check("theta 换算为弧度 ≈ pi", approx(emulator.theta, 3.142, 1e-9),
          str(emulator.theta))
    check("ry(pi)|0> 测量必为 1", state.get("x10", 0) == 1, str(state))

    # rz 只改相位，不改测量分布
    emulator = QuantumRISCVEmulator(seed=3)
    emulator.load_program("""
    qinit  1
    qgate  h, 0
    li     x5, 1571
    qsetp  x5
    qrot   rz, 0
    """)
    emulator.execute()
    probabilities = emulator.quantum.probabilities()
    check("rz 不改变测量概率", approx(probabilities.get("0", 0), 0.5)
          and approx(probabilities.get("1", 0), 0.5), str(probabilities))


# --- §6 Toffoli 与 GHZ ------------------------------------------------------

def test_ccx_and_ghz() -> None:
    print("\n§6 Toffoli（目标位编码于 funct7）与 GHZ-3")
    # |110> --ccx--> |111>：q[0]=0? 小端下 |110> 指 q2=1,q1=1,q0=0。
    # 取控制位 q[1],q[2] 均为 1，目标 q[0] 应被翻转为 1。
    emulator = QuantumRISCVEmulator(seed=5)
    emulator.load_program("""
    qinit 3
    qgate x, 1
    qgate x, 2
    qccx  1, 2, 0
    """)
    emulator.execute()
    probabilities = emulator.quantum.probabilities()
    check("ccx 将 |110> 翻为 |111>", set(probabilities) == {"111"}, str(probabilities))

    emulator = QuantumRISCVEmulator(seed=5)
    emulator.load_program("""
    qinit  3
    qgate  h, 0
    qgate2 cx, 0, 1
    qgate2 cx, 0, 2
    """)
    emulator.execute()
    probabilities = emulator.quantum.probabilities()
    check("GHZ-3 只有 |000> 与 |111>", set(probabilities) == {"000", "111"},
          str(probabilities))
    check("GHZ-3 两态各占一半",
          approx(probabilities.get("000", 0), 0.5)
          and approx(probabilities.get("111", 0), 0.5), str(probabilities))

    # swap
    emulator = QuantumRISCVEmulator(seed=5)
    emulator.load_program("""
    qinit  2
    qgate  x, 0
    qgate2 swap, 0, 1
    """)
    emulator.execute()
    check("swap 把 |01> 换成 |10>",
          set(emulator.quantum.probabilities()) == {"10"},
          str(emulator.quantum.probabilities()))


# --- §7 测量塌缩一致性 ------------------------------------------------------

def test_collapse() -> None:
    print("\n§7 测量塌缩：重复测量同一比特必得相同结果")
    emulator = QuantumRISCVEmulator(seed=11)
    emulator.load_program("""
    qinit 1
    qgate h, 0
    qmeas x10, 0
    qmeas x11, 0
    qmeas x12, 0
    """)
    state = emulator.execute()
    first = state.get("x10", 0)
    check("三次测量结果一致（态矢已塌缩）",
          state.get("x11", 0) == first and state.get("x12", 0) == first,
          str(state))

    # 统计检验：h 之后大量采样应接近半分
    ones = 0
    trials = 400
    for trial in range(trials):
        emulator = QuantumRISCVEmulator(seed=trial)
        emulator.load_program("qinit 1\nqgate h, 0\nqmeas x10, 0")
        ones += emulator.execute().get("x10", 0)
    check(f"400 次采样中 1 的比例 ≈ 0.5（实测 {ones / trials:.3f}）",
          0.40 <= ones / trials <= 0.60, f"{ones}/{trials}")


def main() -> int:
    print("=" * 66)
    print("LoomQ Quantum RISC-V 扩展 (LQ-Q v1.0) 端到端测试")
    print("=" * 66)
    test_classical_regression()
    test_encoding()
    test_bell_state()
    test_midcircuit_feedback()
    test_parametric()
    test_ccx_and_ghz()
    test_collapse()
    print("\n" + "=" * 66)
    print(f"结果：{PASSED} passed, {FAILED} failed")
    print("=" * 66)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
