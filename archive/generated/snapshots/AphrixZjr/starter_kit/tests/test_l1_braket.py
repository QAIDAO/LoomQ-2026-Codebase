import os
import sys
import unittest
from collections import Counter
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import l1_braket
import loomq_l1


QASM = (
    "OPENQASM 2.0; qreg q[2]; creg c[2]; "
    "x q[0]; measure q[0] -> c[0]; measure q[1] -> c[1];"
)


class BraketRunnerTests(unittest.TestCase):
    def test_runner_executes_program_and_normalizes_bit_order(self):
        observed = {}

        class Program:
            def __init__(self, source):
                observed["source"] = source

        class Result:
            measurement_counts = Counter({"10": 16})
            task_metadata = type("Metadata", (), {"deviceId": "braket_sv"})()

        class Task:
            id = "local-task-id"

            def result(self):
                return Result()

        class LocalSimulator:
            def run(self, program, shots):
                observed.update(program=program, shots=shots)
                return Task()

        circuit = loomq_l1.parse_qasm(QASM)
        with mock.patch.object(
            l1_braket, "_load_sdk", return_value=(LocalSimulator, Program)
        ):
            counts, backend, job_id, meta = l1_braket.run_braket(circuit, 16)

        self.assertEqual({"01": 16}, counts)
        self.assertEqual("braket-local-simulator", backend)
        self.assertEqual("local-task-id", job_id)
        self.assertEqual(16, observed["shots"])
        self.assertIn("OPENQASM 3.0", observed["source"])
        self.assertNotIn("stdgates.inc", observed["source"])
        self.assertEqual("braket_sv", meta["device_id"])

    def test_maps_partial_measurements_to_classical_indices(self):
        circuit = loomq_l1.parse_qasm(
            "OPENQASM 2.0; qreg q[5]; creg c[4]; "
            "measure q[4] -> c[0]; measure q[2] -> c[1]; "
            "measure q[0] -> c[3];"
        )
        self.assertEqual(
            {"1011": 8},
            l1_braket._map_counts_to_classical({"111": 8}, circuit),
        )

    def test_local_source_decomposes_unsupported_standard_gates(self):
        circuit = loomq_l1.parse_qasm(
            "OPENQASM 2.0; qreg q[3]; creg c[3]; sdg q[0]; tdg q[1]; "
            "cu1(pi/3) q[0],q[1]; ccx q[0],q[1],q[2]; measure q -> c;"
        )
        source = l1_braket.emit_braket_executable(circuit)
        for unsupported in ("sdg", "tdg", "cp", "ccx"):
            self.assertNotIn(unsupported, source)
        self.assertIn("cnot", source)
        self.assertIn("rz(", source)

    def test_missing_sdk_is_explicit(self):
        with mock.patch.dict(sys.modules, {"braket.devices": None}):
            with self.assertRaisesRegex(RuntimeError, "pinned amazon-braket-sdk"):
                l1_braket._load_sdk()

    def test_invalid_counts_are_rejected(self):
        class Program:
            def __init__(self, source):
                pass

        class Task:
            id = "task"

            def result(self):
                return type("Result", (), {"measurement_counts": None})()

        class LocalSimulator:
            def run(self, program, shots):
                return Task()

        circuit = loomq_l1.parse_qasm(QASM)
        with mock.patch.object(
            l1_braket, "_load_sdk", return_value=(LocalSimulator, Program)
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid counts"):
                l1_braket.run_braket(circuit, 4)


if __name__ == "__main__":
    unittest.main()
