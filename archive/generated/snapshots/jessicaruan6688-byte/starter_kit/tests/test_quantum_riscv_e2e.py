#!/usr/bin/env python3
"""End-to-end tests for LoomQ QISA v1 (custom quantum RISC-V Bonus).

Run:
  PYTHONPATH=starter_kit python starter_kit/tests/test_quantum_riscv_e2e.py

RNG: TinyRISCVEmulator defaults to seed=42 (documented in LOOMQ_QISA_V1.md).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from riscv_emulator import (  # noqa: E402
    CUSTOM0_OPCODE,
    TinyRISCVEmulator,
    assemble_quantum_program_words,
    assemble_quantum_word,
    decode_quantum_word,
    decoded_to_op_args,
)

BELL_ASM = """
# Bell |Φ+>; seed=42 by default
qinit 2
qh 0
qcx 0, 1
qmeas 0, x10
qmeas 1, x11
"""

CLASSICAL_ASM = """
li x1, 5
li x2, 7
add x3, x1, x2
addi x4, x3, -2
mv x5, x4
"""


def test_encode_decode_roundtrip() -> None:
    cases = [
        ("qinit", {"qs1": 2}),
        ("qh", {"qs1": 0}),
        ("qx", {"qs1": 1}),
        ("qcx", {"qs1": 0, "qs2": 1}),
        ("qmeas", {"qs1": 0, "rd": 10}),
    ]
    for mnemonic, fields in cases:
        word = assemble_quantum_word(mnemonic, **fields)
        decoded = decode_quantum_word(word)
        assert decoded["opcode"] == CUSTOM0_OPCODE
        assert decoded["mnemonic"] == mnemonic
        assert decoded["qs1"] == fields.get("qs1", 0)
        assert decoded["qs2"] == fields.get("qs2", 0)
        assert decoded["rd"] == fields.get("rd", 0)
        # Re-assemble must match exactly
        again = assemble_quantum_word(
            decoded["mnemonic"],
            qs1=decoded["qs1"],
            qs2=decoded["qs2"],
            rd=decoded["rd"],
            funct7=decoded["funct7"],
        )
        assert again == word, (mnemonic, hex(word), hex(again))


def test_bell_correlated_seeded() -> None:
    """Single seeded shot: outcomes must be perfectly correlated."""
    emu = TinyRISCVEmulator(rng_seed=42)
    emu.load_program(BELL_ASM)
    state = emu.execute()
    b0 = state.get("x10", 0)
    b1 = state.get("x11", 0)
    assert b0 in (0, 1) and b1 in (0, 1)
    assert b0 == b1, f"Bell outcomes not correlated: x10={b0} x11={b1}"


def test_bell_multi_shot_consistency() -> None:
    """Many shots with a fixed seed stream: always x10==x11; both values appear.

    Uses independent emulators with seeds 42..42+N-1 so each run is
    reproducible, and checks deterministic post-measure correlation.
    """
    outcomes = []
    for seed in range(42, 42 + 40):
        emu = TinyRISCVEmulator(rng_seed=seed)
        emu.load_program(BELL_ASM)
        state = emu.execute()
        b0 = state.get("x10", 0)
        b1 = state.get("x11", 0)
        assert b0 == b1, f"seed={seed}: x10={b0} x11={b1}"
        outcomes.append(b0)
    assert 0 in outcomes and 1 in outcomes, outcomes

    # Same seed => identical measurement (deterministic collapse under fixed RNG)
    a = TinyRISCVEmulator(rng_seed=7)
    a.load_program(BELL_ASM)
    sa = a.execute()
    b = TinyRISCVEmulator(rng_seed=7)
    b.load_program(BELL_ASM)
    sb = b.execute()
    assert sa.get("x10", 0) == sb.get("x10", 0)
    assert sa.get("x11", 0) == sb.get("x11", 0)


def test_classical_l3_style_still_runs() -> None:
    emu = TinyRISCVEmulator()
    emu.load_program(CLASSICAL_ASM)
    state = emu.execute()
    assert state.get("x1") == 5
    assert state.get("x2") == 7
    assert state.get("x3") == 12
    assert state.get("x4") == 10
    assert state.get("x5") == 10

    # Smoke the original built-in smoke path style (branch + add)
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
    emu.load_program(code)
    state = emu.execute()
    assert state.get("x3") == 16


def test_bell_via_machine_words_closed_loop() -> None:
    """Organizer Q3 direction 1: CUSTOM-0 words must enter the live pipeline.

    Pipeline: assemble fields → 32-bit words → load_machine_words (decode) → execute.
    Text ``load_program`` remains for L3 classical / human-readable asm.
    """
    steps = [
        ("qinit", {"qs1": 2}),
        ("qh", {"qs1": 0}),
        ("qcx", {"qs1": 0, "qs2": 1}),
        ("qmeas", {"qs1": 0, "rd": 10}),
        ("qmeas", {"qs1": 1, "rd": 11}),
    ]
    words = assemble_quantum_program_words(steps)
    assert len(words) == 5
    assert all(isinstance(w, int) for w in words)
    # Spot-check first word is CUSTOM-0
    assert (words[0] & 0x7F) == CUSTOM0_OPCODE

    # decode → (op, args) must match intent before execute
    op0, args0 = decoded_to_op_args(decode_quantum_word(words[0]))
    assert op0 == "qinit" and args0 == ["2"]
    op_cx, args_cx = decoded_to_op_args(decode_quantum_word(words[2]))
    assert op_cx == "qcx" and args_cx == ["0", "1"]
    op_m, args_m = decoded_to_op_args(decode_quantum_word(words[3]))
    assert op_m == "qmeas" and args_m == ["0", "x10"]

    emu = TinyRISCVEmulator(rng_seed=42)
    emu.load_machine_words(words)
    assert emu.machine_words == words
    state = emu.execute()
    assert state.get("x10", 0) == state.get("x11", 0)

    # Same seed + same words ⇒ identical classical outcomes
    emu2 = TinyRISCVEmulator(rng_seed=42)
    emu2.load_machine_words(words)
    state2 = emu2.execute()
    assert state2.get("x10") == state.get("x10")
    assert state2.get("x11") == state.get("x11")


def main() -> int:
    tests = [
        test_encode_decode_roundtrip,
        test_bell_correlated_seeded,
        test_bell_multi_shot_consistency,
        test_classical_l3_style_still_runs,
        test_bell_via_machine_words_closed_loop,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"[FAIL] {test.__name__}: {exc}")
        else:
            print(f"[PASS] {test.__name__}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
