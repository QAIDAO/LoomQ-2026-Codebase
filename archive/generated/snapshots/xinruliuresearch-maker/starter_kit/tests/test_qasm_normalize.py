import math
import unittest

from loomq.qasm import (
    GateOp,
    MeasureOp,
    QASMSemanticError,
    parse_and_normalize,
)


def qasm(body: str) -> str:
    return 'OPENQASM 2.0;\ninclude "qelib1.inc";\n' + body


class QASMNormalizationTests(unittest.TestCase):
    def test_all_supported_gates_and_expression_evaluation(self):
        circuit = parse_and_normalize(
            qasm(
                """\
qreg quantum_data[3];
h quantum_data[0];
x quantum_data[0];
s quantum_data[0];
sdg quantum_data[0];
t quantum_data[0];
tdg quantum_data[0];
rz(pi/2) quantum_data[0];
ry(-(2.5e-1 + +.25) * 2) quantum_data[0];
cx quantum_data[0],quantum_data[1];
cu1(pi/4) quantum_data[0],quantum_data[1];
swap quantum_data[0],quantum_data[1];
ccx quantum_data[0],quantum_data[1],quantum_data[2];
"""
            )
        )
        self.assertEqual(
            [operation.name for operation in circuit.operations],
            ["h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx"],
        )
        self.assertAlmostEqual(circuit.operations[6].params[0], math.pi / 2)
        self.assertAlmostEqual(circuit.operations[7].params[0], -1.0)

    def test_multiple_register_offsets_and_gate_broadcasting(self):
        circuit = parse_and_normalize(
            qasm(
                """\
qreg left_side[2];
qreg right_side[2];
cx left_side,right_side;
cx left_side[1],right_side;
"""
            )
        )
        self.assertEqual(circuit.qubit_count, 4)
        self.assertEqual(
            circuit.operations,
            (
                GateOp("cx", (), (0, 2)),
                GateOp("cx", (), (1, 3)),
                GateOp("cx", (), (1, 2)),
                GateOp("cx", (), (1, 3)),
            ),
        )

    def test_indexed_and_whole_register_measurement(self):
        circuit = parse_and_normalize(
            qasm(
                """\
qreg source_a[2];
qreg source_b[1];
creg target_a[1];
creg target_b[2];
measure source_b[0] -> target_a[0];
measure source_a -> target_b;
"""
            )
        )
        self.assertEqual((circuit.qubit_count, circuit.classical_count), (3, 3))
        self.assertEqual(
            circuit.operations,
            (MeasureOp(2, 0), MeasureOp(0, 1), MeasureOp(1, 2)),
        )

    def test_source_order_survives_expansion(self):
        circuit = parse_and_normalize(
            qasm(
                """\
qreg data_line[2];
creg output_line[2];
h data_line;
measure data_line[0] -> output_line[1];
x data_line[1];
"""
            )
        )
        self.assertEqual(
            circuit.operations,
            (
                GateOp("h", (), (0,)),
                GateOp("h", (), (1,)),
                MeasureOp(0, 1),
                GateOp("x", (), (1,)),
            ),
        )

    def test_duplicate_declarations_across_types_are_rejected(self):
        with self.assertRaisesRegex(QASMSemanticError, "duplicate declaration"):
            parse_and_normalize(qasm("qreg shared[1];\ncreg shared[1];\n"))

    def test_zero_sized_register_is_rejected(self):
        with self.assertRaisesRegex(QASMSemanticError, "must have positive size"):
            parse_and_normalize(qasm("qreg empty_data[0];\n"))

    def test_unsupported_include_is_not_read(self):
        with self.assertRaisesRegex(QASMSemanticError, "unsupported include path"):
            parse_and_normalize(
                'OPENQASM 2.0; include "local-file.inc"; qreg data[1];'
            )

    def test_unknown_gate_has_recovery_suggestion(self):
        with self.assertRaises(QASMSemanticError) as caught:
            parse_and_normalize(qasm("qreg data[1];\nhh data[0];"))
        self.assertIn("unsupported gate", caught.exception.message)
        self.assertIn("h", caught.exception.suggestion)

    def test_gate_parameter_and_qubit_arity_are_strict(self):
        with self.assertRaisesRegex(QASMSemanticError, "expects 1 parameter"):
            parse_and_normalize(qasm("qreg data[1];\nrz data[0];"))
        with self.assertRaisesRegex(QASMSemanticError, "expects 2 qubit argument"):
            parse_and_normalize(qasm("qreg data[1];\ncx data[0];"))
        with self.assertRaisesRegex(QASMSemanticError, "expects 0 parameter"):
            parse_and_normalize(qasm("qreg data[1];\nh(pi) data[0];"))

    def test_register_lookup_type_and_index_errors(self):
        with self.assertRaisesRegex(QASMSemanticError, "unknown register 'dat'"):
            parse_and_normalize(qasm("qreg data[1];\nh dat[0];"))
        with self.assertRaisesRegex(QASMSemanticError, "is classical"):
            parse_and_normalize(qasm("creg result[1];\nh result[0];"))
        with self.assertRaisesRegex(QASMSemanticError, "is quantum"):
            parse_and_normalize(
                qasm(
                    "qreg data[1]; creg result[1]; "
                    "measure data[0] -> data[0];"
                )
            )
        with self.assertRaisesRegex(QASMSemanticError, "out of range"):
            parse_and_normalize(qasm("qreg data[2];\nh data[2];"))

    def test_gate_broadcast_requires_equal_whole_register_sizes(self):
        with self.assertRaisesRegex(QASMSemanticError, "unequal register sizes"):
            parse_and_normalize(
                qasm("qreg left_data[2]; qreg right_data[3]; cx left_data,right_data;")
            )

    def test_measurement_shape_and_size_are_strict(self):
        with self.assertRaisesRegex(QASMSemanticError, "both be indexed"):
            parse_and_normalize(
                qasm(
                    "qreg source_data[2]; creg result_data[2]; "
                    "measure source_data[0] -> result_data;"
                )
            )
        with self.assertRaisesRegex(QASMSemanticError, "sizes differ"):
            parse_and_normalize(
                qasm(
                    "qreg source_data[2]; creg result_data[3]; "
                    "measure source_data -> result_data;"
                )
            )

    def test_division_by_zero_and_non_finite_values_are_rejected(self):
        with self.assertRaisesRegex(QASMSemanticError, "division by zero"):
            parse_and_normalize(qasm("qreg data[1]; rz(1/(2-2)) data[0];"))
        with self.assertRaisesRegex(QASMSemanticError, "not finite"):
            parse_and_normalize(qasm("qreg data[1]; rz(1e309) data[0];"))


if __name__ == "__main__":
    unittest.main()
