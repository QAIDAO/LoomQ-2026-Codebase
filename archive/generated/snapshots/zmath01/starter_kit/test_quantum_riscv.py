#!/usr/bin/env python3
"""End-to-end tests for the LoomQ-Q quantum RISC-V extension (Bonus item 3).

Run:  python3 test_quantum_riscv.py
Exit code 0 = all tests passed.

Covered:
  1. deterministic superposition readout via qprob (no sampling noise)
  2. Bell pair: measurement correlation over repeated runs
  3. quantum->classical feedback: classical branch driven by a live
     measurement result inside one program (the thing the base emulator
     cannot do without external injection)
  4. error handling: out-of-range qubit access raises
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from riscv_emulator_ext import QuantumRISCVEmulator  # noqa: E402

FAILURES = 0


def check(label, ok, detail=""):
    global FAILURES
    print("[%s] %s %s" % ("PASS" if ok else "FAIL", label, detail))
    if not ok:
        FAILURES += 1


def test_qprob_deterministic():
    # |0> --H--> qprob == 500 (50.0%); after X, qprob == 1000.
    program = """
    li x1, 1
    qinit x1
    li x1, 0
    qprob x5, x1        # ground state: 0
    qh x1
    qprob x6, x1        # superposition: 500
    qx x1
    qprob x7, x1        # H|1> still 50/50: 500
    qx x1
    qx x1               # back to H|0>... no: X^2 = I, so still superposition
    qprob x8, x1
    """
    emu = QuantumRISCVEmulator(rng=random.Random(7))
    emu.load_program(program)
    state = emu.execute()
    check("qprob ground state", state.get("x5", 0) == 0, "x5=%s" % state.get("x5"))
    check("qprob superposition", state.get("x6") == 500, "x6=%s" % state.get("x6"))
    check("qprob after X", state.get("x7") == 500, "x7=%s" % state.get("x7"))
    check("qprob after X^2", state.get("x8") == 500, "x8=%s" % state.get("x8"))


def test_bell_correlation():
    program = """
    li x1, 2
    qinit x1
    li x1, 0
    li x2, 1
    qh x1
    qcx x1, x2
    qmeas x3, x1
    qmeas x4, x2
    """
    trials = 200
    rng = random.Random(42)
    correlated = 0
    ones = 0
    for _ in range(trials):
        emu = QuantumRISCVEmulator(rng=rng)
        emu.load_program(program)
        state = emu.execute()
        if state.get("x3", 0) == state.get("x4", 0):
            correlated += 1
        ones += state.get("x3", 0)
    check("bell correlation 100%", correlated == trials,
          "%d/%d" % (correlated, trials))
    check("bell marginal ~50%", 60 < ones < 140, "ones=%d/200" % ones)


def test_quantum_feedback():
    # Measure q0; if 1, set x5 = 100, else x5 = 10 -- classical control flow
    # driven by a live quantum measurement in a single program.
    program = """
    li x1, 1
    qinit x1
    li x1, 0
    qh x1
    qmeas x2, x1        # x2 = measurement of q0
    li x3, 1
    beq x2, x3, ONE
    li x5, 10
    j DONE
    ONE:
    li x5, 100
    DONE:
    """
    rng = random.Random(1)
    seen = set()
    for _ in range(100):
        emu = QuantumRISCVEmulator(rng=rng)
        emu.load_program(program)
        state = emu.execute()
        x2, x5 = state.get("x2", 0), state.get("x5", 0)
        consistent = (x2 == 1 and x5 == 100) or (x2 == 0 and x5 == 10)
        if not consistent:
            check("quantum feedback consistency", False, "x2=%s x5=%s" % (x2, x5))
            return
        seen.add(x2)
    check("quantum feedback consistency", True, "100 runs consistent")
    check("both branches exercised", seen == {0, 1}, "seen=%s" % seen)


def test_error_handling():
    emu = QuantumRISCVEmulator()
    emu.load_program("li x1, 1\nqinit x1\nli x2, 5\nqh x2\n")
    try:
        emu.execute()
    except RuntimeError:
        check("out-of-range qubit raises", True)
    else:
        check("out-of-range qubit raises", False, "no exception")


if __name__ == "__main__":
    test_qprob_deterministic()
    test_bell_correlation()
    test_quantum_feedback()
    test_error_handling()
    print()
    if FAILURES:
        print("FAILED: %d test(s)" % FAILURES)
        sys.exit(1)
    print("ALL QUANTUM RISC-V EXTENSION TESTS PASSED")
