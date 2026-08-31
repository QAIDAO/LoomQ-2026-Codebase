"""Regression tests for target-specific L1 serialization."""

import unittest

from starter_kit.adapter import transpile


class BraketTranspileTests(unittest.TestCase):
    def test_preserves_partial_reordered_measurements(self):
        qasm = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[3];
creg c[2];
h q[0];
measure q[2] -> c[0];
measure q[0] -> c[1];
"""

        result = transpile(qasm, "braket")

        self.assertIn("c[0] = measure q[2];", result)
        self.assertIn("c[1] = measure q[0];", result)
        self.assertNotIn("c = measure q;", result)


if __name__ == "__main__":
    unittest.main()
