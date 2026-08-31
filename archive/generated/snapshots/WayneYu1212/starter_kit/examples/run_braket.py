#!/usr/bin/env python3
"""Run the public Bell circuit through emitted QASM3 and Braket LocalSimulator."""

from __future__ import annotations

import json
from pathlib import Path
import sys


STARTER_ROOT = Path(__file__).resolve().parents[1]
if str(STARTER_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTER_ROOT))

import adapter


def main() -> None:
    qasm = (STARTER_ROOT / "circuits" / "bell.qasm").read_text(encoding="utf-8")
    print("--- Braket OpenQASM 3 ---")
    print(adapter.transpile(qasm, "braket").strip())
    print("--- Real Braket LocalSimulator result ---")
    print(json.dumps(adapter.run(qasm, "braket", 1024), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
