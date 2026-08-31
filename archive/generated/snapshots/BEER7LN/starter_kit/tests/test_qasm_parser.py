"""Regression tests for the restricted OpenQASM 2.0 parser."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

from loomq.qasm import QasmParseError, parse_openqasm2, serialize_openqasm2  # noqa: E402
from loomq.transpilers.braket import serialize_openqasm3  # noqa: E402
from loomq.transpilers.originq import serialize_originir  # noqa: E402


class QasmParserTests(unittest.TestCase):
    def test_round_trip_all_whitelisted_gates(self) -> None:
        source = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[3];
creg c[3];
h q[0];
x q[1];
s q[2];
sdg q[2];
t q[1];
tdg q[1];
rz(pi/2) q[0];
ry(-0.25) q[1];
cx q[0], q[1];
cu1(pi/4) q[0], q[1];
swap q[1], q[2];
ccx q[0], q[1], q[2];
measure q -> c;
"""
        rendered = serialize_openqasm2(parse_openqasm2(source))
        self.assertEqual(rendered, source)

    def test_rejects_unknown_gate(self) -> None:
        source = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[1];
creg c[1];
z q[0];
measure q -> c;
"""
        with self.assertRaisesRegex(QasmParseError, "unsupported gate"):
            parse_openqasm2(source)

    def test_target_renderers_preserve_cu1_and_measurement(self) -> None:
        source = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[2];
creg c[2];
cu1(pi/4) q[0], q[1];
measure q -> c;
"""
        program = parse_openqasm2(source)
        originir = serialize_originir(program)
        qasm3 = serialize_openqasm3(program)
        self.assertIn("CU1(pi/4) q[0], q[1]", originir)
        self.assertIn("MEASURE q[0], c[0]", originir)
        self.assertIn('include "stdgates.inc";', qasm3)
        self.assertIn("cp(pi/4) q[0], q[1];", qasm3)
        self.assertIn("c = measure q;", qasm3)

    def test_nested_parameter_parentheses_are_preserved(self) -> None:
        source = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[1];
creg c[1];
rz((pi/2)+0.125) q[0];
measure q -> c;
"""
        program = parse_openqasm2(source)
        self.assertEqual(program.operations[0].parameter, "(pi/2)+0.125")
        self.assertIn("rz((pi/2)+0.125) q[0];", serialize_openqasm2(program))


if __name__ == "__main__":
    unittest.main()
