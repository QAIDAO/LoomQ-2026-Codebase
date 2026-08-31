"""Tests for target serializers and adapter routing."""

import math
import unittest

import adapter
from loomq.parser import parse_qasm
from loomq.serializers import serialize_braket, serialize_originq, serialize_spinq


CUSTOM_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg data[2];
creg result[2];
h data[0];
cx data[0], data[1];
measure data -> result;
"""

FULL_GATE_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
x q[0];
s q[0];
sdg q[0];
t q[0];
tdg q[0];
ry(pi/2) q[0];
rz(-pi/4) q[1];
cx q[0], q[1];
cu1(pi/8) q[0], q[1];
swap q[0], q[1];
ccx q[0], q[1], q[2];
measure q -> c;
"""


class SerializerTests(unittest.TestCase):
    def test_spinq_output_is_complete_and_semantically_parseable(self) -> None:
        output = serialize_spinq(parse_qasm(CUSTOM_QASM))

        self.assertIn("OPENQASM 2.0;", output)
        self.assertIn('include "qelib1.inc";', output)
        self.assertIn("qreg data[2];", output)
        self.assertIn("creg result[2];", output)
        self.assertIn("cx data[0], data[1];", output)
        reparsed = parse_qasm(output)
        self.assertEqual(parse_qasm(CUSTOM_QASM), reparsed)

    def test_braket_output_has_qasm3_declarations_and_operations(self) -> None:
        output = serialize_braket(parse_qasm(CUSTOM_QASM))

        expected_lines = {
            "OPENQASM 3.0;",
            'include "stdgates.inc";',
            "qubit[2] data;",
            "bit[2] result;",
            "h data[0];",
            "cnot data[0], data[1];",
            "result = measure data;",
        }
        self.assertTrue(expected_lines.issubset(set(output.splitlines())))

    def test_braket_can_omit_stdgates_without_changing_program_body(self) -> None:
        circuit = parse_qasm(CUSTOM_QASM)
        default_output = serialize_braket(circuit)
        without_include = serialize_braket(circuit, include_stdgates=False)

        self.assertIn('include "stdgates.inc";', default_output)
        self.assertNotIn('include "stdgates.inc";', without_include)
        # 除 include 外，寄存器、门和测量语句必须保持完全一致。
        self.assertEqual(
            [line for line in default_output.splitlines() if "stdgates.inc" not in line],
            without_include.splitlines(),
        )

    def test_braket_single_bit_measurement(self) -> None:
        circuit = parse_qasm(
            "OPENQASM 2.0; qreg q[1]; creg c[1]; measure q[0] -> c[0];"
        )

        self.assertIn("c[0] = measure q[0];", serialize_braket(circuit))

    def test_spinq_all_gates_round_trip_to_equal_ir(self) -> None:
        circuit = parse_qasm(FULL_GATE_QASM)
        output = serialize_spinq(circuit)

        self.assertEqual(circuit, parse_qasm(output))
        self.assertIn("cu1(%s) q[0], q[1];" % format(math.pi / 8, ".17g"), output)
        self.assertIn("ccx q[0], q[1], q[2];", output)

    def test_braket_maps_controlled_gate_names(self) -> None:
        output = serialize_braket(parse_qasm(FULL_GATE_QASM))

        self.assertIn("cnot q[0], q[1];", output)
        self.assertIn(
            "cp(%s) q[0], q[1];" % format(math.pi / 8, ".17g"),
            output,
        )
        self.assertNotIn("cu1(", output)

    def test_braket_preserves_other_gate_names_and_parameters(self) -> None:
        output = serialize_braket(parse_qasm(FULL_GATE_QASM))
        lines = set(output.splitlines())

        self.assertIn("ry(%s) q[0];" % format(math.pi / 2, ".17g"), lines)
        self.assertIn("rz(%s) q[1];" % format(-math.pi / 4, ".17g"), lines)
        self.assertIn("swap q[0], q[1];", lines)
        self.assertIn("sdg q[0];", lines)
        self.assertIn("tdg q[0];", lines)
        self.assertIn("ccx q[0], q[1], q[2];", lines)

    def test_braket_execution_mode_uses_local_simulator_compatible_gates(self) -> None:
        output = serialize_braket(
            parse_qasm(FULL_GATE_QASM), include_stdgates=False, execution_mode=True
        )

        self.assertNotIn("sdg ", output)
        self.assertNotIn("tdg ", output)
        self.assertNotIn("cp(", output)
        self.assertNotIn("ccx ", output)
        self.assertIn("cphaseshift(%s) q[0], q[1];" % format(math.pi / 8, ".17g"), output)

    def test_adapter_transpiles_full_gate_circuit(self) -> None:
        spinq = adapter.transpile(FULL_GATE_QASM, "spinq")
        braket = adapter.transpile(FULL_GATE_QASM, "braket")

        self.assertEqual(parse_qasm(FULL_GATE_QASM), parse_qasm(spinq))
        self.assertIn(
            "cp(%s) q[0], q[1];" % format(math.pi / 8, ".17g"),
            braket,
        )


class AdapterTests(unittest.TestCase):
    def test_transpile_routes_spinq_and_braket(self) -> None:
        spinq = adapter.transpile(CUSTOM_QASM, "spinq")
        braket = adapter.transpile(CUSTOM_QASM, "braket")

        self.assertTrue(spinq.startswith("OPENQASM 2.0;"))
        self.assertTrue(braket.startswith("OPENQASM 3.0;"))
        self.assertIn('include "stdgates.inc";', braket)
        self.assertIn("cnot data[0], data[1];", braket)

    def test_originq_target_is_supported(self) -> None:
        self.assertTrue(serialize_originq(parse_qasm(CUSTOM_QASM)).startswith("QINIT 2"))
        self.assertTrue(adapter.transpile(CUSTOM_QASM, "originq").startswith("QINIT 2"))

    def test_unsupported_target_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported transpile target"):
            adapter.transpile(CUSTOM_QASM, "unknown")

    def test_non_string_target_is_rejected_cleanly(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported transpile target"):
            adapter.transpile(CUSTOM_QASM, None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
