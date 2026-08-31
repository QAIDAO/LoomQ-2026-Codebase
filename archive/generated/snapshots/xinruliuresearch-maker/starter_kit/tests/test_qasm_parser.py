import unittest

from loomq.qasm import (
    BinaryExpr,
    GateStatement,
    MeasureStatement,
    QASMLexError,
    QASMParseError,
    UnaryExpr,
    parse_qasm2,
)


class QASMParserTests(unittest.TestCase):
    def test_parses_header_include_registers_and_operations(self):
        program = parse_qasm2(
            """\
OPENQASM 2.0;
include "qelib1.inc";
qreg input_data[3];
creg readout_bits[3];
rz(-(pi / 2) + 1e-3) input_data[1];
measure input_data -> readout_bits;
"""
        )

        self.assertEqual(program.version, "2.0")
        self.assertEqual(program.includes[0].path, "qelib1.inc")
        self.assertEqual(
            [(decl.kind, decl.name, decl.size) for decl in program.declarations],
            [("qreg", "input_data", 3), ("creg", "readout_bits", 3)],
        )
        gate = program.statements[0]
        self.assertIsInstance(gate, GateStatement)
        self.assertEqual(gate.name, "rz")
        self.assertIsInstance(gate.parameters[0], BinaryExpr)
        self.assertIsInstance(gate.parameters[0].left, UnaryExpr)
        self.assertIsInstance(program.statements[1], MeasureStatement)

    def test_comments_bom_crlf_and_leading_dot_number(self):
        source = (
            "\ufeffOPENQASM 2.00; // header\r\n"
            'include "qelib1.inc";\r\n'
            "qreg amplitudes[1];\r\n"
            "rz(.5E+1) amplitudes[0]; // operation\r\n"
        )
        program = parse_qasm2(source)
        self.assertEqual(program.declarations[0].name, "amplitudes")
        self.assertEqual(program.statements[0].parameters[0].text, ".5E+1")

    def test_reports_line_column_and_suggestion(self):
        source = "OPENQASM 2.0;\nqreg data[2]\nh data[0];\n"
        with self.assertRaises(QASMParseError) as caught:
            parse_qasm2(source)
        error = caught.exception
        self.assertEqual((error.line, error.column), (3, 1))
        self.assertIn("expected ';'", str(error))
        self.assertTrue(error.suggestion)

    def test_rejects_wrong_version(self):
        with self.assertRaisesRegex(QASMParseError, "unsupported OpenQASM version"):
            parse_qasm2("OPENQASM 3.0;")

    def test_rejects_missing_magic(self):
        with self.assertRaisesRegex(QASMParseError, "expected 'OPENQASM'"):
            parse_qasm2("OPENQAS 2.0;")

    def test_rejects_illegal_character(self):
        with self.assertRaises(QASMLexError) as caught:
            parse_qasm2("OPENQASM 2.0;\nqreg q_data[1];\nh @q_data[0];")
        self.assertEqual((caught.exception.line, caught.exception.column), (3, 3))

    def test_rejects_malformed_exponent(self):
        with self.assertRaisesRegex(QASMLexError, "exponent has no digits"):
            parse_qasm2("OPENQASM 2.0; qreg data[1]; rz(1e+) data[0];")

    def test_rejects_decimal_register_size_and_index(self):
        with self.assertRaisesRegex(QASMParseError, "register size must be an integer"):
            parse_qasm2("OPENQASM 2.0; qreg data[2.0];")
        with self.assertRaisesRegex(QASMParseError, "register index must be an integer"):
            parse_qasm2("OPENQASM 2.0; qreg data[2]; h data[1.0];")

    def test_rejects_empty_parameter_list(self):
        with self.assertRaisesRegex(QASMParseError, "empty gate parameter"):
            parse_qasm2("OPENQASM 2.0; qreg data[1]; h() data[0];")

    def test_top_level_constructs_can_be_interleaved(self):
        program = parse_qasm2(
            "OPENQASM 2.0; qreg first[1]; h first[0]; qreg late[1];"
        )
        self.assertEqual([item.name for item in program.declarations], ["first", "late"])
        self.assertEqual(program.statements[0].name, "h")

    def test_measurement_requires_arrow(self):
        with self.assertRaisesRegex(QASMParseError, "expected '->'"):
            parse_qasm2(
                "OPENQASM 2.0; qreg source[1]; creg result[1]; "
                "measure source[0], result[0];"
            )


if __name__ == "__main__":
    unittest.main()
