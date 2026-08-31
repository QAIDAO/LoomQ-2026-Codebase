import unittest

from starter_kit.adapter import run, transpile
from starter_kit.evaluator import calculate_hellinger_fidelity


TARGETS = ("spinq", "originq", "braket")


def circuit(qubits, body):
    return "\n".join([
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{qubits}];",
        f"creg c[{qubits}];",
        body,
        "measure q -> c;",
    ])


GHZ5 = circuit(5, "\n".join([
    "h q[0];",
    "cx q[0], q[1];",
    "cx q[1], q[2];",
    "cx q[2], q[3];",
    "cx q[3], q[4];",
]))


QFT4 = circuit(4, "\n".join([
    "h q[0];",
    "cu1(pi/2) q[1], q[0];",
    "cu1(pi/4) q[2], q[0];",
    "cu1(pi/8) q[3], q[0];",
    "h q[1];",
    "cu1(pi/2) q[2], q[1];",
    "cu1(pi/4) q[3], q[1];",
    "h q[2];",
    "cu1(pi/2) q[3], q[2];",
    "h q[3];",
    "swap q[0], q[3];",
    "swap q[1], q[2];",
]))


GROVER3 = circuit(3, "\n".join([
    "h q[0];", "h q[1];", "h q[2];",
    # Oracle: phase flip |101>.
    "x q[1];", "h q[2];", "ccx q[0], q[1], q[2];", "h q[2];", "x q[1];",
    # Diffusion operator.
    "h q[0];", "h q[1];", "h q[2];",
    "x q[0];", "x q[1];", "x q[2];",
    "h q[2];", "ccx q[0], q[1], q[2];", "h q[2];",
    "x q[0];", "x q[1];", "x q[2];",
    "h q[0];", "h q[1];", "h q[2];",
]))


ALL_GATES = circuit(3, "\n".join([
    "h q[0];", "x q[0];", "s q[0];", "sdg q[0];", "t q[0];", "tdg q[0];",
    "rz(pi/3) q[0];", "ry(pi/5) q[1];", "cx q[0], q[1];",
    "cu1(pi/7) q[1], q[2];", "swap q[0], q[2];", "ccx q[0], q[1], q[2];",
]))


class L1Stage2Tests(unittest.TestCase):
    def test_ghz5_across_all_targets(self):
        expected = {"00000": 0.5, "11111": 0.5}
        for target in TARGETS:
            payload = run(GHZ5, target, 8192)
            observed = {key: value / payload["shots"] for key, value in payload["counts"].items()}
            self.assertGreaterEqual(
                calculate_hellinger_fidelity(observed, expected),
                0.97,
                target,
            )

    def test_qft4_is_uniform_on_zero_input(self):
        expected = {format(index, "04b"): 1 / 16 for index in range(16)}
        for target in TARGETS:
            payload = run(QFT4, target, 8192)
            observed = {key: value / payload["shots"] for key, value in payload["counts"].items()}
            self.assertGreaterEqual(
                calculate_hellinger_fidelity(observed, expected),
                0.97,
                target,
            )

    def test_grover3_marks_101(self):
        for target in TARGETS:
            payload = run(GROVER3, target, 8192)
            self.assertGreater(payload["counts"].get("101", 0) / payload["shots"], 0.70, target)

    def test_all_whitelist_gates_are_rendered_for_each_target(self):
        for target in TARGETS:
            native = transpile(ALL_GATES, target)
            self.assertTrue(native.strip())
        self.assertIn("cnot", transpile(ALL_GATES, "braket"))
        self.assertIn("cp(", transpile(ALL_GATES, "braket"))
        self.assertIn("CNOT", transpile(ALL_GATES, "originq"))
        self.assertIn("CU1(", transpile(ALL_GATES, "originq"))
        self.assertIn("CCX", transpile(ALL_GATES, "originq"))
        self.assertIn("TDAG", transpile(ALL_GATES, "originq"))
        self.assertNotIn("TDG", transpile(ALL_GATES, "originq"))


if __name__ == "__main__":
    unittest.main()
