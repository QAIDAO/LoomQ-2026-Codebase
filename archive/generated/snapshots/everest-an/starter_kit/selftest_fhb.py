#!/usr/bin/env python3
"""FHB closed-form self-test for the LoomQ L1 transpiler.

Runs the Fuxi Hypercube Benchmark through transpile + run on all three
targets and checks the counts against the exact reference distributions
(uniform at t = pi/4, exact return at t = pi). Because FHB needs no
classical simulation for ground truth, this is a fast zero-dependency
regression net for the whole L1 pipeline.

Exit code 0 = all assertions passed.
"""

import math
import sys

try:
    from .fhb_ref import check_fhb_circuit
except ImportError:  # standalone-module fallback
    from fhb_ref import check_fhb_circuit


THRESHOLD = 0.97  # same bar as the organizer's evaluator
SHOTS = 32768  # enough sampling headroom for the 64-outcome uniform case


def assert_native_format(native: str, target: str, case: str) -> None:
    checks = {
        "spinq": ("OPENQASM 2.0",),
        "braket": ("OPENQASM 3.0", "stdgates.inc"),
        "originq": ("QINIT",),
    }
    for marker in checks[target]:
        if marker not in native:
            raise AssertionError("%s: %s transpile missing %r" % (case, target, marker))


def main() -> int:
    failures = 0
    for label, n, t in (
        ("uniform-mix", 6, math.pi / 4),
        ("exact-return", 6, math.pi),
    ):
        results = check_fhb_circuit(n, t, shots=SHOTS)
        for target, entry in results.items():
            fidelity = entry["fidelity"]
            try:
                assert fidelity >= THRESHOLD, (
                    "fidelity %.4f < %.2f" % (fidelity, THRESHOLD)
                )
                assert_native_format(entry["native"], target, label)
            except AssertionError as exc:
                failures += 1
                print("[FAIL] fhb:%s:%s - %s" % (label, target, exc))
                continue
            print(
                "[PASS] fhb:%s:%s fidelity=%.6f shots=%d"
                % (label, target, fidelity, entry["payload"]["shots"])
            )
    if failures:
        print("FHB self-test: %d failure(s)" % failures, file=sys.stderr)
        return 1
    print("FHB self-test: all %d target-cases passed" % 6)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover - top-level guard
        print("FHB self-test failed: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(1)
