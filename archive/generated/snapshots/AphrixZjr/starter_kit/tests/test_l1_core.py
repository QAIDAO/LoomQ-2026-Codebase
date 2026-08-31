import math
import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import loomq_l1


ALL_GATES = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3]; creg c[3];
h q[0]; x q[0]; s q[0]; sdg q[0]; t q[0]; tdg q[0];
rz(pi/2) q[0]; ry(-pi/4) q[1]; cx q[0],q[1];
cu1(2*pi) q[0],q[1]; swap q[1],q[2]; ccx q[0],q[1],q[2];
measure q -> c;
"""


class ParserTests(unittest.TestCase):
    def test_parses_all_gates_and_angles(self):
        circuit = loomq_l1.parse_qasm(ALL_GATES)
        self.assertEqual(12, len(circuit.gates))
        self.assertAlmostEqual(math.pi / 2, circuit.gates[6].params[0])
        self.assertEqual(3, len(circuit.measurements))

    def test_rejects_invalid_inputs_with_context(self):
        cases = [
            ALL_GATES.replace("h q[0]", "z q[0]", 1),
            ALL_GATES.replace("q[2]", "q[9]", 1),
            ALL_GATES.replace("measure q -> c", "measure q[0] -> c"),
            ALL_GATES.replace("pi/2", "__import__('os')"),
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(loomq_l1.QASMError):
                loomq_l1.parse_qasm(source)


class EmitterTests(unittest.TestCase):
    def test_emitters_are_complete_and_deterministic(self):
        for target in loomq_l1.EMITTERS:
            with self.subTest(target=target):
                first = loomq_l1.transpile(ALL_GATES, target)
                self.assertEqual(first, loomq_l1.transpile(ALL_GATES, target))
                self.assertTrue(first.endswith("\n"))
                self.assertIn("MEASURE" if target == "originq" else "measure", first)

    def test_target_specific_headers_and_gate_names(self):
        self.assertIn("OPENQASM 2.0;", loomq_l1.transpile(ALL_GATES, "spinq"))
        originq = loomq_l1.transpile(ALL_GATES, "originq")
        self.assertIn("QINIT 3", originq)
        self.assertIn("RY q[1],(-0.78539816339744828)", originq)
        self.assertIn("CR q[0], q[1],(6.2831853071795862)", originq)
        self.assertNotIn("SDAG", originq)
        self.assertNotIn("TDAG", originq)
        braket = loomq_l1.transpile(ALL_GATES, "braket")
        self.assertIn("OPENQASM 3.0;", braket)
        self.assertIn("cp(", braket)

    def test_invalid_target_and_qasm_propagate(self):
        with self.assertRaises(ValueError):
            loomq_l1.transpile(ALL_GATES, "unknown")
        with self.assertRaises(loomq_l1.QASMError):
            loomq_l1.transpile("not qasm", "spinq")


class ResultTests(unittest.TestCase):
    def test_normalizes_supported_keys(self):
        actual = loomq_l1.normalize_counts({0: 1, "01": 2, "0b10": 3}, 6, 2)
        self.assertEqual({"00": 1, "01": 2, "10": 3}, actual)

    def test_rejects_bad_counts_and_shots(self):
        for raw, shots in [({}, 1), ({"0": -1}, 1), ({"0": 1}, 2), ({-1: 1}, 1)]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                loomq_l1.normalize_counts(raw, shots, 1)
        for shots in (0, -1, True, 1.5):
            with self.subTest(shots=shots), self.assertRaises(ValueError):
                loomq_l1.run(ALL_GATES, "spinq", shots)

    def test_uninstalled_runner_fails_explicitly(self):
        runner = loomq_l1.RUNNERS.pop("spinq", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "not installed"):
                loomq_l1.run(ALL_GATES, "spinq", 4)
        finally:
            if runner is not None:
                loomq_l1.RUNNERS["spinq"] = runner

    def test_run_dispatch_and_schema(self):
        old = dict(loomq_l1.RUNNERS)
        try:
            loomq_l1.RUNNERS["spinq"] = lambda circuit, shots: ({0: shots}, "fake", "job-1", None)
            result = loomq_l1.run(ALL_GATES, "spinq", 4)
            self.assertEqual("little", result["bit_order"])
            self.assertEqual({"000": 4}, result["counts"])
            self.assertTrue(result["timestamp"].endswith("+00:00"))
            self.assertNotIn("meta", result)
        finally:
            loomq_l1.RUNNERS.clear()
            loomq_l1.RUNNERS.update(old)


if __name__ == "__main__":
    unittest.main()
