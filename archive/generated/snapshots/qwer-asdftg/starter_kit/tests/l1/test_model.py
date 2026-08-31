import unittest

from starter_kit.loomq_l1.model import Circuit, Measurement, Operation, Register


class ModelTests(unittest.TestCase):
    def test_circuit_exposes_global_widths_and_depth_inputs(self):
        circuit = Circuit(
            qregs=(Register("qa", 2, 0), Register("qb", 1, 2)),
            cregs=(Register("c", 3, 0),),
            operations=(
                Operation("h", (0,)),
                Operation("cx", (0, 2)),
            ),
            measurements=(Measurement(0, 0), Measurement(2, 2)),
        )
        self.assertEqual(circuit.num_qubits, 3)
        self.assertEqual(circuit.num_clbits, 3)
        self.assertEqual(circuit.gate_count, 2)

    def test_register_rejects_non_positive_size(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            Register("q", 0, 0)


if __name__ == "__main__":
    unittest.main()
