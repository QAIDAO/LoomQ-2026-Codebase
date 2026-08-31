import math
import unittest

from starter_kit.loomq_l1.errors import (
    ExpressionError,
    QASMParseError,
    QASMSemanticError,
)
from starter_kit.loomq_l1.parser import _remove_comments, parse_qasm


class ParserTests(unittest.TestCase):
    _HEADER = 'OPENQASM 2.0; include "qelib1.inc";'

    def test_parses_complete_contest_circuit_in_operation_order(self):
        circuit = parse_qasm(
            '''
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[3]; creg c[3];
            h q[0]; x q[1]; s q[0]; sdg q[0]; t q[1]; tdg q[1];
            rz(pi/2) q[0]; ry(-pi/4) q[1];
            cx q[0],q[1]; cu1(pi/3) q[1],q[2]; swap q[0],q[2];
            ccx q[0],q[1],q[2];
            measure q -> c;
            '''
        )

        self.assertEqual(circuit.num_qubits, 3)
        self.assertEqual(circuit.num_clbits, 3)
        self.assertEqual(
            tuple(operation.name for operation in circuit.operations),
            ("h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx"),
        )
        self.assertEqual(circuit.operations[0].qubits, (0,))
        self.assertEqual(circuit.operations[8].qubits, (0, 1))
        self.assertEqual(circuit.operations[11].qubits, (0, 1, 2))
        self.assertAlmostEqual(circuit.operations[6].parameter, math.pi / 2)
        self.assertAlmostEqual(circuit.operations[7].parameter, -math.pi / 4)
        self.assertAlmostEqual(circuit.operations[9].parameter, math.pi / 3)
        self.assertEqual(
            tuple((measurement.qubit, measurement.cbit) for measurement in circuit.measurements),
            ((0, 0), (1, 1), (2, 2)),
        )

    def test_flattens_multiple_registers_with_independent_offsets(self):
        circuit = parse_qasm(
            '''
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg left[1]; qreg right[2]; creg out[2];
            cx left[0], right[1]; measure right -> out;
            '''
        )

        self.assertEqual(circuit.operations[0].qubits, (0, 2))
        self.assertEqual(
            tuple((measurement.qubit, measurement.cbit) for measurement in circuit.measurements),
            ((1, 0), (2, 1)),
        )

    def test_removes_line_and_block_comments_before_statement_splitting(self):
        circuit = parse_qasm(
            '''
            // header comment
            OPENQASM 2.0; /* include comment ; */
            include "qelib1.inc";
            qreg q[1]; // gate comment ;
            creg c[1];
            h q[0]; /* measurement comment */ measure q -> c;
            '''
        )

        self.assertEqual(circuit.operations[0].name, "h")
        self.assertEqual(tuple((item.qubit, item.cbit) for item in circuit.measurements), ((0, 0),))

    def test_terminates_line_comments_on_carriage_return(self):
        circuit = parse_qasm(
            "// c\rOPENQASM 2.0;\rinclude \"qelib1.inc\";\r"
            "qreg q[1];\rcreg c[1];\rmeasure q[0] -> c[0];"
        )

        self.assertEqual(
            tuple((item.qubit, item.cbit) for item in circuit.measurements), ((0, 0),)
        )

    def test_scans_large_lf_only_comment_heavy_source_without_suffix_searches(self):
        class TrackingSource(str):
            find_calls = 0

            def find(self, *args):
                self.find_calls += 1
                return super().find(*args)

        source = TrackingSource(
            "".join("// comment\n" for _ in range(4096))
            + self._HEADER
            + " qreg q[1]; creg c[1];"
        )
        circuit = parse_qasm(_remove_comments(source))

        self.assertEqual(circuit.num_qubits, 1)
        self.assertEqual(source.find_calls, 0)

    def test_treats_inline_block_comment_as_token_separator(self):
        circuit = parse_qasm(
            '''
            OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[1]; creg c[1];
            measure/* delimiter */q[0] -> c[0];
            '''
        )

        self.assertEqual(
            tuple((item.qubit, item.cbit) for item in circuit.measurements), ((0, 0),)
        )

    def test_accepts_ascii_whitespace_after_measure_keyword(self):
        for separator in ("\t", "\n", "\r"):
            with self.subTest(separator=repr(separator)):
                circuit = parse_qasm(
                    self._HEADER
                    + " qreg q[1]; creg c[1]; measure"
                    + separator
                    + "q[0] -> c[0];"
                )
                self.assertEqual(
                    tuple((item.qubit, item.cbit) for item in circuit.measurements),
                    ((0, 0),),
                )

    def test_accepts_ascii_whitespace_in_header_and_include_declarations(self):
        circuit = parse_qasm(
            'OPENQASM \t\r\n 2.0; include\r\n\t "qelib1.inc"; qreg q[1]; creg c[1];'
        )

        self.assertEqual(circuit.num_qubits, 1)

    def test_accepts_ascii_whitespace_in_register_declaration_brackets(self):
        circuit = parse_qasm(
            self._HEADER + " qreg\tq \r[\n1\t]; creg\r\nc\t[\r1\n];"
        )

        self.assertEqual(circuit.num_qubits, 1)
        self.assertEqual(circuit.num_clbits, 1)

    def test_accepts_ascii_whitespace_before_parameter_gate_parenthesis(self):
        circuit = parse_qasm(self._HEADER + " qreg q[1]; creg c[1]; rz \t(pi/2) q[0];")

        self.assertAlmostEqual(circuit.operations[0].parameter, math.pi / 2)

    def test_accepts_parameter_gate_operand_adjacent_to_closing_parenthesis(self):
        circuit = parse_qasm(
            self._HEADER
            + " qreg q[2]; creg c[2]; rz(pi/2)q[0]; ry(-pi/4)q[1]; cu1(pi/3)q[0],q[1];"
        )

        self.assertEqual(
            tuple(operation.name for operation in circuit.operations),
            ("rz", "ry", "cu1"),
        )
        self.assertAlmostEqual(circuit.operations[0].parameter, math.pi / 2)
        self.assertAlmostEqual(circuit.operations[1].parameter, -math.pi / 4)
        self.assertAlmostEqual(circuit.operations[2].parameter, math.pi / 3)
        self.assertEqual(circuit.operations[0].qubits, (0,))
        self.assertEqual(circuit.operations[1].qubits, (1,))
        self.assertEqual(circuit.operations[2].qubits, (0, 1))

    def test_accepts_ascii_whitespace_in_gate_operands_and_commas(self):
        circuit = parse_qasm(
            self._HEADER + " qreg q[2]; creg c[2]; cx q \t[ 0\r] \n,\tq [\n1 ];"
        )

        self.assertEqual(circuit.operations[0].qubits, (0, 1))

    def test_accepts_ascii_whitespace_in_measurement_operands(self):
        circuit = parse_qasm(
            self._HEADER + " qreg q[1]; creg c[1]; measure q [\t0 ] -> c\r[ 0 ];"
        )

        self.assertEqual(
            tuple((item.qubit, item.cbit) for item in circuit.measurements), ((0, 0),)
        )

    def test_requires_quantum_and_classical_registers(self):
        cases = (
            self._HEADER,
            self._HEADER + " qreg q[1];",
            self._HEADER + " creg c[1];",
        )
        for source in cases:
            with self.subTest(source=source):
                with self.assertRaises(QASMSemanticError):
                    parse_qasm(source)

    def test_rejects_repeated_qubit_operands_in_multi_qubit_gate(self):
        with self.assertRaises(QASMSemanticError):
            parse_qasm(self._HEADER + " qreg q[1]; creg c[1]; cx q[0],q[0];")

    def test_rejects_non_ascii_whitespace_in_parser_grammar(self):
        cases = (
            'OPENQASM 2.0; include "qelib1.inc"; qreg\u00a0q[1];',
            self._HEADER + " qreg q[1]; h\u00a0q[0];",
        )
        for source in cases:
            with self.subTest(source=source):
                with self.assertRaises(QASMParseError):
                    parse_qasm(source)

    def test_comment_only_source_raises_parser_error(self):
        with self.assertRaises(QASMParseError):
            parse_qasm("// comment only\n/* another comment */")

    def test_allows_multiple_nonduplicate_measurements_in_statement_order(self):
        circuit = parse_qasm(
            self._HEADER
            + " qreg q[2]; creg c[2]; measure q[1] -> c[1]; measure q[0] -> c[0];"
        )

        self.assertEqual(
            tuple((item.qubit, item.cbit) for item in circuit.measurements), ((1, 1), (0, 0))
        )

    def test_rejects_oversized_register_size_without_raw_exception(self):
        with self.assertRaises(QASMParseError):
            parse_qasm(self._HEADER + " qreg q[" + "9" * 5000 + "];")

    def test_rejects_register_sizes_above_supported_width(self):
        for declaration in ("qreg q[4097]", "creg c[4097]"):
            with self.subTest(declaration=declaration):
                with self.assertRaises(QASMSemanticError):
                    parse_qasm(self._HEADER + " " + declaration + ";")

    def test_rejects_cumulative_register_width_above_supported_width(self):
        cases = (
            self._HEADER + " qreg a[4096]; qreg b[1];",
            self._HEADER + " creg a[4096]; creg b[1];",
        )
        for source in cases:
            with self.subTest(source=source):
                with self.assertRaises(QASMSemanticError):
                    parse_qasm(source)

    def test_rejects_oversized_operand_index_without_raw_exception(self):
        with self.assertRaises(QASMParseError):
            parse_qasm(self._HEADER + " qreg q[1]; h q[" + "9" * 5000 + "];")

    def test_rejects_invalid_qasm_statements(self):
        cases = (
            ("missing header", 'include "qelib1.inc"; qreg q[1];', QASMParseError),
            ("missing include", "OPENQASM 2.0; qreg q[1];", QASMParseError),
            (
                "duplicate header",
                'OPENQASM 2.0; OPENQASM 2.0; include "qelib1.inc";',
                QASMParseError,
            ),
            (
                "duplicate include",
                'OPENQASM 2.0; include "qelib1.inc"; include "qelib1.inc";',
                QASMParseError,
            ),
            ("wrong header", 'OPENQASM 3.0; include "qelib1.inc";', QASMParseError),
            ("wrong include", 'OPENQASM 2.0; include "other.inc";', QASMParseError),
            ("wrong header order", 'include "qelib1.inc"; OPENQASM 2.0;', QASMParseError),
            (
                "declaration before headers",
                'qreg q[1]; OPENQASM 2.0; include "qelib1.inc";',
                QASMParseError,
            ),
            (
                "include after declaration",
                'OPENQASM 2.0; qreg q[1]; include "qelib1.inc";',
                QASMParseError,
            ),
            ("empty source", " \t\n", QASMParseError),
            ("duplicate register", self._HEADER + " qreg q[1]; creg q[1];", QASMSemanticError),
            ("zero register size", self._HEADER + " qreg q[0];", QASMSemanticError),
            ("unknown gate", self._HEADER + " qreg q[1]; nope q[0];", QASMSemanticError),
            ("wrong gate arity", self._HEADER + " qreg q[2]; cx q[0];", QASMSemanticError),
            ("missing parameter", self._HEADER + " qreg q[1]; rz q[0];", QASMSemanticError),
            ("non-parameter gate parameter", self._HEADER + " qreg q[1]; h(pi/2) q[0];", QASMSemanticError),
            (
                "excess parameter form",
                self._HEADER + " qreg q[1]; rz(pi/2)(pi/3) q[0];",
                QASMParseError,
            ),
            ("unknown register", self._HEADER + " qreg q[1]; h missing[0];", QASMSemanticError),
            (
                "register type mismatch",
                self._HEADER + " qreg q[1]; creg c[1]; h c[0];",
                QASMSemanticError,
            ),
            ("out of range index", self._HEADER + " qreg q[1]; h q[1];", QASMSemanticError),
            (
                "unequal whole-register measurement",
                self._HEADER + " qreg q[2]; creg c[1]; measure q -> c;",
                QASMSemanticError,
            ),
            (
                "duplicate classical destination",
                self._HEADER
                + " qreg q[2]; creg c[1]; measure q[0] -> c[0]; measure q[1] -> c[0];",
                QASMSemanticError,
            ),
            (
                "gate after measurement",
                self._HEADER + " qreg q[1]; creg c[1]; measure q[0] -> c[0]; h q[0];",
                QASMSemanticError,
            ),
            ("malformed operand", self._HEADER + " qreg q[1]; h q;", QASMParseError),
            (
                "malformed measurement",
                self._HEADER + " qreg q[1]; creg c[1]; measure q[0] c[0];",
                QASMParseError,
            ),
            ("unterminated final statement", self._HEADER + " qreg q[1]", QASMParseError),
            (
                "unterminated block comment",
                self._HEADER + " qreg q[1]; /* unfinished",
                QASMParseError,
            ),
            ("non-ascii identifier", self._HEADER + " qreg qé[1];", QASMParseError),
            ("non-ascii digit", self._HEADER + " qreg q[١];", QASMParseError),
        )
        for name, source, error_type in cases:
            with self.subTest(name=name):
                with self.assertRaises(error_type):
                    parse_qasm(source)

    def test_parameter_expression_error_is_semantic_and_preserves_cause(self):
        source = self._HEADER + " qreg q[1]; rz(pi+*2) q[0];"

        with self.assertRaises(QASMSemanticError) as raised:
            parse_qasm(source)

        self.assertIsInstance(raised.exception.__cause__, ExpressionError)
        self.assertIn("rz", str(raised.exception))
        self.assertIn("pi+*2", str(raised.exception))

    def test_semantic_errors_identify_the_offending_statement(self):
        statement = "h missing[0]"
        with self.assertRaises(QASMSemanticError) as raised:
            parse_qasm(self._HEADER + " qreg q[1]; " + statement + ";")

        self.assertIn(statement, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
