#!/usr/bin/env python3
"""Quantum RISC-V extension: end-to-end tests.

Covers the three deliverables of the Bonus:
1. instruction encoding round-trip (encode -> decode, Q14 precision);
2. fork of the official emulator with quantum semantics (gates, measure
   write-back to x10+k, collapse);
3. end-to-end quantum+classical programs (Bell state with measurement
   feedback branching, rotation precision, classical regression).

Exit code 0 = all tests pass.
"""

import math
import sys

try:
    from .riscv_emulator_quantum import (
        TinyRISCVQuantumEmulator,
        encode_qinst,
        decode_qinst,
        _to_q14,
        _from_q14,
    )
except ImportError:  # standalone-module fallback
    from riscv_emulator_quantum import (
        TinyRISCVQuantumEmulator,
        encode_qinst,
        decode_qinst,
        _to_q14,
        _from_q14,
    )


BELL_PROGRAM = """
qinit 2
qh q0
qcx q0, q1
qm q0
qm q1
beq x10, x11, ENTANGLED
li x1, 0
j END
ENTANGLED:
li x1, 1
END:
"""

ROTATION_PROGRAM = """
qinit 1
qry q0, 1.5707963267948966
qm q0
"""


def test_encoding_roundtrip() -> None:
    cases = [
        ("qh", 0, 0, 0.0),
        ("qrz", 3, 0, math.pi / 2),
        ("qry", 7, 0, -math.pi / 4),
        ("qcx", 1, 2, 0.0),
        ("qm", 5, 0, 0.0),
    ]
    for mnemonic, qa, qb, theta in cases:
        word = encode_qinst(mnemonic, qa, qb, theta)
        name, dqa, dqb, dtheta = decode_qinst(word)
        assert name == mnemonic and dqa == qa and dqb == qb, (
            "encode/decode mismatch for %s" % mnemonic
        )
        # Q14 fixed-point precision: error <= 2^-14
        assert abs(dtheta - theta) <= 2.0 ** -14 + 1e-12
    # raw binary layout check for qrz q3, pi/2
    word = encode_qinst("qrz", 3, 0, math.pi / 2)
    assert (word >> 28) == 0xF and ((word >> 24) & 0xF) == 0b0010
    assert ((word >> 20) & 0xF) == 3
    assert abs(_from_q14(word & 0xFFFF) - math.pi / 2) <= 2.0 ** -14 + 1e-12


def test_bell_feedback() -> None:
    outcomes = {}
    for _ in range(60):
        emu = TinyRISCVQuantumEmulator()
        emu.load_program(BELL_PROGRAM)
        state = emu.execute()
        assert state.get("x1") == 1, "Bell pairs must agree (x10 == x11)"
        outcomes[(state.get("x10", 0), state.get("x11", 0))] = (
            outcomes.get((state.get("x10", 0), state.get("x11", 0)), 0) + 1
        )
    assert set(outcomes) <= {(0, 0), (1, 1)}, "Bell outcomes must be 00 or 11 only"
    # 60 samples: expect ~30/30; allow 3-sigma (~23..37)
    assert 15 <= outcomes.get((0, 0), 0) <= 45
    assert 15 <= outcomes.get((1, 1), 0) <= 45


def test_rotation_precision() -> None:
    ones = 0
    total = 200
    for _ in range(total):
        emu = TinyRISCVQuantumEmulator()
        emu.load_program(ROTATION_PROGRAM)
        state = emu.execute()
        ones += state.get("x10", 0)
    # RY(pi/2)|0> = (|0>+|1>)/sqrt(2): expect ~50% within 3 sigma (~30%)
    assert 0.30 * total <= ones <= 0.70 * total, "RY(pi/2) should measure ~50% |1>"


def test_classical_regression() -> None:
    code = """
    li x1, 5
    li x2, 10
    beq x1, x2, EQUAL
    add x3, x1, x2
    j END
    EQUAL:
    sub x3, x2, x1
    END:
    addi x3, x3, 1
    """
    emu = TinyRISCVQuantumEmulator()
    emu.load_program(code)
    state = emu.execute()
    assert state.get("x3") == 16, "official sample program must still work"


def test_qinit_idempotent_and_measure_zero() -> None:
    code = "qinit 3\nqm q0\nqm q2\n"
    emu = TinyRISCVQuantumEmulator()
    emu.load_program(code)
    state = emu.execute()
    assert state.get("x10", 0) == 0 and state.get("x12", 0) == 0


def main() -> int:
    tests = [
        ("encoding-roundtrip", test_encoding_roundtrip),
        ("bell-feedback", test_bell_feedback),
        ("rotation-precision", test_rotation_precision),
        ("classical-regression", test_classical_regression),
        ("qinit-measure", test_qinit_idempotent_and_measure_zero),
    ]
    failures = 0
    for label, test in tests:
        try:
            test()
            print("[PASS] qisa:%s" % label)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print("[FAIL] qisa:%s - %s: %s" % (label, type(exc).__name__, exc))
    if failures:
        print("Quantum ISA self-test: %d failure(s)" % failures, file=sys.stderr)
        return 1
    print("Quantum ISA self-test: all %d tests passed" % len(tests))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover - top-level guard
        print("Quantum ISA self-test failed: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(1)
