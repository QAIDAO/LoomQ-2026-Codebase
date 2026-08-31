import unittest

from starter_kit.adapter import run, transpile
from starter_kit.evaluator import calculate_hellinger_fidelity


BELL = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
'''


class L1AdapterTests(unittest.TestCase):
    def test_all_target_renderers_emit_contract_headers(self):
        expected = {
            "spinq": "OPENQASM 2.0;",
            "originq": "QINIT 2",
            "braket": "OPENQASM 3.0;",
        }
        for target, header in expected.items():
            self.assertIn(header, transpile(BELL, target))

    def test_all_targets_return_normalized_counts(self):
        for target in ("spinq", "originq", "braket"):
            payload = run(BELL, target, 2048)
            self.assertEqual(payload["shots"], 2048)
            self.assertEqual(sum(payload["counts"].values()), 2048)
            self.assertEqual(payload["bit_order"], "little")
            self.assertEqual(set(payload["counts"]).issubset({"00", "11"}), True)

    def test_bell_fidelity_is_above_public_threshold(self):
        payload = run(BELL, "braket", 8192)
        observed = {key: value / payload["shots"] for key, value in payload["counts"].items()}
        self.assertGreaterEqual(
            calculate_hellinger_fidelity(observed, {"00": 0.5, "11": 0.5}),
            0.97,
        )

    def test_parameter_expression_and_mid_measurement(self):
        qasm = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
measure q[0] -> c[0];
x q[0];
'''
        payload = run(qasm, "spinq", 256)
        self.assertEqual(sum(payload["counts"].values()), 256)
        self.assertEqual(set(payload["counts"]), {"0", "1"})

    def test_standard_register_wide_gates_expand_elementwise(self):
        qasm = '''OPENQASM 2.0;
include "qelib1.inc";
qreg left[2];
qreg right[2];
creg first[2];
creg second[2];
x left;
cx left, right;
measure left -> first;
measure right -> second;
'''
        for target in ("spinq", "originq", "braket"):
            payload = run(qasm, target, 128)
            self.assertEqual(payload["counts"], {"1111": 128}, target)
            native = transpile(qasm, target)
            self.assertNotIn("left", native)
            self.assertNotIn("right", native)

    def test_register_wide_gate_size_mismatch_is_rejected(self):
        qasm = '''OPENQASM 2.0;
include "qelib1.inc";
qreg left[2];
qreg right[3];
creg c[3];
cx left, right;
measure right -> c;
'''
        with self.assertRaisesRegex(ValueError, "equal sizes"):
            transpile(qasm, "spinq")

    def test_unknown_target_is_rejected(self):
        with self.assertRaises(ValueError):
            transpile(BELL, "unknown")


if __name__ == "__main__":
    unittest.main()
