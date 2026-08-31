"""Reference and local-provider coverage for LoomQ L1 hidden-style circuits."""

import math
import unittest

from starter_kit.loomq_l1.parser import GATE_ARITY, parse_qasm
from starter_kit import adapter
from starter_kit.evaluator import calculate_hellinger_fidelity
from starter_kit.tests.l1.support.circuit_factory import hidden_style_circuits
from starter_kit.tests.l1.support.reference_simulator import (
    simulate_operation_probabilities,
    simulate_probabilities,
)


def _qasm(num_qubits, operations, measurements=None, num_clbits=None):
    """Build a strict OpenQASM 2 program with explicit measurements."""
    if num_clbits is None:
        num_clbits = num_qubits
    if measurements is None:
        measurements = [(qubit, qubit) for qubit in range(num_qubits)]
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{num_qubits}];",
        f"creg c[{num_clbits}];",
        *operations,
        *(f"measure q[{qubit}] -> c[{cbit}];" for qubit, cbit in measurements),
    ]
    return "\n".join(lines) + "\n"


class ReferenceSimulatorTests(unittest.TestCase):
    """Lock down every L1 whitelist gate against a small known distribution."""

    def assert_distribution(self, qasm, expected):
        actual = simulate_probabilities(qasm)
        self.assertEqual(set(actual), set(expected))
        for key, probability in expected.items():
            self.assertAlmostEqual(actual[key], probability, places=12, msg=key)

    def test_h_creates_an_equal_superposition(self):
        self.assert_distribution(_qasm(1, ["h q[0];"]), {"0": 0.5, "1": 0.5})

    def test_x_flips_the_least_significant_qubit(self):
        self.assert_distribution(_qasm(2, ["x q[0];"]), {"01": 1.0})

    def test_s_phase_is_visible_after_hadamards(self):
        self.assert_distribution(_qasm(1, ["h q[0];", "s q[0];", "h q[0];"]), {"0": 0.5, "1": 0.5})

    def test_sdg_is_the_inverse_of_s(self):
        self.assert_distribution(
            _qasm(1, ["h q[0];", "sdg q[0];", "s q[0];", "h q[0];"]),
            {"0": 1.0},
        )

    def test_t_phase_is_visible_after_hadamards(self):
        probability_one = math.sin(math.pi / 8) ** 2
        self.assert_distribution(
            _qasm(1, ["h q[0];", "t q[0];", "h q[0];"]),
            {"0": 1.0 - probability_one, "1": probability_one},
        )

    def test_tdg_is_the_inverse_of_t(self):
        self.assert_distribution(
            _qasm(1, ["h q[0];", "tdg q[0];", "t q[0];", "h q[0];"]),
            {"0": 1.0},
        )

    def test_rz_phase_is_visible_after_hadamards(self):
        angle = math.pi / 3
        probability_one = math.sin(angle / 2) ** 2
        self.assert_distribution(
            _qasm(1, ["h q[0];", f"rz(pi/3) q[0];", "h q[0];"]),
            {"0": 1.0 - probability_one, "1": probability_one},
        )

    def test_ry_rotates_the_least_significant_qubit(self):
        angle = math.pi / 3
        probability_one = math.sin(angle / 2) ** 2
        self.assert_distribution(
            _qasm(1, ["ry(pi/3) q[0];"]),
            {"0": 1.0 - probability_one, "1": probability_one},
        )

    def test_cx_creates_a_bell_distribution(self):
        self.assert_distribution(
            _qasm(2, ["h q[0];", "cx q[0],q[1];"]),
            {"00": 0.5, "11": 0.5},
        )

    def test_cu1_matches_the_documented_decomposition(self):
        angle = math.pi / 3
        prefix = (("h", (0,), None), ("h", (1,), None))
        suffix = (("h", (0,), None), ("h", (1,), None))
        direct = prefix + (("cu1", (0, 1), angle),) + suffix
        decomposed = prefix + (
            ("u1", (0,), angle / 2),
            ("cx", (0, 1), None),
            ("u1", (1,), -angle / 2),
            ("cx", (0, 1), None),
            ("u1", (1,), angle / 2),
        ) + suffix
        self.assertEqual(
            simulate_operation_probabilities(2, direct),
            simulate_operation_probabilities(2, decomposed),
        )

    def test_swap_matches_three_controlled_not_gates(self):
        direct = _qasm(2, ["x q[0];", "swap q[0],q[1];"])
        decomposed = _qasm(2, ["x q[0];", "cx q[0],q[1];", "cx q[1],q[0];", "cx q[0],q[1];"])
        self.assertEqual(simulate_probabilities(direct), simulate_probabilities(decomposed))

    def test_ccx_matches_the_documented_decomposition(self):
        direct = _qasm(3, ["h q[0];", "h q[1];", "ccx q[0],q[1],q[2];"])
        decomposed = _qasm(
            3,
            [
                "h q[0];",
                "h q[1];",
                "h q[2];",
                "cx q[1],q[2];",
                "tdg q[2];",
                "cx q[0],q[2];",
                "t q[2];",
                "cx q[1],q[2];",
                "tdg q[2];",
                "cx q[0],q[2];",
                "t q[1];",
                "t q[2];",
                "h q[2];",
                "cx q[0],q[1];",
                "t q[0];",
                "tdg q[1];",
                "cx q[0],q[1];",
            ],
        )
        self.assertEqual(simulate_probabilities(direct), simulate_probabilities(decomposed))

    def test_measurements_map_qubits_to_canonical_classical_positions(self):
        self.assert_distribution(
            _qasm(
                3,
                ["x q[0];"],
                measurements=[(0, 2), (1, 1), (2, 0)],
            ),
            {"100": 1.0},
        )


class CircuitFactoryTests(unittest.TestCase):
    """Keep hidden-style corpus construction deterministic and strict."""

    def test_factories_build_the_named_measured_circuits_deterministically(self):
        from starter_kit.tests.l1.support.circuit_factory import hidden_style_circuits

        first = hidden_style_circuits()
        second = hidden_style_circuits()
        self.assertEqual(first, second)
        self.assertEqual(tuple(first), ("ghz-5", "qft-4", "grover-3", "random-5-1", "random-5-2", "random-5-3"))

        for name, qasm in first.items():
            with self.subTest(circuit=name):
                circuit = parse_qasm(qasm)
                self.assertTrue(all(operation.name in GATE_ARITY for operation in circuit.operations))
                self.assertEqual(
                    tuple((measurement.qubit, measurement.cbit) for measurement in circuit.measurements),
                    tuple((index, index) for index in range(circuit.num_qubits)),
                )

    def test_exact_builders_have_the_expected_operation_sequences(self):
        from starter_kit.tests.l1.support.circuit_factory import hidden_style_circuits

        circuits = {name: parse_qasm(qasm) for name, qasm in hidden_style_circuits().items()}
        self.assertEqual(
            tuple(operation.name for operation in circuits["ghz-5"].operations),
            ("h", "cx", "cx", "cx", "cx"),
        )
        self.assertEqual(
            tuple(operation.name for operation in circuits["qft-4"].operations),
            ("h", "cu1", "cu1", "cu1", "h", "cu1", "cu1", "h", "cu1", "h", "swap", "swap"),
        )
        self.assertEqual(
            tuple(operation.name for operation in circuits["grover-3"].operations),
            (
                "h", "h", "h",
                "h", "ccx", "h", "h", "h", "h", "x", "x", "x", "h", "ccx", "h", "x", "x", "x", "h", "h", "h",
                "h", "ccx", "h", "h", "h", "h", "x", "x", "x", "h", "ccx", "h", "x", "x", "x", "h", "h", "h",
            ),
        )

    def test_grover_3_runs_two_iterations_and_amplifies_marked_111(self):
        probabilities = simulate_probabilities(hidden_style_circuits()["grover-3"])
        self.assertAlmostEqual(probabilities["111"], 0.9453125, places=12)
        for key, probability in probabilities.items():
            if key != "111":
                self.assertAlmostEqual(probability, 0.0078125, places=12, msg=key)

    def test_qft_4_maps_zero_to_the_uniform_distribution(self):
        probabilities = simulate_probabilities(hidden_style_circuits()["qft-4"])
        self.assertEqual(len(probabilities), 16)
        for key, probability in probabilities.items():
            self.assertAlmostEqual(probability, 1 / 16, places=12, msg=key)

    def test_test_only_circuits_and_reference_distributions_are_bit_exactly_repeatable(self):
        first = hidden_style_circuits()
        second = hidden_style_circuits()
        self.assertEqual(first, second)
        for name in first:
            with self.subTest(circuit=name):
                self.assertEqual(simulate_probabilities(first[name]), simulate_probabilities(second[name]))


class ProviderReferenceFidelityTests(unittest.TestCase):
    """Compare sampled local providers with deterministic exact references.

    The pinned SpinQ config exposes only ``configure_shots``; Braket 1.108.0
    has no documented seed parameter; pyQPanda's CPUQVM exposes no seed API;
    and LoomQ's public adapter cannot forward a seed. Raw sample histograms
    therefore cannot be made seed-identical through the public adapter. The
    deterministic invariant is the factory/reference pair; each real provider
    is judged by the official 8192-shot fidelity threshold, rather than by
    exact raw-count equality.
    """

    shots = 8192

    def test_all_hidden_style_circuits_clear_the_fidelity_threshold(self):
        for target in ("spinq", "originq", "braket"):
            for name, qasm in hidden_style_circuits().items():
                with self.subTest(target=target, circuit=name):
                    expected = simulate_probabilities(qasm)
                    result = adapter.run(qasm, target, self.shots)
                    observed = {key: count / self.shots for key, count in result["counts"].items()}
                    fidelity = calculate_hellinger_fidelity(observed, expected)
                    self.assertGreaterEqual(
                        fidelity,
                        0.97,
                        f"target={target} circuit={name} fidelity={fidelity:.6f}",
                    )


if __name__ == "__main__":
    unittest.main()
