#!/usr/bin/env python3
"""One-command, dependency-free submission verification."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(label: str, command: list[str]) -> None:
    print(f"\n=== {label} ===", flush=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-l2", action="store_true", help="also call the configured live L2 model")
    args = parser.parse_args()
    run("submission-contained tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run("public L1 / all targets", [sys.executable, "evaluator.py", "--level", "l1", "--target", "spinq,originq,braket"])
    run("public L3", [sys.executable, "evaluator.py", "--level", "l3"])
    if args.with_l2:
        missing = [name for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL") if not os.environ.get(name)]
        if missing:
            raise SystemExit("--with-l2 requires: " + ", ".join(missing))
        run("public L2 / configured model", [sys.executable, "evaluator.py", "--level", "l2"])
    print("\nAll requested LoomQ verification layers passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
