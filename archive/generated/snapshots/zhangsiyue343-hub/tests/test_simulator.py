"""Simulator semantics: exact amplitudes for every whitelisted gate."""

import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starter_kit.ir import Circuit
from starter_kit.simulator import SimulationError, Statevector, run_circuit

R2 = 1.0 / math.sqrt(2.0)


def state_after(gate, params=(), qubits=(0,), n=1):
    return Statevector.zero(n).apply_gate(gate, params, qubits)


class TestSingleQubitGates(unittest.TestCase):
    def test_h_creates_superposition(self):
        amps = state_after("h").amplitudes
        self.assertAlmostEqual(abs(amps[0]), R2, places=12)
        self.assertAlmostEqual(abs(amps[1]), R2, places=12)

    def test_x_flips(self):
        self.assertAlmostEqual(abs(state_after("x").amplitudes[1]), 1.0)

    def test_s_phase(self):
        amps = Statevector.zero(1).apply_gate("h", (), (0,)).apply_gate("s", (), (0,)).amplitudes
        self.assertAlmostEqual(amps[1].real, 0.0, places=12)
        self.assertAlmostEqual(amps[1].imag, R2, places=12)

    def test_sdg_inverts_s_exactly(self):
        combined = (Statevector.zero(1)
                    .apply_gate("h", (), (0,))
                    .apply_gate("s", (), (0,))
                    .apply_gate("sdg", (), (0,)))
        reference = Statevector.zero(1).apply_gate("h", (), (0,))
        for got, want in zip(combined.amplitudes, reference.amplitudes):
            self.assertAlmostEqual(got.real, want.real, places=10)
            self.assertAlmostEqual(got.imag, want.imag, places=10)

    def test_t_phase_is_pi_over_four(self):
        amps = (Statevector.zero(1)
                .apply_gate("h", (), (0,))
                .apply_gate("t", (), (0,)).amplitudes)
        expected = complex(R2 * math.cos(math.pi / 4), R2 * math.sin(math.pi / 4))
        self.assertAlmostEqual(amps[1], expected, places=12)

    def test_rz_rotation_angle(self):
        theta = 0.7
        amps = (Statevector.zero(1)
                .apply_gate("x", (), (0,))
                .apply_gate("rz", (theta,), (0,)).amplitudes)
        self.assertAlmostEqual(abs(amps[1]), 1.0, places=12)
        self.assertAlmostEqual(amps[1].imag, math.sin(theta / 2), places=12)

    def test_ry_population_follows_cos_squared(self):
        theta = 1.1
        probs = state_after("ry", (theta,)).probabilities()
        self.assertAlmostEqual(probs[1], math.sin(theta / 2) ** 2, places=12)


class TestTwoAndThreeQubitGates(unittest.TestCase):
    def test_bell_state_entanglement(self):
        bell = (Statevector.zero(2)
                .apply_gate("h", (), (0,))
                .apply_gate("cx", (), (0, 1)))
        self.assertAlmostEqual(bell.probabilities()[0b00], 0.5, places=12)
        self.assertAlmostEqual(bell.probabilities()[0b11], 0.5, places=12)

    def test_cx_control_order_matters(self):
        # control on qubit 1 must NOT flip when qubit 0 is excited alone
        state = (Statevector.zero(2)
                 .apply_gate("x", (), (0,))
                 .apply_gate("cx", (), (1, 0)))
        self.assertAlmostEqual(state.probabilities()[0b01], 1.0, places=12)

    def test_cu1_pi_equals_cz_on_superposition(self):
        prep = lambda: (Statevector.zero(2)
                        .apply_gate("h", (), (0,))
                        .apply_gate("h", (), (1,)))
        via_cu1 = prep().apply_gate("cu1", (math.pi,), (0, 1))
        via_cz = prep().apply_gate("cz_like", (), ()) if False else None
        # cu1(pi) == CZ: only |q0=1,q1=1> gains a minus sign
        amps = via_cu1.amplitudes
        self.assertAlmostEqual(amps[0b00].real, 0.5, places=12)
        self.assertAlmostEqual(amps[0b01].real, 0.5, places=12)
        self.assertAlmostEqual(amps[0b10].real, 0.5, places=12)
        self.assertAlmostEqual(amps[0b11].real, -0.5, places=12)

    def test_swap_exchanges_qubits(self):
        state = (Statevector.zero(2)
                 .apply_gate("x", (), (1,))
                 .apply_gate("swap", (), (0, 1)))
        self.assertAlmostEqual(state.probabilities()[0b01], 1.0, places=12)

    def test_ccx_flips_only_with_two_controls(self):
        both = (Statevector.zero(3)
                .apply_gate("x", (), (0,))
                .apply_gate("x", (), (1,))
                .apply_gate("ccx", (), (0, 1, 2)))
        self.assertAlmostEqual(both.probabilities()[0b111], 1.0, places=12)

        single = (Statevector.zero(3)
                  .apply_gate("x", (), (1,))
                  .apply_gate("ccx", (), (0, 1, 2)))
        self.assertAlmostEqual(single.probabilities()[0b010], 1.0, places=12)


class TestSampling(unittest.TestCase):
    def test_ghz_distribution_matches_ideal(self):
        ghz = Circuit(
            5, 5,
            [("h", (), (0,))] + [("cx", (), (i, i + 1)) for i in range(4)],
            [(i, i) for i in range(5)],
        )
        counts = run_circuit(ghz, shots=4096, rng=random.Random(42))
        self.assertEqual(sum(counts.values()), 4096)
        self.assertEqual(set(counts), {"00000", "11111"})
        self.assertGreater(counts["00000"], 1800)
        self.assertGreater(counts["11111"], 1800)

    def test_partial_measure_map(self):
        circuit = Circuit(2, 3,
                          [("x", (), (1,))],
                          [(1, 0)])          # measure q1 into c0 only
        counts = run_circuit(circuit, shots=64, rng=random.Random(1))
        self.assertEqual(counts, {"001": 64})   # c0=1 -> key '001' little-endian

    def test_no_measure_means_measure_all(self):
        circuit = Circuit(1, 1, [("x", (), (0,))], [])
        counts = run_circuit(circuit, shots=32, rng=random.Random(3))
        self.assertEqual(counts, {"1": 32})

    def test_invalid_reuse_of_qubit_rejected(self):
        with self.assertRaises(SimulationError):
            Statevector.zero(2).apply_gate("cx", (), (0, 0))


if __name__ == "__main__":
    unittest.main()
