#!/usr/bin/env python3
"""End-to-end test for the Bonus quantum RISC-V extension."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from riscv_emulator import TinyRISCVEmulator


def test_bell_correlation() -> None:
    code = """
    li x1, 0
    li x2, 1
    qh x1
    qcx x1, x2
    qmeas x1, x3
    qmeas x2, x4
    """
    emu = TinyRISCVEmulator()
    emu.load_program(code)
    state = emu.execute()
    assert state.get("x3", 0) == state.get("x4", 0)


def test_classical_still_works() -> None:
    code = """
    li x1, 5
    li x2, 10
    add x3, x1, x2
    """
    emu = TinyRISCVEmulator()
    emu.load_program(code)
    assert emu.execute().get("x3") == 15


if __name__ == "__main__":
    test_bell_correlation()
    test_classical_still_works()
    print("quantum RISC-V bonus tests passed")
