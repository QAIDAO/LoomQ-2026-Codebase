#!/usr/bin/env python3
"""Run the LoomQ custom quantum RISC-V extension as encoded 32-bit words."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starter_kit.riscv_emulator import TinyRISCVEmulator, encode_quantum_instruction


OPERATIONS = (
    ("qinit", (0,)),
    ("qinit", (1,)),
    ("qh", (0,)),
    ("qcx", (0, 1)),
    ("qmeasure", (0, 0)),
    ("qmeasure", (1, 0)),
)


def main() -> int:
    assembly = "\n".join(
        f".word 0x{encode_quantum_instruction(name, *operands):08x}"
        for name, operands in OPERATIONS
    )
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    emulator.execute()
    print(json.dumps(emulator.quantum_trace, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
