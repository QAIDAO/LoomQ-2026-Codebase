#!/usr/bin/env python3
"""Q-extension 端到端测试。

验证自定义量子 RISC-V 指令的编码、执行与量子轨迹，并打通与 L1 模拟器的闭环。
运行：python3 qisa_test.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapter import run  # noqa: E402
from qriscv_emulator import QuantumRISCVEmulator  # noqa: E402


def test_trace_and_classic():
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
    assert emu.quantum_trace == [
        "h q[0]",
        "cx q[0],q[1]",
        "measure q[0] -> c[0]",
        "measure q[1] -> c[1]",
    ], emu.quantum_trace
    assert state.get("x1") == 6
    print("[OK] test_trace_and_classic")


def test_measurement_injection():
    code = """
    qmeasure x0, x0
    qmeasure x1, x1
    li x2, 100
    """
    emu = QuantumRISCVEmulator()
    emu.measurement_inputs = [1, 0]
    emu.load_program(code)
    state = emu.execute()
    assert state.get("x10") == 1
    assert state.get("x11", 0) == 0
    assert state.get("x2") == 100
    print("[OK] test_measurement_injection")


def test_quantum_classic_branch():
    code = """
    qmeasure x0, x0
    li x20, 1
    bne x10, x20, .Lelse
    li x1, 100
    j .Lend
    .Lelse:
    li x1, 10
    .Lend:
    """
    for measured, expected in ((1, 100), (0, 10)):
        emu = QuantumRISCVEmulator()
        emu.measurement_inputs = [measured]
        emu.load_program(code)
        state = emu.execute()
        assert state.get("x1") == expected
    print("[OK] test_quantum_classic_branch")


def test_end_to_end_qasm():
    code = """
    qh x0
    qcx x1, x0
    qmeasure x0, x0
    qmeasure x1, x1
    """
    emu = QuantumRISCVEmulator()
    emu.load_program(code)
    emu.execute()

    body = "\n".join(line + ";" for line in emu.quantum_trace)
    qasm = (
        'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\n'
        + body
        + "\n"
    )
    counts = run(qasm, "braket", 8192)["counts"]
    assert set(counts) == {"00", "11"}, counts
    assert abs(counts["00"] - counts["11"]) < 8192 * 0.15
    print("[OK] test_end_to_end_qasm:", counts)


if __name__ == "__main__":
    test_trace_and_classic()
    test_measurement_injection()
    test_quantum_classic_branch()
    test_end_to_end_qasm()
    print("Q-extension 全部端到端测试通过！")
