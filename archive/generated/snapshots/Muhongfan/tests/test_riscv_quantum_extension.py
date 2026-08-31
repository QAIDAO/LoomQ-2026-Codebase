"""End-to-end tests for the Bonus quantum RISC-V extension
(starter_kit/riscv_emulator_ext.py, encoding spec in
starter_kit/custom_riscv_isa.md).

Correctness signal comes from two kinds of assertions:
  - deterministic invariants that hold regardless of random seed (X on |0>
    is always 1; a Bell pair's two measurements always agree) -- no
    statistical tolerance needed, so these can't pass by luck.
  - a statistical check (H on |0> measures ~50/50) with an explicit
    tolerance band, run over many seeds.
"""

import unittest

from starter_kit.riscv_emulator_ext import QuantumRISCVEmulator


class DeterministicGateTests(unittest.TestCase):
    def test_x_then_measure_is_always_one(self):
        for seed in range(20):
            emu = QuantumRISCVEmulator(seed=seed)
            emu.load_program("qgate x, 0\nqmeas x1, 0\n")
            state = emu.execute()
            self.assertEqual(state.get("x1", 0), 1)

    def test_measure_without_any_gate_is_always_zero(self):
        emu = QuantumRISCVEmulator(seed=0)
        emu.load_program("qmeas x1, 0\n")
        state = emu.execute()
        self.assertEqual(state.get("x1", 0), 0)

    def test_x_twice_returns_to_zero(self):
        emu = QuantumRISCVEmulator(seed=0)
        emu.load_program("qgate x, 0\nqgate x, 0\nqmeas x1, 0\n")
        state = emu.execute()
        self.assertEqual(state.get("x1", 0), 0)


class BellPairInvariantTests(unittest.TestCase):
    """H + CX entangles two qubits; measuring both in the computational
    basis must agree every single time, for every seed -- a hard invariant,
    not a statistical tendency."""

    PROGRAM = "qgate h, 0\nqgate cx, 0, 1\nqmeas x1, 0\nqmeas x2, 1\n"

    def test_measurements_always_agree_across_many_seeds(self):
        saw_00 = saw_11 = False
        for seed in range(50):
            emu = QuantumRISCVEmulator(seed=seed)
            emu.load_program(self.PROGRAM)
            state = emu.execute()
            m0, m1 = state.get("x1", 0), state.get("x2", 0)
            self.assertEqual(m0, m1, msg=f"seed={seed}: bell pair disagreed ({m0} != {m1})")
            saw_00 = saw_00 or (m0 == 0)
            saw_11 = saw_11 or (m0 == 1)
        # Both outcomes should actually occur across 50 seeds (otherwise the
        # "agreement" check above would be trivially true from a stuck RNG).
        self.assertTrue(saw_00 and saw_11)


class StatisticalTests(unittest.TestCase):
    def test_hadamard_then_measure_is_roughly_fifty_fifty(self):
        ones = 0
        trials = 500
        for seed in range(trials):
            emu = QuantumRISCVEmulator(seed=seed)
            emu.load_program("qgate h, 0\nqmeas x1, 0\n")
            state = emu.execute()
            ones += state.get("x1", 0)
        fraction = ones / trials
        self.assertTrue(0.35 <= fraction <= 0.65, msg=f"observed fraction={fraction}")


class ClassicalQuantumFeedbackLoopTests(unittest.TestCase):
    """The actual point of a *quantum RISC-V extension*: a classical branch
    (beq) chooses which quantum gate to apply next, based on a measurement
    outcome from an earlier quantum instruction."""

    PROGRAM = (
        "qgate h, 0\n"
        "qmeas x10, 0\n"
        "beq x10, x0, ELSE\n"
        "qgate x, 1\n"
        "j END\n"
        "ELSE:\n"
        "qgate h, 1\n"
        "END:\n"
        "qmeas x11, 1\n"
    )

    def test_branch_taken_implies_deterministic_second_measurement(self):
        # x10==1 -> ELSE is skipped -> qgate x,1 -> qubit 1 is |1> -> x11 must be 1.
        branch_taken_results = []
        for seed in range(200):
            emu = QuantumRISCVEmulator(seed=seed)
            emu.load_program(self.PROGRAM)
            state = emu.execute()
            if state.get("x10", 0) == 1:
                branch_taken_results.append(state.get("x11", 0))
        self.assertTrue(branch_taken_results, "no seed in range triggered the x10==1 branch")
        self.assertTrue(all(v == 1 for v in branch_taken_results))

    def test_branch_not_taken_implies_fifty_fifty_second_measurement(self):
        # x10==0 -> ELSE runs -> qgate h,1 -> qubit 1 is superposed -> x11 ~50/50.
        branch_not_taken_results = []
        for seed in range(400):
            emu = QuantumRISCVEmulator(seed=seed)
            emu.load_program(self.PROGRAM)
            state = emu.execute()
            if state.get("x10", 0) == 0:
                branch_not_taken_results.append(state.get("x11", 0))
        self.assertTrue(branch_not_taken_results, "no seed in range triggered the x10==0 branch")
        fraction = sum(branch_not_taken_results) / len(branch_not_taken_results)
        self.assertTrue(0.3 <= fraction <= 0.7, msg=f"observed fraction={fraction}")


class UnsupportedGateTests(unittest.TestCase):
    def test_rejects_gate_outside_h_x_cx(self):
        emu = QuantumRISCVEmulator(seed=0)
        emu.load_program("qgate rz, 0\n")
        with self.assertRaises(ValueError):
            emu.execute()


if __name__ == "__main__":
    unittest.main()
