"""Parser front-end tests: grammar coverage beyond line-regex parsers."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starter_kit.gates import GATES
from starter_kit.ir import eval_expr
from starter_kit.parser import ParseError, parse_source


def parse(text):
    return parse_source(text, GATES)


class TestExpressions(unittest.TestCase):
    def test_pi_arithmetic(self):
        program = parse("qreg q[1]; creg c[1]; rz(pi/2) q[0];")
        value = eval_expr(program.statements[0].params[0])
        self.assertAlmostEqual(value, 3.14159265358979 / 2, places=12)

    def test_nested_parentheses_and_functions(self):
        program = parse("qreg q[1]; creg c[1]; ry(cos(pi/4)*2-(0.5+0.25)) q[0];")
        value = eval_expr(program.statements[0].params[0])
        self.assertAlmostEqual(value, 1.41421356 * 1 - 0.75, places=6)

    def test_unary_minus(self):
        program = parse("qreg q[1]; creg c[1]; rz(-pi/4) q[0];")
        value = eval_expr(program.statements[0].params[0])
        self.assertAlmostEqual(value, -0.7853981633974483, places=12)


class TestGrammar(unittest.TestCase):
    def test_all_twelve_gates_parse(self):
        source = """
        qreg q[3]; creg c[3];
        h q[0]; x q[0]; s q[0]; sdg q[0]; t q[0]; tdg q[0];
        rz(0.3) q[0]; ry(pi) q[1];
        cx q[0], q[1]; cu1(pi/3) q[1], q[2];
        swap q[0], q[2]; ccx q[0], q[1], q[2];
        measure q -> c;
        """
        program = parse(source)
        gate_calls = [s for s in program.statements if hasattr(s, "gate")]
        self.assertEqual(len(gate_calls), 12)

    def test_case_insensitive_gate_names(self):
        # gate names fold to lowercase; register names stay case-sensitive
        program = parse('OPENQASM 2.0; include "qelib1.inc"; '
                        "qreg q[2]; creg c[2]; CX q[0], q[1]; H q[0]; measure q->c;")
        gates = [s.gate for s in program.statements if hasattr(s, "gate")]
        self.assertEqual(gates, ["cx", "h"])

    def test_arbitrary_register_names(self):
        source = ("qreg data[2]; qreg ancilla[1]; creg result[3];"
                  "h data[0]; cx data[0], ancilla[0];"
                  "measure data[0] -> result[0];"
                  "measure ancilla[0] -> result[2];")
        program = parse(source)
        self.assertEqual((program.n_qubits, program.n_clbits), (3, 3))

    def test_register_broadcast(self):
        program = parse("qreg q[4]; creg c[4]; h q; measure q -> c;")
        h_calls = [s for s in program.statements if getattr(s, "gate", "") == "h"]
        self.assertEqual(len(h_calls), 1)          # single statement...

        from starter_kit.ir import lower
        circuit = lower(program)
        h_ops = [op for op in circuit.ops if op[0] == "h"]
        self.assertEqual(len(h_ops), 4)            # ...expanded to four ops

    def test_comments_and_whitespace_free_layout(self):
        source = ("OPENQASM 2.0; /* header */ include \"qelib1.inc\";\n"
                  "qreg q[2];\n// bit registers\ncreg c[2];\n"
                  "h\n q[0]\n ;\ncx q[0],q[1];measure q -> c;")
        program = parse(source)
        self.assertEqual(len(program.statements), 3)   # h, cx, measure

    def test_missing_version_line_is_tolerated(self):
        program = parse("qreg q[1]; creg c[1]; x q[0]; measure q[0] -> c[0];")
        self.assertTrue(program.statements)


class TestErrors(unittest.TestCase):
    def assert_parse_error(self, source):
        with self.assertRaises(ParseError):
            parse(source)

    def test_unknown_gate_rejected(self):
        self.assert_parse_error("qreg q[1]; creg c[1]; foo q[0];")

    def test_arity_mismatch_rejected(self):
        self.assert_parse_error("qreg q[1]; creg c[1]; cx q[0];")

    def test_param_count_mismatch_rejected(self):
        self.assert_parse_error("qreg q[1]; creg c[1]; h(pi) q[0];")

    def test_index_out_of_range_rejected(self):
        self.assert_parse_error("qreg q[2]; creg c[2]; h q[2];")

    def test_duplicate_register_rejected(self):
        self.assert_parse_error("qreg q[2]; qreg q[1]; creg c[1];")

    def test_undeclared_register_rejected(self):
        self.assert_parse_error("qreg q[2]; creg c[2]; h z[0];")


if __name__ == "__main__":
    unittest.main()
