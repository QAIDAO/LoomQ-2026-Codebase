import os
import sys
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import l1_spinq
import loomq_l1


QASM = "OPENQASM 2.0; qreg q[1]; creg c[1]; measure q -> c;"


class SpinQRunnerTests(unittest.TestCase):
    def test_maps_sdk_qubit_order_through_noncontiguous_measurements(self):
        qasm = (
            "OPENQASM 2.0; qreg a[2]; qreg b[3]; creg c[4]; "
            "measure b[2] -> c[0]; measure b[0] -> c[1]; "
            "measure a[0] -> c[3];"
        )
        circuit = loomq_l1.parse_qasm(qasm)
        self.assertEqual(
            {"1011": 7},
            l1_spinq._map_counts_to_classical({"10101": 7}, circuit),
        )

    def test_rejects_sdk_counts_key_with_wrong_qubit_width(self):
        circuit = loomq_l1.parse_qasm(QASM)
        with self.assertRaisesRegex(RuntimeError, "invalid counts key"):
            l1_spinq._map_counts_to_classical({"00": 4}, circuit)

    def test_runner_compiles_executes_and_cleans_temporary_file(self):
        observed = {}

        class Compiler:
            def compile(self, path, optimization):
                observed["path"] = path
                with open(path, encoding="utf-8") as handle:
                    observed["source"] = handle.read()
                observed["optimization"] = optimization
                return "ir"

        class Config:
            def configure_shots(self, shots):
                observed["shots"] = shots

        class Result:
            counts = {"0": 8}

        class Simulator:
            def execute(self, ir, config):
                observed["ir"] = ir
                return Result()

        sdk = (Config, lambda: Simulator(), lambda name: Compiler())
        circuit = loomq_l1.parse_qasm(QASM)
        with mock.patch.object(l1_spinq, "_load_sdk", return_value=sdk):
            counts, backend, job_id, meta = l1_spinq.run_spinq(circuit, 8)
        self.assertEqual({"0": 8}, counts)
        self.assertEqual("spinq-basic-simulator", backend)
        self.assertTrue(job_id.startswith("spinq-local-"))
        self.assertEqual(8, observed["shots"])
        self.assertEqual(0, observed["optimization"])
        self.assertIn("OPENQASM 2.0;", observed["source"])
        self.assertFalse(os.path.exists(observed["path"]))
        self.assertEqual(1, meta["qubits"])

    def test_missing_sdk_is_explicit(self):
        with mock.patch.dict(sys.modules, {"spinqit": None}):
            with self.assertRaisesRegex(RuntimeError, "pinned spinqit"):
                l1_spinq._load_sdk()


if __name__ == "__main__":
    unittest.main()
