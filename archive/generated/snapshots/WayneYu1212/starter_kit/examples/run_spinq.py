#!/usr/bin/env python3
"""Run the public Bell circuit through the real SpinQ adapter path."""

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
    print("--- SpinQ OpenQASM 2.0 ---")
    print(adapter.transpile(qasm, "spinq").strip())
    print("--- Real SpinQit BasicSimulator result ---")
    print(json.dumps(adapter.run(qasm, "spinq", 1024), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
