#!/usr/bin/env python3
"""Run the Bell circuit through LoomQ's SpinQ-compatible local path."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adapter  # noqa: E402


def main() -> None:
    qasm = (Path(__file__).resolve().parents[1] / "circuits" / "bell.qasm").read_text(encoding="utf-8")
    print("--- SpinQ OpenQASM 2.0 ---")
    print(adapter.transpile(qasm, "spinq"))
    print("--- Unified local result ---")
    print(json.dumps(adapter.run(qasm, "spinq", 1024), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
