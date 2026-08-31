import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loomq.facade import run


def circuit(body: str, qubits: int = 1) -> str:
    return """OPENQASM 2.0;
include "qelib1.inc";
qreg q[%d];
creg c[%d];
%s
measure q -> c;
""" % (qubits, qubits, body)


class ReferenceGateSemanticsTests(unittest.TestCase):
    def assert_deterministic(self, source: str, expected: str) -> None:
        for target in ("spinq", "originq", "braket"):
            with self.subTest(target=target):
                self.assertEqual(run(source, target, 64)["counts"], {expected: 64})

    def test_all_single_qubit_gates(self):
        cases = (
            ("h q[0];\nh q[0];", "0"),
            ("x q[0];", "1"),
            ("h q[0];\ns q[0];\ns q[0];\nh q[0];", "1"),
            ("h q[0];\nsdg q[0];\nsdg q[0];\nh q[0];", "1"),
            ("h q[0];\nt q[0];\nt q[0];\nt q[0];\nt q[0];\nh q[0];", "1"),
            ("h q[0];\ntdg q[0];\ntdg q[0];\ntdg q[0];\ntdg q[0];\nh q[0];", "1"),
            ("ry(pi) q[0];", "1"),
            ("h q[0];\nrz(pi) q[0];\nh q[0];", "1"),
        )
        for body, expected in cases:
            with self.subTest(body=body):
                self.assert_deterministic(circuit(body), expected)

    def test_controlled_swap_and_toffoli_gates(self):
        self.assert_deterministic(circuit("x q[0];\ncx q[0], q[1];", 2), "11")
        self.assert_deterministic(
            circuit("x q[1];\nh q[0];\ncu1(pi) q[0], q[1];\nh q[0];", 2),
            "11",
        )
        self.assert_deterministic(circuit("x q[0];\nswap q[0], q[1];", 2), "10")
        self.assert_deterministic(
            circuit("x q[0];\nx q[1];\nccx q[0], q[1], q[2];", 3),
            "111",
        )

    def test_multiple_register_flattening_and_bit_order(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg a[1];
qreg b[2];
creg left[1];
creg right[2];
x a[0];
x b[1];
measure a[0] -> right[0];
measure b[1] -> left[0];
"""
        self.assert_deterministic(source, "011")


if __name__ == "__main__":
    unittest.main()
