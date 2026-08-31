import unittest

try:
    from starter_kit import adapter
    from starter_kit.loomq_core.qasm2 import parse_qasm2
except ModuleNotFoundError:
    import adapter
    from loomq_core.qasm2 import parse_qasm2


ALL_GATES = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[4];
creg c[4];
h q[0];
x q[1];
s q[0];
sdg q[0];
t q[1];
tdg q[1];
rz(pi/3) q[2];
ry(-pi/5) q[3];
cx q[0],q[1];
cu1(pi/7) q[1],q[2];
swap q[2],q[3];
ccx q[0],q[1],q[3];
measure q -> c;
"""

QFT4 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[4]; creg c[4];
x q[0];
h q[3]; cu1(pi/2) q[2],q[3]; cu1(pi/4) q[1],q[3]; cu1(pi/8) q[0],q[3];
h q[2]; cu1(pi/2) q[1],q[2]; cu1(pi/4) q[0],q[2];
h q[1]; cu1(pi/2) q[0],q[1]; h q[0];
swap q[0],q[3]; swap q[1],q[2];
measure q -> c;
"""

GROVER3 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3]; creg c[3];
h q[0]; h q[1]; h q[2];
h q[2]; ccx q[0],q[1],q[2]; h q[2];
h q[0]; h q[1]; h q[2];
x q[0]; x q[1]; x q[2];
h q[2]; ccx q[0],q[1],q[2]; h q[2];
x q[0]; x q[1]; x q[2];
h q[0]; h q[1]; h q[2];
measure q -> c;
"""


class L1CoreTests(unittest.TestCase):
    def test_all_whitelisted_gates_execute_for_every_target(self):
        circuit = parse_qasm2(ALL_GATES)
        self.assertEqual(len(circuit.operations), 12)
        for target in adapter.SUPPORTED_TARGETS:
            with self.subTest(target=target):
                result = adapter.run(ALL_GATES, target, 8192)
                self.assertEqual(sum(result["counts"].values()), 8192)
                self.assertEqual(result["bit_order"], "little")

    def test_classical_keys_use_rightmost_bit_for_c_zero(self):
        source = """OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[3]; creg c[3];
        x q[0]; measure q -> c;
        """
        self.assertEqual(adapter.run(source, "spinq", 100)["counts"], {"001": 100})

    def test_parameter_parser_rejects_code_and_unknown_names(self):
        source = """OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[1]; creg c[1];
        rz(__import__('os')) q[0]; measure q -> c;
        """
        with self.assertRaisesRegex(ValueError, "Unsupported gate parameter"):
            parse_qasm2(source)

    def test_block_comments_and_register_wide_gates_are_supported(self):
        source = """OPENQASM 2.0;
        include "qelib1.inc";
        /* Apply H to every qubit. */
        qreg q[3]; creg c[3];
        h q;
        measure q -> c;
        """
        circuit = parse_qasm2(source)
        self.assertEqual(len(circuit.operations), 3)
        self.assertEqual(set(adapter.run(source, "spinq", 8192)["counts"].values()), {1024})

    def test_target_headers_and_gate_names(self):
        self.assertTrue(adapter.transpile(ALL_GATES, "spinq").startswith("OPENQASM 2.0;"))
        braket = adapter.transpile(ALL_GATES, "braket")
        self.assertTrue(braket.startswith("OPENQASM 3.0;"))
        self.assertIn("cnot q[0], q[1];", braket)
        self.assertIn("cp(", braket)
        origin = adapter.transpile(ALL_GATES, "originq")
        self.assertIn("QINIT 4", origin)
        self.assertIn("CNOT q[0], q[1]", origin)
        self.assertIn("TOFFOLI q[0], q[1], q[3]", origin)

    def test_qft4_has_uniform_measurement_distribution(self):
        counts = adapter.run(QFT4, "braket", 8192)["counts"]
        self.assertEqual(len(counts), 16)
        self.assertEqual(set(counts.values()), {512})

    def test_grover3_amplifies_the_marked_state(self):
        counts = adapter.run(GROVER3, "originq", 8192)["counts"]
        self.assertEqual(max(counts, key=counts.get), "111")
        self.assertEqual(counts["111"], 6400)

    def test_invalid_target_and_shots_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Unsupported target"):
            adapter.transpile(ALL_GATES, "unknown")
        with self.assertRaisesRegex(ValueError, "shots"):
            adapter.run(ALL_GATES, "spinq", 0)


if __name__ == "__main__":
    unittest.main()
