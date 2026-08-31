import unittest

from starter_kit.evaluator import calculate_hellinger_fidelity, validate_schema
from starter_kit.loomq.compiler.parser import parse_qasm
from starter_kit.loomq.runners import run_circuit
from starter_kit.loomq.simulator import probabilities
from starter_kit.tests.fixtures import (
    GHZ5_QASM,
    GROVER_LIKE_QASM,
    QFT_LIKE_QASM,
    random_qasm,
)


class HiddenResistanceTests(unittest.TestCase):
    def test_private_shape_circuits_match_reference_on_three_sdks(self):
        circuits = {
            "ghz5": GHZ5_QASM,
            "qft-like": QFT_LIKE_QASM,
            "grover-like": GROVER_LIKE_QASM,
            "random-1701": random_qasm(1701),
            "random-2603": random_qasm(2603),
            "random-8119": random_qasm(8119),
        }
        shots = 8192
        for name, source in circuits.items():
            parsed = parse_qasm(source)
            expected = probabilities(parsed)
            for target in ("spinq", "originq", "braket"):
                with self.subTest(circuit=name, target=target):
                    result = run_circuit(parsed, target, shots)
                    valid, reason = validate_schema(result)
                    self.assertTrue(valid, reason)
                    observed = {
                        state: count / shots for state, count in result["counts"].items()
                    }
                    fidelity = calculate_hellinger_fidelity(observed, expected)
                    self.assertGreaterEqual(
                        fidelity,
                        0.97,
                        (name, target, fidelity, result["counts"], expected),
                    )


if __name__ == "__main__":
    unittest.main()
