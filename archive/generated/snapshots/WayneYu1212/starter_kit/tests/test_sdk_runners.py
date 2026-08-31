import unittest

from starter_kit.evaluator import calculate_hellinger_fidelity, validate_schema
from starter_kit.loomq.compiler.parser import parse_qasm
from starter_kit.loomq.simulator import probabilities
from starter_kit.tests.test_parser_validator import ALL_GATES_QASM, BELL_QASM


try:
    from starter_kit.loomq.runners import run_circuit
except ImportError:
    run_circuit = None


GHZ_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0], q[1];
cx q[1], q[2];
measure q -> c;
"""


MAPPED_MEASUREMENT_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[3];
x q[0];
measure q[0] -> c[2];
measure q[1] -> c[0];
"""


class RealSDKRunnerTests(unittest.TestCase):
    targets = ("spinq", "originq", "braket")

    def setUp(self):
        self.assertIsNotNone(run_circuit, "real SDK runner dispatch is missing")

    def assertFidelity(self, qasm: str, target: str, shots: int = 2048):
        circuit = parse_qasm(qasm)
        result = run_circuit(circuit, target, shots)
        valid, reason = validate_schema(result)
        self.assertTrue(valid, reason)
        observed = {state: count / shots for state, count in result["counts"].items()}
        expected = probabilities(circuit)
        fidelity = calculate_hellinger_fidelity(observed, expected)
        self.assertGreaterEqual(fidelity, 0.97, (target, fidelity, result["counts"]))
        self.assertNotIn("reference", result["meta"]["engine"])
        return result

    def test_public_bell_and_ghz_run_on_each_real_sdk(self):
        for target in self.targets:
            for name, qasm in (("bell", BELL_QASM), ("ghz", GHZ_QASM)):
                with self.subTest(target=target, circuit=name):
                    self.assertFidelity(qasm, target)

    def test_all_official_gates_execute_with_matching_distribution(self):
        for target in self.targets:
            with self.subTest(target=target):
                self.assertFidelity(ALL_GATES_QASM, target, shots=4096)

    def test_classical_measurement_mapping_is_preserved(self):
        for target in self.targets:
            with self.subTest(target=target):
                result = run_circuit(parse_qasm(MAPPED_MEASUREMENT_QASM), target, 64)
                self.assertEqual(result["counts"], {"100": 64})

    def test_rejects_unknown_target_and_invalid_shots(self):
        parsed = parse_qasm(BELL_QASM)
        with self.assertRaisesRegex(ValueError, "unsupported target"):
            run_circuit(parsed, "unknown", 8)
        for shots in (0, -1, True, 1.5):
            with self.subTest(shots=shots), self.assertRaises(ValueError):
                run_circuit(parsed, "spinq", shots)


if __name__ == "__main__":
    unittest.main()
