import math
import unittest

from starter_kit.loomq.compiler.parser import parse_qasm


try:
    from starter_kit.loomq.simulator import SimulationError, probabilities, sample
except ImportError:
    SimulationError = RuntimeError
    probabilities = None
    sample = None


def circuit(body: str, qubits: int = 1, cbits: int | None = None) -> str:
    classical = qubits if cbits is None else cbits
    return f"""OPENQASM 2.0;
include "qelib1.inc";
qreg q[{qubits}];
creg c[{classical}];
{body}
"""


class ReferenceSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(probabilities, "reference simulator is missing")

    def assertDistribution(self, qasm: str, expected: dict[str, float], places: int = 10):
        actual = probabilities(parse_qasm(qasm))
        self.assertEqual(set(actual), set(expected))
        for state, probability in expected.items():
            self.assertAlmostEqual(actual[state], probability, places=places)

    def test_bell_and_ghz_distributions_are_ideal(self):
        bell = circuit("h q[0]; cx q[0],q[1]; measure q -> c;", qubits=2)
        ghz = circuit("h q[0]; cx q[0],q[1]; cx q[1],q[2]; measure q -> c;", qubits=3)
        self.assertDistribution(bell, {"00": 0.5, "11": 0.5})
        self.assertDistribution(ghz, {"000": 0.5, "111": 0.5})

    def test_single_qubit_gate_semantics_include_phase_interference(self):
        phase_t = math.cos(math.pi / 8) ** 2
        cases = (
            ("x q[0]; measure q -> c;", {"1": 1.0}),
            ("h q[0]; measure q -> c;", {"0": 0.5, "1": 0.5}),
            ("h q[0]; s q[0]; h q[0]; measure q -> c;", {"0": 0.5, "1": 0.5}),
            ("h q[0]; sdg q[0]; h q[0]; measure q -> c;", {"0": 0.5, "1": 0.5}),
            ("h q[0]; t q[0]; h q[0]; measure q -> c;", {"0": phase_t, "1": 1 - phase_t}),
            ("h q[0]; tdg q[0]; h q[0]; measure q -> c;", {"0": phase_t, "1": 1 - phase_t}),
            ("ry(pi) q[0]; measure q -> c;", {"1": 1.0}),
            ("h q[0]; rz(pi) q[0]; h q[0]; measure q -> c;", {"1": 1.0}),
        )
        for body, expected in cases:
            with self.subTest(body=body):
                self.assertDistribution(circuit(body), expected)

    def test_controlled_swap_and_toffoli_semantics(self):
        controlled_phase = circuit(
            "h q[0]; h q[1]; cu1(pi) q[0],q[1]; h q[1]; measure q -> c;",
            qubits=2,
        )
        swapped = circuit("x q[0]; swap q[0],q[1]; measure q -> c;", qubits=2)
        toffoli = circuit("x q[0]; x q[1]; ccx q[0],q[1],q[2]; measure q -> c;", qubits=3)
        self.assertDistribution(controlled_phase, {"00": 0.5, "11": 0.5})
        self.assertDistribution(swapped, {"10": 1.0})
        self.assertDistribution(toffoli, {"111": 1.0})

    def test_measurements_map_into_declared_classical_positions(self):
        source = circuit(
            "x q[0]; measure q[0] -> c[2]; measure q[1] -> c[0];",
            qubits=2,
            cbits=3,
        )
        self.assertDistribution(source, {"100": 1.0})

    def test_sampling_is_seeded_and_preserves_exact_shot_total(self):
        parsed = parse_qasm(circuit("h q[0]; measure q -> c;"))
        first = sample(parsed, 257, seed=42)
        second = sample(parsed, 257, seed=42)

        self.assertEqual(first, second)
        self.assertEqual(sum(first.values()), 257)
        self.assertEqual(set(first), {"0", "1"})

    def test_statevector_memory_guard_is_explicit(self):
        source = circuit("h q[0]; measure q -> c;", qubits=17)
        with self.assertRaisesRegex(SimulationError, "16"):
            probabilities(parse_qasm(source))


if __name__ == "__main__":
    unittest.main()
