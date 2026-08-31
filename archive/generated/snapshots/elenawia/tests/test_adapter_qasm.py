import unittest

from starter_kit.adapter import QASMParseError, run, transpile


class QASMTranspileTests(unittest.TestCase):
    def test_spinq_transpile_normalizes_public_bell_circuit(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
"""

        self.assertEqual(
            transpile(source, "spinq"),
            """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
""",
        )

    def test_spinq_transpile_accepts_parameterized_whitelist_gates(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
rz(pi/2) q[0];
cu1(0.25) q[0], q[1];
measure q[0] -> c[0];
"""

        output = transpile(source, "spinq")

        self.assertIn("rz(pi/2) q[0];", output)
        self.assertIn("cu1(0.25) q[0], q[1];", output)
        self.assertIn("measure q[0] -> c[0];", output)

    def test_originq_transpile_emits_originir_for_bell_circuit(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""

        self.assertEqual(
            transpile(source, "originq"),
            """QINIT 2
CREG 2
H q[0]
CNOT q[0], q[1]
MEASURE q[0], c[0]
MEASURE q[1], c[1]
""",
        )

    def test_originq_run_reuses_local_simulator(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""

        result = run(source, "originq", 128)

        self.assertEqual(result["backend"], "originq_local_simulator")
        self.assertEqual(result["shots"], 128)
        self.assertEqual(set(result["counts"]), {"00", "11"})

    def test_braket_transpile_emits_openqasm3_for_bell_circuit(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""

        self.assertEqual(
            transpile(source, "braket"),
            """OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cnot q[0], q[1];
c = measure q;
""",
        )

    def test_braket_run_reuses_local_simulator(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""

        result = run(source, "braket", 128)

        self.assertEqual(result["backend"], "braket_local_simulator")
        self.assertEqual(result["shots"], 128)
        self.assertEqual(set(result["counts"]), {"00", "11"})

    def test_spinq_transpile_rejects_non_whitelist_gate(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
z q[0];
measure q -> c;
"""

        with self.assertRaises(QASMParseError):
            transpile(source, "spinq")

    def test_spinq_run_returns_counts_for_bell_circuit(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""

        result = run(source, "spinq", 128)

        self.assertEqual(result["backend"], "spinq_local_simulator")
        self.assertEqual(result["shots"], 128)
        self.assertEqual(result["bit_order"], "little")
        self.assertEqual(sum(result["counts"].values()), 128)
        self.assertEqual(set(result["counts"]), {"00", "11"})

    def test_spinq_run_supports_all_contest_gates(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
x q[1];
s q[1];
sdg q[1];
t q[1];
tdg q[1];
rz(pi/2) q[0];
ry(0.25) q[2];
cx q[0], q[1];
cu1(pi/4) q[0], q[2];
swap q[1], q[2];
ccx q[0], q[1], q[2];
measure q -> c;
"""

        result = run(source, "spinq", 64)

        self.assertEqual(result["shots"], 64)
        self.assertEqual(sum(result["counts"].values()), 64)

    def test_spinq_run_x_gate_flips_zero_to_one(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
x q[0];
measure q -> c;
"""

        result = run(source, "spinq", 32)

        self.assertEqual(result["counts"], {"1": 32})

    def test_spinq_run_swap_exchanges_bits(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[0];
swap q[0], q[1];
measure q -> c;
"""

        result = run(source, "spinq", 32)

        self.assertEqual(result["counts"], {"10": 32})

    def test_spinq_run_ccx_flips_target_when_both_controls_are_one(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
x q[0];
x q[1];
ccx q[0], q[1], q[2];
measure q -> c;
"""

        result = run(source, "spinq", 32)

        self.assertEqual(result["counts"], {"111": 32})

    def test_all_backends_agree_on_deterministic_gate_combo(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[4];
creg c[4];
x q[0];
x q[2];
swap q[0], q[3];
cx q[2], q[1];
ccx q[1], q[2], q[0];
measure q -> c;
"""

        for target in ("spinq", "originq", "braket"):
            with self.subTest(target=target):
                result = run(source, target, 64)
                self.assertEqual(result["counts"], {"1111": 64})

    def test_all_backends_handle_phase_heavy_circuit(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
h q[1];
s q[0];
sdg q[0];
t q[1];
tdg q[1];
rz(pi/3) q[0];
cu1(pi/5) q[0], q[1];
ry(pi/2) q[2];
cx q[0], q[2];
measure q -> c;
"""

        for target in ("spinq", "originq", "braket"):
            with self.subTest(target=target):
                result = run(source, target, 128)
                self.assertEqual(result["shots"], 128)
                self.assertEqual(sum(result["counts"].values()), 128)
                self.assertTrue(set(result["counts"]).issubset({"000", "001", "010", "011", "100", "101", "110", "111"}))

    def test_all_backends_emit_native_ir_for_full_gate_set(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
x q[1];
s q[1];
sdg q[1];
t q[1];
tdg q[1];
rz(pi/2) q[0];
ry(0.25) q[2];
cx q[0], q[1];
cu1(pi/4) q[0], q[2];
swap q[1], q[2];
ccx q[0], q[1], q[2];
measure q -> c;
"""

        self.assertIn("OPENQASM 2.0;", transpile(source, "spinq"))
        self.assertIn("QINIT 3", transpile(source, "originq"))
        self.assertIn("OPENQASM 3.0;", transpile(source, "braket"))


if __name__ == "__main__":
    unittest.main()
