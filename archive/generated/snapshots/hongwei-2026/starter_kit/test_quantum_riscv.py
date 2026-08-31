#!/usr/bin/env python3
"""End-to-end tests for LoomQ custom-0 quantum RISC-V extension."""

from __future__ import annotations

from riscv_emulator import LOOMQ_CUSTOM0_OPCODE, TinyRISCVEmulator


BELL = """
qinit 2
qh x0
qcx x0, x1
qmeas x0, x10
qmeas x1, x11
"""


def test_classic_regression() -> None:
    code = """
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
    emu = TinyRISCVEmulator()
    emu.load_program(code)
    state = emu.execute()
    assert state.get("x3") == 16, state
    print("[ok] classic regression")


def test_encode() -> None:
    word = TinyRISCVEmulator.encode_custom("qh", rd=0, rs1=0, rs2=0)
    assert (word & 0x7F) == LOOMQ_CUSTOM0_OPCODE
    assert ((word >> 12) & 0x7) == 0b001
    cx = TinyRISCVEmulator.encode_custom("qcx", rd=0, rs1=0, rs2=1)
    assert ((cx >> 15) & 0x1F) == 0
    assert ((cx >> 20) & 0x1F) == 1
    print("[ok] custom-0 encoding", hex(word), hex(cx))


def test_bell_shots() -> None:
    emu = TinyRISCVEmulator()
    counts = emu.load_and_shot(BELL, 512)
    total = sum(counts.values())
    assert total == 512, counts
    p00 = counts.get("00", 0) / 512
    p11 = counts.get("11", 0) / 512
    assert p00 + p11 >= 0.85, counts
    print("[ok] bell shots", counts)


def test_single_x() -> None:
    prog = """
    qinit 1
    qx x0
    qmeas x0, x10
    """
    emu = TinyRISCVEmulator()
    emu.load_program(prog)
    emu.execute()
    assert emu.get_register("x10") == 1
    print("[ok] X then measure")


def main() -> int:
    test_classic_regression()
    test_encode()
    test_single_x()
    test_bell_shots()
    print("quantum RISC-V e2e passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
