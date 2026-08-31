import dataclasses
import math
import unittest


try:
    from starter_kit.loomq.compiler.expressions import parse_parameter
    from starter_kit.loomq.compiler.ir import Circuit, Gate, Measurement
except ImportError:
    parse_parameter = None
    Circuit = None
    Gate = None
    Measurement = None


class ParameterExpressionTests(unittest.TestCase):
    def test_evaluates_official_parameter_arithmetic(self):
        self.assertIsNotNone(parse_parameter, "safe parameter parser is missing")
        cases = {
            "pi": math.pi,
            "-3*pi/8 + pi/4": -math.pi / 8,
            "2^(3-1) / 8": 0.5,
            "+0.125": 0.125,
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertAlmostEqual(parse_parameter(source), expected, places=12)

    def test_rejects_executable_or_non_finite_expressions(self):
        self.assertIsNotNone(parse_parameter, "safe parameter parser is missing")
        for source in (
            "__import__('os')",
            "sin(pi)",
            "theta",
            "True",
            "1 / 0",
            "1e309",
            "2 ** 1000000",
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse_parameter(source)


class CircuitIRTests(unittest.TestCase):
    def test_ir_values_are_immutable_and_typed(self):
        self.assertIsNotNone(Gate, "typed circuit IR is missing")
        gate = Gate(name="h", qubits=(0,), params=(), source="h q[0]")
        measurement = Measurement(qubit=0, cbit=0, source="measure q[0] -> c[0]")
        circuit = Circuit(qubit_count=1, cbit_count=1, operations=(gate, measurement))

        self.assertEqual(circuit.gates, (gate,))
        self.assertEqual(circuit.measurements, (measurement,))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            gate.name = "x"


if __name__ == "__main__":
    unittest.main()
