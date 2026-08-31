"""End-to-end Bell-pair demonstration for the Bonus quantum RISC-V ISA."""

from __future__ import annotations

import json

from .emulator import QuantumRISCVEmulator


BELL_PROGRAM = """
# GPR x1..x3 carry qubit indices; x10 carries QINIT size.
li x1, 0
li x2, 1
li x3, 2
li x10, 3
li x11, 102944

# Exercise QINIT and an active Toffoli (target qubit becomes 1).
qinit x10
qx x1
qx x2
qccx x1, x2, x3
qmeasure x5, x3

# Reinitialize, exercise parameterized rotations and SWAP, then make Bell pair.
qinit x10
qry x3, x11
qrz x3, x11
qswap x2, x3
qswap x2, x3
qh x1
qcx x1, x2
qmeasure x20, x1
qmeasure x21, x2
"""


def main() -> int:
    emulator = QuantumRISCVEmulator(seed=2026)
    emulator.load_program(BELL_PROGRAM)
    emulator.execute()
    report = emulator.execution_report()
    first = emulator.get_register("x20")
    second = emulator.get_register("x21")
    report["toffoli_target_check"] = emulator.get_register("x5") == 1
    report["bell_correlation_check"] = first == second
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if first == second and report["toffoli_target_check"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
