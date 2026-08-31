#!/usr/bin/env python3
"""Extra local stress tests beyond the public evaluator."""

from __future__ import annotations

import os
import sys

import adapter
from loomq_core import compile_hybrid_program
from riscv_emulator import TinyRISCVEmulator


def check_l1(path: str, targets=("spinq", "originq", "braket"), shots=2048) -> None:
    qasm = open(path, encoding="utf-8").read()
    for target in targets:
        native = adapter.transpile(qasm, target)
        assert native.strip(), target
        result = adapter.run(qasm, target, shots)
        assert result["bit_order"] == "little"
        assert sum(result["counts"].values()) == shots
        print("[ok] l1", os.path.basename(path), target, "keys=", sorted(result["counts"])[:4])


def check_l3() -> None:
    source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
classical {
  if (c[0] == 1) {
    if (c[1] != 0) { r1 = 9; } else { r1 = 4; }
  } else {
    r1 = 1;
  }
  r1 = r1 + 5;
  r2 = r1 - 2;
}
"""
    _ops, asm = compile_hybrid_program(source)
    expectations = {
        (0, 0): (6, 4),   # r1=1+5=6, r2=4
        (1, 0): (9, 7),   # r1=4+5=9
        (0, 1): (6, 4),
        (1, 1): (14, 12), # r1=9+5=14
    }
    for (c0, c1), (x1, x2) in expectations.items():
        emu = TinyRISCVEmulator()
        emu.load_program(asm)
        emu.set_register("x10", c0)
        emu.set_register("x11", c1)
        state = emu.execute()
        assert state.get("x1", 0) == x1, (c0, c1, state, x1)
        assert state.get("x2", 0) == x2, (c0, c1, state, x2)
        print("[ok] l3 nested", c0, c1, state)


def check_recommend() -> None:
    from loomq_agent import load_backends, recommend_reply

    text, ids = recommend_reply("我需要运行一个 15 比特电路，且零排队等待，选哪个平台？", load_backends())
    assert any(
        i in ids
        for i in (
            "spinq_taurus_simulator",
            "originq_local_simulator",
            "braket_local_simulator",
        )
    ), ids
    print("[ok] recommend", ids)


def main() -> int:
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "circuits")
    for name in ("bell.qasm", "ghz3.qasm", "ghz5.qasm", "bell_plus.qasm"):
        check_l1(os.path.join(base, name))
    check_l3()
    check_recommend()
    print("all stress tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
