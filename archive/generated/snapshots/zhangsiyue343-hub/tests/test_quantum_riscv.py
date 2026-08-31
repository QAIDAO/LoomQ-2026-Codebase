"""End-to-end tests for the custom quantum RISC-V extension (Bonus).

Covers: Bell/GHZ correlation statistics, encode/decode round-trips,
mixed classical-quantum control flow, and error paths.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "starter_kit"))

from quantum_riscv import (QuantumTinyRISCVEmulator, CUSTOM_OPCODE, decode,
                           encode)

BELL = """
li    x5, 0
qh    x5
li    x6, 1
qcx   x5, x6
qmeas x5, x10
qmeas x6, x11
"""

GHZ3 = """
li    x5, 0
qh    x5
li    x6, 1
qcx   x5, x6
li    x7, 2
qcx   x6, x7
qmeas x5, x10
qmeas x6, x11
qmeas x7, x12
"""


def _shots(asm: str, n_qubits: int, count: int):
    outcomes = []
    for seed in range(count):
        emu = QuantumTinyRISCVEmulator(n_qubits=n_qubits, seed=seed)
        emu.load_program(asm)
        state = emu.execute()
        outcomes.append(tuple(state.get("x%d" % r, 0)
                              for r in range(10, 10 + n_qubits)))
    return outcomes


class TestBellStatistics(unittest.TestCase):
    def test_only_correlated_outcomes(self):
        shots = _shots(BELL, 2, 400)
        distinct = set(shots)
        self.assertEqual(distinct, {(0, 0), (1, 1)})
        ones = sum(1 for s in shots if s == (1, 1))
        # seeded but still must be a healthy split, not degenerate
        self.assertTrue(150 < ones < 350, "suspicious split: %d/400" % ones)

    def test_ghz_three_way_correlation(self):
        shots = set(_shots(GHZ3, 3, 300))
        self.assertEqual(shots, {(0, 0, 0), (1, 1, 1)})


class TestEncoding(unittest.TestCase):
    def test_word_layout(self):
        word = encode("qh", "x5")
        self.assertEqual(word & 0x7F, CUSTOM_OPCODE)
        self.assertEqual((word >> 25) & 0x7F, 1)          # funct7 qh
        self.assertEqual((word >> 15) & 0x1F, 5)          # rs1

    def test_round_trip_all_ops(self):
        cases = [("qh", ["x3"]), ("qx", ["x31"]), ("qz", ["x0"]),
                 ("qrz", ["x6", "-3"]), ("qcx", ["x4", "x9"]),
                 ("qmeas", ["x8", "x20"]), ("qinit", [])]
        for mnemonic, operands in cases:
            with self.subTest(mnemonic=mnemonic):
                name, ops = decode(encode(mnemonic, *operands))
                self.assertEqual(name, mnemonic)
                self.assertEqual(ops, operands)

    def test_rejects_non_custom_opcode(self):
        with self.assertRaises(ValueError):
            decode(0x00000013)                            # plain addi


class TestHybridControlFlow(unittest.TestCase):
    def test_measurement_driven_correction(self):
        """Measure q0; if it read 1, classically flip a flag register."""
        asm = BELL + """
beq   x10, x0, SKIP
li    x20, 100
SKIP:
"""
        seen_flags = set()
        for seed in range(60):
            emu = QuantumTinyRISCVEmulator(n_qubits=2, seed=seed)
            emu.load_program(asm)
            state = emu.execute()
            seen_flags.add(state.get("x20", 0))
            self.assertEqual(state.get("x10", 0), state.get("x11", 0))
        self.assertEqual(seen_flags, {0, 100})            # both branches hit

    def test_classical_arithmetic_unaffected_by_quantum_ops(self):
        asm = """
li    x1, 15
li    x2, 4
sub   x3, x1, x2
li    x5, 0
qh    x5
qmeas x5, x21
addi  x3, x3, 1
"""
        for seed in range(10):
            emu = QuantumTinyRISCVEmulator(n_qubits=2, seed=seed)
            emu.load_program(asm)
            state = emu.execute()
            self.assertEqual(state.get("x3"), 12)


class TestErrorPaths(unittest.TestCase):
    def test_unknown_mnemonic_rejected(self):
        with self.assertRaises(ValueError):
            encode("qft", "x1")

    def test_qubit_index_bounds(self):
        emu = QuantumTinyRISCVEmulator(n_qubits=2, seed=1)
        emu.load_program("li x5, 5\nqh x5")
        with self.assertRaises(ValueError):
            emu.execute()

    def test_qrz_immediate_range(self):
        with self.assertRaises(ValueError):
            encode("qrz", "x1", 32)


if __name__ == "__main__":
    unittest.main()
