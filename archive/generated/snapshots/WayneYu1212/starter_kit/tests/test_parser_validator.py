import math
import unittest


try:
    from starter_kit.loomq.compiler.ir import Gate, Measurement
    from starter_kit.loomq.compiler.parser import QASMParseError, parse_qasm
    from starter_kit.loomq.compiler.validator import CircuitValidationError
except ImportError:
    Gate = None
    Measurement = None
    QASMParseError = ValueError
    CircuitValidationError = ValueError
    parse_qasm = None


BELL_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""


ALL_GATES_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg work[3];
creg result[3];
h work[0];
x work[1];
s work[0];
sdg work[0];
t work[1];
tdg work[1];
rz(pi/2) work[0];
ry(-0.5) work[1];
cx work[0], work[1];
cu1(pi/4) work[1], work[2];
swap work[0], work[2];
ccx work[0], work[1], work[2];
measure work -> result;
"""


class OpenQASMParserTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(parse_qasm, "OpenQASM parser is missing")

    def test_parses_public_bell_and_expands_register_measurement(self):
        circuit = parse_qasm(BELL_QASM)

        self.assertEqual((circuit.qubit_count, circuit.cbit_count), (2, 2))
        self.assertEqual(circuit.gates, (
            Gate("h", (0,), (), "h q[0]"),
            Gate("cx", (0, 1), (), "cx q[0], q[1]"),
        ))
        self.assertEqual(circuit.measurements, (
            Measurement(0, 0, "measure q -> c"),
            Measurement(1, 1, "measure q -> c"),
        ))

    def test_parses_all_official_gates_and_parameters(self):
        circuit = parse_qasm(ALL_GATES_QASM)

        self.assertEqual([gate.name for gate in circuit.gates], [
            "h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx"
        ])
        self.assertAlmostEqual(circuit.gates[6].params[0], math.pi / 2)
        self.assertAlmostEqual(circuit.gates[9].params[0], math.pi / 4)

    def test_flattens_multiple_registers_and_accepts_comments_and_case(self):
        source = """// user-friendly uppercase should be repairable
        OPENQASM 2.0;
        include "qelib1.inc";
        qreg main[2]; /* an auxiliary qubit */ qreg aux[1];
        creg output[2]; creg flag[1];
        H main[1];
        CX main[1], aux[0];
        measure main[0] -> output[0];
        measure main[1] -> output[1];
        measure aux[0] -> flag[0];
        """
        circuit = parse_qasm(source)

        self.assertEqual((circuit.qubit_count, circuit.cbit_count), (3, 3))
        self.assertEqual(circuit.gates[0].qubits, (1,))
        self.assertEqual(circuit.gates[1].qubits, (1, 2))
        self.assertEqual(circuit.measurements[-1], Measurement(2, 2, "measure aux[0] -> flag[0]"))

    def test_rejects_unsupported_or_malformed_source_statements(self):
        cases = {
            "unknown gate": BELL_QASM.replace("h q[0]", "z q[0]"),
            "missing include": BELL_QASM.replace('include "qelib1.inc";\n', ""),
            "wrong version": BELL_QASM.replace("OPENQASM 2.0", "OPENQASM 3.0"),
            "undeclared register": BELL_QASM.replace("h q[0]", "h nope[0]"),
            "bad parameter": BELL_QASM.replace("h q[0]", "rz(sin(pi)) q[0]"),
            "wrong arity": BELL_QASM.replace("h q[0]", "h q[0], q[1]"),
            "missing semicolon": BELL_QASM.replace("h q[0];", "h q[0]"),
        }
        for label, source in cases.items():
            with self.subTest(label=label), self.assertRaises((QASMParseError, CircuitValidationError)):
                parse_qasm(source)


class CircuitValidatorTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(parse_qasm, "circuit validator is missing")

    def test_rejects_semantically_invalid_circuits(self):
        cases = {
            "qubit out of range": BELL_QASM.replace("h q[0]", "h q[2]"),
            "mismatched whole registers": BELL_QASM.replace("creg c[2]", "creg c[1]"),
            "repeated gate qubit": BELL_QASM.replace("cx q[0], q[1]", "cx q[0], q[0]"),
            "duplicate classical write": BELL_QASM.replace("measure q -> c", "measure q[0] -> c[0]; measure q[1] -> c[0]"),
            "gate after measurement": BELL_QASM.replace("measure q -> c", "measure q -> c; x q[0]"),
            "no measurement": BELL_QASM.replace("measure q -> c;\n", ""),
            "over resource bound": BELL_QASM.replace("qreg q[2]", "qreg q[31]").replace("creg c[2]", "creg c[31]"),
        }
        for label, source in cases.items():
            with self.subTest(label=label), self.assertRaises((QASMParseError, CircuitValidationError)):
                parse_qasm(source)


if __name__ == "__main__":
    unittest.main()
