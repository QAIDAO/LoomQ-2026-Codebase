"""Tests for OpenQASM parsing and semantic validation."""

import unittest
import math
from pathlib import Path

from loomq.errors import QASMParseError, QASMSemanticError, UnsupportedGateError
from loomq.ir import GateOperation, MeasureOperation, QubitRef
from loomq.parser import parse_qasm


STARTER_KIT = Path(__file__).resolve().parents[1]

GATE_SPECS = {
    "h": (0, 1),
    "x": (0, 1),
    "s": (0, 1),
    "sdg": (0, 1),
    "t": (0, 1),
    "tdg": (0, 1),
    "ry": (1, 1),
    "rz": (1, 1),
    "cx": (0, 2),
    "cu1": (1, 2),
    "swap": (0, 2),
    "ccx": (0, 3),
}


class ParserTests(unittest.TestCase):
    def read_circuit(self, name: str) -> str:
        return (STARTER_KIT / "circuits" / name).read_text(encoding="utf-8")

    def test_bell_registers_and_operation_order(self) -> None:
        circuit = parse_qasm(self.read_circuit("bell.qasm"))

        self.assertEqual([("q", 2)], [(item.name, item.size) for item in circuit.quantum_registers])
        self.assertEqual([("c", 2)], [(item.name, item.size) for item in circuit.classical_registers])
        self.assertEqual(3, len(circuit.operations))
        self.assertEqual(["h", "cx"], [operation.name for operation in circuit.operations[:2]])
        self.assertIsInstance(circuit.operations[2], MeasureOperation)

    def test_ghz3_parses(self) -> None:
        circuit = parse_qasm(self.read_circuit("ghz3.qasm"))

        gates = [operation for operation in circuit.operations if isinstance(operation, GateOperation)]
        self.assertEqual(["h", "cx", "cx"], [gate.name for gate in gates])
        self.assertEqual((QubitRef("q", 1), QubitRef("q", 2)), gates[-1].qubits)

    def test_register_measurement(self) -> None:
        circuit = parse_qasm(
            'OPENQASM 2.0; include "qelib1.inc"; qreg data[2]; '
            "creg result[2]; measure data -> result;"
        )

        measurement = circuit.operations[0]
        self.assertIsInstance(measurement, MeasureOperation)
        self.assertEqual("data", measurement.quantum.register)
        self.assertEqual("result", measurement.classical.register)

    def test_single_qubit_measurement(self) -> None:
        circuit = parse_qasm(
            "OPENQASM 2.0; qreg data[2]; creg result[2]; "
            "measure data[1] -> result[0];"
        )

        measurement = circuit.operations[0]
        self.assertEqual(QubitRef("data", 1), measurement.quantum)
        self.assertEqual(0, measurement.classical.index)

    def test_comments_whitespace_and_multiple_statements_per_line(self) -> None:
        circuit = parse_qasm(
            "  // heading\n"
            " OPENQASM 2.0; include \"qelib1.inc\";\n"
            "qreg data [ 2 ]; creg out[2]; // declarations\n"
            " h data[0] ; cx data[0] ,data[1] ; measure data -> out; // done\n"
        )

        self.assertEqual(["h", "cx"], [operation.name for operation in circuit.operations[:2]])
        self.assertEqual("data", circuit.quantum_registers[0].name)

    def test_undeclared_register_is_rejected_with_line(self) -> None:
        with self.assertRaisesRegex(QASMSemanticError, r"line 3:.*missing.*not declared"):
            parse_qasm("OPENQASM 2.0;\nqreg q[1];\nh missing[0];")

    def test_qubit_index_out_of_range_is_rejected(self) -> None:
        with self.assertRaisesRegex(QASMSemanticError, r"index 2 is out of range"):
            parse_qasm("OPENQASM 2.0; qreg q[2]; h q[2];")

    def test_register_measurement_size_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(QASMSemanticError, "size mismatch"):
            parse_qasm(
                "OPENQASM 2.0; qreg q[2]; creg c[1]; measure q -> c;"
            )

    def test_unsupported_gate_is_rejected(self) -> None:
        with self.assertRaisesRegex(UnsupportedGateError, "unsupported quantum gate 'y'"):
            parse_qasm("OPENQASM 2.0; qreg q[1]; y q[0];")

    def test_all_twelve_whitelisted_gates_parse(self) -> None:
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
h q[0];
x q[0];
s q[0];
sdg q[0];
t q[0];
tdg q[0];
ry(pi/2) q[0];
rz(-pi/4) q[1];
cx q[0], q[1];
cu1(3*pi/8) q[0], q[1];
swap q[0], q[1];
ccx q[0], q[1], q[2];
"""

        gates = parse_qasm(source).operations

        self.assertEqual(list(GATE_SPECS), [gate.name for gate in gates])
        self.assertAlmostEqual(math.pi / 2, gates[6].parameters[0])
        self.assertAlmostEqual(-math.pi / 4, gates[7].parameters[0])
        self.assertAlmostEqual(3 * math.pi / 8, gates[9].parameters[0])

    def test_every_gate_rejects_wrong_parameter_count(self) -> None:
        for name, (parameter_count, qubit_count) in GATE_SPECS.items():
            parameters = "" if parameter_count else "(pi)"
            operands = ", ".join("q[%d]" % index for index in range(qubit_count))
            with self.subTest(gate=name):
                with self.assertRaisesRegex(QASMParseError, "expects .* parameter"):
                    parse_qasm(
                        "OPENQASM 2.0; qreg q[3]; %s%s %s;"
                        % (name, parameters, operands)
                    )

    def test_every_gate_rejects_wrong_qubit_count(self) -> None:
        for name, (parameter_count, qubit_count) in GATE_SPECS.items():
            parameters = "(pi)" if parameter_count else ""
            wrong_count = 2 if qubit_count == 1 else qubit_count - 1
            operands = ", ".join("q[%d]" % index for index in range(wrong_count))
            with self.subTest(gate=name):
                with self.assertRaisesRegex(QASMParseError, "expects .* qubit"):
                    parse_qasm(
                        "OPENQASM 2.0; qreg q[3]; %s%s %s;"
                        % (name, parameters, operands)
                    )

    def test_nested_parameter_expression_does_not_break_operands(self) -> None:
        circuit = parse_qasm(
            "OPENQASM 2.0; qreg q[1]; ry((pi + pi/2) / 3) q[0];"
        )

        self.assertAlmostEqual(math.pi / 2, circuit.operations[0].parameters[0])
        self.assertEqual((QubitRef("q", 0),), circuit.operations[0].qubits)

    def test_invalid_parameter_expression_reports_line_and_statement(self) -> None:
        with self.assertRaisesRegex(
            QASMParseError, r"line 3: invalid parameter expression.*ry\(theta\) q\[0\]"
        ):
            parse_qasm("OPENQASM 2.0;\nqreg q[1];\nry(theta) q[0];")


if __name__ == "__main__":
    unittest.main()
