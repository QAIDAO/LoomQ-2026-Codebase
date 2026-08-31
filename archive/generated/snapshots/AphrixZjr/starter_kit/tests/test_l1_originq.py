import os
import sys
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import l1_originq
import loomq_l1


QASM = "OPENQASM 2.0; qreg q[1]; creg c[1]; measure q -> c;"


class OriginQRunnerTests(unittest.TestCase):
    def test_runner_converts_executes_and_finalizes(self):
        observed = {}

        class Machine:
            def init_qvm(self):
                observed["initialized"] = True

            def run_with_configuration(self, prog, cbits, shots):
                observed.update(prog=prog, cbits=cbits, shots=shots)
                return {"0": shots}

            def finalize(self):
                observed["finalized"] = True

        class SDK:
            CPUQVM = Machine

            @staticmethod
            def convert_originir_str_to_qprog(source, machine):
                observed["source"] = source
                return "prog", ["q0"], ["c0"]

        circuit = loomq_l1.parse_qasm(QASM)
        with mock.patch.object(l1_originq, "_load_sdk", return_value=SDK):
            counts, backend, job_id, meta = l1_originq.run_originq(circuit, 16)
        self.assertEqual({"0": 16}, counts)
        self.assertEqual("originq-cpuqvm", backend)
        self.assertTrue(job_id.startswith("originq-local-"))
        self.assertIn("QINIT 1", observed["source"])
        self.assertEqual(16, observed["shots"])
        self.assertTrue(observed["initialized"])
        self.assertTrue(observed["finalized"])
        self.assertEqual(1, meta["qubits"])

    def test_finalizes_after_execution_failure(self):
        observed = {}

        class Machine:
            def init_qvm(self):
                pass

            def run_with_configuration(self, prog, cbits, shots):
                raise RuntimeError("execute failed")

            def finalize(self):
                observed["finalized"] = True

        class SDK:
            CPUQVM = Machine
            convert_originir_str_to_qprog = staticmethod(
                lambda source, machine: ("prog", [], ["c0"])
            )

        circuit = loomq_l1.parse_qasm(QASM)
        with mock.patch.object(l1_originq, "_load_sdk", return_value=SDK):
            with self.assertRaisesRegex(RuntimeError, "execute failed"):
                l1_originq.run_originq(circuit, 4)
        self.assertTrue(observed["finalized"])


if __name__ == "__main__":
    unittest.main()
