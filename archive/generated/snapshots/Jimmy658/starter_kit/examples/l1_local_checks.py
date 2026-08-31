#!/usr/bin/env python3
"""Extra local L1 checks for the LoomQ adapter.

These checks are not official scores. They cover cases that the public
evaluator does not expose well: bit order, parameter parsing, and every
whitelisted gate at least once.
"""

from __future__ import annotations

import os
import subprocess
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import adapter  # noqa: E402


SHOTS = 64


CASES = {
    "bit_order": (
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
x q[0];
measure q -> c;
""",
        {"001": SHOTS},
    ),
    "ry_pi": (
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
ry(pi) q[0];
measure q -> c;
""",
        {"1": SHOTS},
    ),
    "swap": (
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[0];
swap q[0],q[1];
measure q -> c;
""",
        {"10": SHOTS},
    ),
    "ccx": (
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
x q[0];
x q[1];
ccx q[0],q[1],q[2];
measure q -> c;
""",
        {"111": SHOTS},
    ),
    "inverse_phase_pair": (
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
s q[0];
sdg q[0];
t q[0];
tdg q[0];
h q[0];
measure q -> c;
""",
        {"0": SHOTS},
    ),
    "rz_pi_interference": (
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
rz(pi) q[0];
h q[0];
measure q -> c;
""",
        {"1": SHOTS},
    ),
    "cu1_phase_kick": (
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
x q[1];
cu1(pi) q[0],q[1];
h q[0];
measure q -> c;
""",
        {"11": SHOTS},
    ),
    "barrier_is_ignored": (
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
barrier q;
x q[0];
measure q -> c;
""",
        {"1": SHOTS},
    ),
}


def assert_counts(name: str, qasm: str, expected: dict[str, int]) -> None:
    for target in adapter.SUPPORTED_TARGETS:
        native = adapter.transpile(qasm, target)
        if not native.strip():
            raise AssertionError(f"{name}:{target} produced empty transpile output")
        result = adapter.run(qasm, target, SHOTS)
        counts = result["counts"]
        if counts != expected:
            raise AssertionError(f"{name}:{target} expected {expected}, got {counts}")


def main() -> int:
    print("Running official public L1 evaluator...")
    completed = subprocess.run(
        [
            sys.executable,
            "evaluator.py",
            "--level",
            "l1",
            "--target",
            "spinq,originq,braket",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    print(completed.stdout.strip())
    if completed.returncode != 0:
        print(completed.stderr, file=sys.stderr)
        return completed.returncode

    print("Running extra deterministic L1 checks...")
    for name, (qasm, expected) in CASES.items():
        assert_counts(name, qasm, expected)
        print(f"[PASS] {name}")
    print("All extra L1 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
