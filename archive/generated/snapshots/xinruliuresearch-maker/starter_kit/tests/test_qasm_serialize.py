import math
import unittest

from loomq.qasm import (
    GateOp,
    MeasureOp,
    NormalizedCircuit,
    QASMSerializationError,
    parse_and_normalize,
    serialize_qasm2,
)


class QASMSerializationTests(unittest.TestCase):
    def test_canonical_serialization_and_round_trip(self):
        circuit = NormalizedCircuit(
            3,
            2,
            (
                GateOp("h", (), (0,)),
                GateOp("cu1", (math.pi / 4,), (0, 2)),
                MeasureOp(2, 1),
            ),
        )
        source = serialize_qasm2(circuit)
        self.assertEqual(
            source,
            """\
OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[2];
h q[0];
cu1(0.78539816339744828) q[0],q[2];
measure q[2] -> c[1];
""",
        )
        self.assertEqual(parse_and_normalize(source), circuit)

    def test_empty_circuit_is_valid_and_round_trips(self):
        circuit = NormalizedCircuit(0, 0, ())
        source = serialize_qasm2(circuit)
        self.assertEqual(
            source, 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
        )
        self.assertEqual(parse_and_normalize(source), circuit)

    def test_rejects_bad_counts_and_indices(self):
        with self.assertRaisesRegex(QASMSerializationError, "non-negative integer"):
            serialize_qasm2(NormalizedCircuit(-1, 0, ()))
        with self.assertRaisesRegex(QASMSerializationError, "outside"):
            serialize_qasm2(
                NormalizedCircuit(1, 1, (MeasureOp(1, 0),))
            )

    def test_rejects_invalid_gate_shape_and_parameter(self):
        with self.assertRaisesRegex(QASMSerializationError, "expects 2 qubit"):
            serialize_qasm2(
                NormalizedCircuit(1, 0, (GateOp("cx", (), (0,)),))
            )
        with self.assertRaisesRegex(QASMSerializationError, "not finite"):
            serialize_qasm2(
                NormalizedCircuit(1, 0, (GateOp("rz", (math.inf,), (0,)),))
            )
        with self.assertRaisesRegex(QASMSerializationError, "unsupported gate"):
            serialize_qasm2(
                NormalizedCircuit(1, 0, (GateOp("u3", (0.0, 0.0, 0.0), (0,)),))
            )


if __name__ == "__main__":
    unittest.main()
