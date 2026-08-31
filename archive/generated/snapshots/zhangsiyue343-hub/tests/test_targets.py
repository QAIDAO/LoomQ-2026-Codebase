"""Dialect emitters: golden shapes + round-trip parseability."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starter_kit.adapter import transpile

GHZ3 = ('OPENQASM 2.0; include "qelib1.inc";\n'
        "qreg q[3]; creg c[3];\n"
        "h q[0]; cx q[0],q[1]; cx q[1],q[2];\n"
        "measure q -> c;\n")

PARAMS = ("OPENQASM 2.0; include \"qelib1.inc\";\n"
          "qreg q[2]; creg c[2];\n"
          "sdg q[0]; tdg q[1]; rz(-pi/4) q[0]; ry(pi/3) q[1];\n"
          "cu1(pi/6) q[0], q[1];\n"
          "measure q -> c;\n")


def _angle_value(token: str) -> float:
    """Evaluate an emitted angle: decimal, multiple-of-pi, or pi arithmetic."""
    token = token.replace(" ", "")
    if "pi" in token:
        expr = token.replace("pi", str(3.141592653589793))
        return eval(expr, {"__builtins__": {}})  # noqa: S307 - test fixture only
    return float(token)


class TestOpenQasm2(unittest.TestCase):
    def test_ghz_golden(self):
        text = transpile(GHZ3, "spinq")
        self.assertEqual(
            [line for line in text.strip().splitlines()],
            ['OPENQASM 2.0;', 'include "qelib1.inc";',
             'qreg q[3];', 'creg c[3];',
             'h q[0];', 'cx q[0], q[1];', 'cx q[1], q[2];',
             'measure q[0] -> c[0];', 'measure q[1] -> c[1];',
             'measure q[2] -> c[2];'])

    def test_params_numeric_within_tolerance(self):
        """Contract requires numeric equivalence; symbolic or decimal both OK."""
        import re

        text = transpile(PARAMS, "spinq")
        self.assertIn("sdg q[0];", text)
        expected = {"rz": -3.141592653589793 / 4,
                    "ry": 3.141592653589793 / 3,
                    "cu1": 3.141592653589793 / 6}
        for gate, angle in expected.items():
            match = re.search(r"%s\((-?[\d.eE+pi/]+)\)" % gate, text)
            self.assertIsNotNone(match, gate)
            value = _angle_value(match.group(1))
            self.assertAlmostEqual(value, angle, places=9, msg=gate)

    def test_round_trip(self):
        from starter_kit.parser import parse_source
        from starter_kit.gates import GATES
        text = transpile(PARAMS, "spinq")
        program = parse_source(text, GATES)      # emitted code must re-parse
        self.assertEqual(len(program.statements), 7)


class TestOriginIR(unittest.TestCase):
    def test_canonical_form(self):
        text = transpile(GHZ3, "originq")
        lines = text.strip().splitlines()
        self.assertEqual(lines[0], "QINIT 3")
        self.assertEqual(lines[1], "CREG 3")
        self.assertIn("CNOT q[0], q[1]", lines)
        self.assertTrue(all(line == line.upper()[:6] or line.startswith("MEASURE")
                            or line.split()[0].isupper() for line in lines[2:]))

    def test_decimal_params_per_contract(self):
        import re

        text = transpile(PARAMS, "originq")
        self.assertNotIn("pi", text.lower().replace("qubit", ""))
        self.assertRegex(text, r"SDAG q\[0\]")
        for gate, angle in (("RZ", -3.141592653589793 / 4),
                            ("RY", 3.141592653589793 / 3),
                            ("CU1", 3.141592653589793 / 6)):
            match = re.search(r"%s\((-?[\d.eE+]+)\)" % gate, text)
            self.assertIsNotNone(match, gate)
            self.assertAlmostEqual(float(match.group(1)), angle,
                                   places=9, msg=gate)


class TestOpenQasm3(unittest.TestCase):
    def test_header_and_measure_all(self):
        text = transpile(GHZ3, "braket")
        self.assertTrue(text.startswith("OPENQASM 3.0;"))
        self.assertIn('include "stdgates.inc";', text)
        self.assertIn("qubit[3] q;", text)
        self.assertIn("bit[3] c;", text)
        # contract accepts whole-register OR per-bit measure assignments
        has_register_form = "c = measure q;" in text
        has_per_bit_form = all(("c[%d] = measure q[%d];" % (i, i)) in text
                               for i in range(3))
        self.assertTrue(has_register_form or has_per_bit_form, text)

    def test_cnot_spelling_accepted_by_braket(self):
        self.assertIn("cnot", transpile(GHZ3, "braket"))


class TestUnknownTarget(unittest.TestCase):
    def test_rejected_with_clear_error(self):
        with self.assertRaises(ValueError) as ctx:
            transpile(GHZ3, "qiskit")
        self.assertIn("unsupported", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
