#!/usr/bin/env python3
"""One-command test runner for the LoomQ parser (the `npm run test` of this repo).

Run from anywhere:

    python starter_kit/loomq/run_tests.py

Runs every test style and reports a combined result:
  1. the doctest examples embedded in parser.py's docstrings
  2. the assert-based checks in test_parser.py
  3. the emitter round-trip checks in test_emitters.py

Exit code 0 = everything green, 1 = something failed (so CI can gate on it).
No third-party dependencies.
"""

import doctest
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    failures = 0

    # 1) doctests living inside parser.py's docstrings.
    #    parser.py sits next to this file, so a plain import finds it.
    import parser

    result = doctest.testmod(parser, verbose=False)
    print(f"doctests     : {result.attempted - result.failed}/{result.attempted} passed")
    failures += result.failed

    # 2) the assert-based suites. Run each as a subprocess so its own PASS/FAIL
    #    lines print normally and its exit code tells us if anything failed.
    for name in ("test_parser.py", "test_emitters.py", "test_agent.py"):
        print(f"{name:13s}:")
        proc = subprocess.run([sys.executable, str(HERE / name)])
        if proc.returncode != 0:
            failures += 1

    print("\n" + ("ALL GREEN ✅" if failures == 0 else "FAILURES ABOVE ❌"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
