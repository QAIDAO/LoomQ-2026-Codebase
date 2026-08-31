"""Unit tests for Hybrid-QASM lexing, parsing, and quantum extraction."""

from __future__ import annotations

import unittest

from loomq.hybrid.ast import Assignment, BinaryExpression, IfStatement
from loomq.hybrid.parser import parse_hybrid_program
from loomq.hybrid.tokens import HybridSyntaxError


HEADER = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
"""


class HybridParserTests(unittest.TestCase):
    def test_quantum_operations_are_stable_and_keep_source_order(self) -> None:
        source = HEADER + """
            h   q [ 0 ] ;
            measure q[0]->c[0];
            classical { r1 = 1; }
            rz(-pi/4) q[1];
            cx q[0],q[2]; // classical { is inert in a comment
            measure q[2] -> c[2];
        """
        program = parse_hybrid_program(source)
        self.assertEqual(
            program.quantum_operations,
            (
                "h q[0];",
                "measure q[0] -> c[0];",
                "rz(- pi / 4) q[1];",
                "cx q[0], q[2];",
                "measure q[2] -> c[2];",
            ),
        )
        self.assertEqual(program.declared_measurements, (0, 1, 2))

    def test_subtraction_is_left_associative(self) -> None:
        program = parse_hybrid_program(HEADER + "classical { r1 = 20 - 5 - 3; }")
        assignment = program.classical_statements[0]
        self.assertIsInstance(assignment, Assignment)
        assert isinstance(assignment, Assignment)
        self.assertIsInstance(assignment.value, BinaryExpression)
        assert isinstance(assignment.value, BinaryExpression)
        self.assertEqual(assignment.value.operator, "-")
        self.assertIsInstance(assignment.value.left, BinaryExpression)

    def test_nested_if_else_if_and_no_else(self) -> None:
        source = HEADER + """
        classical {
          if (c[0] != 0) {
            if (c[1] == c[2]) { r1 = -7; }
          } else if (r1 == 0) {
            r1 = +(2 + 3);
          }
          if (r1 != c[0]) { r2 = r1; }
        }
        """
        program = parse_hybrid_program(source)
        first = program.classical_statements[0]
        self.assertIsInstance(first, IfStatement)
        assert isinstance(first, IfStatement)
        self.assertTrue(first.has_else)
        self.assertIsInstance(first.then_body[0], IfStatement)
        self.assertIsInstance(first.else_body[0], IfStatement)
        last = program.classical_statements[1]
        self.assertIsInstance(last, IfStatement)
        assert isinstance(last, IfStatement)
        self.assertFalse(last.has_else)

    def test_multiple_classical_blocks_retain_classical_sequence(self) -> None:
        source = HEADER + """
        h q[0];
        classical { r1 = 1; }
        x q[1];
        classical { r1 = r1 + 2; r2 = r1; }
        measure q[1] -> c[1];
        """
        program = parse_hybrid_program(source)
        self.assertEqual(len(program.classical_statements), 3)
        self.assertEqual(
            program.quantum_operations,
            ("h q[0];", "x q[1];", "measure q[1] -> c[1];"),
        )

    def test_rejects_invalid_classical_forms_with_location(self) -> None:
        bad_fragments = (
            "classical { r0 = 1; }",
            "classical { r1 = 1.5; }",
            "classical { r1 = c[22]; }",
            "classical { if (r1 = 1) { r2 = 2; } }",
            "classical { r1 = 1 }",
        )
        for fragment in bad_fragments:
            with self.subTest(fragment=fragment):
                with self.assertRaisesRegex(HybridSyntaxError, r"line \d+, column \d+"):
                    parse_hybrid_program(HEADER + fragment)


if __name__ == "__main__":
    unittest.main()
