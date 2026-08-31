"""SpinQ Worker 的 stdin/stdout JSON 协议测试。"""

import io
import json
import unittest
from unittest import mock

from loomq.workers import spinq_worker


QASM = (
    'OPENQASM 2.0; include "qelib1.inc"; '
    "qreg q[1]; creg c[1]; measure q -> c;"
)


class SpinQWorkerTests(unittest.TestCase):
    def test_worker_writes_only_result_json_to_stdout(self) -> None:
        expected = {"backend": "spinq_basic_simulator", "counts": {"0": 1}}
        stdin = io.StringIO(json.dumps({"qasm": QASM, "shots": 1}))
        stdout = io.StringIO()
        stderr = io.StringIO()

        def native_runner(circuit, shots):  # type: ignore[no-untyped-def]
            print("sdk log")
            self.assertEqual(1, shots)
            return expected

        with mock.patch.object(spinq_worker.sys, "stdin", stdin), mock.patch.object(
            spinq_worker.sys, "stdout", stdout
        ), mock.patch.object(
            spinq_worker.sys, "stderr", stderr
        ), mock.patch.object(
            spinq_worker, "run_spinq_native", side_effect=native_runner
        ):
            exit_code = spinq_worker.main()

        self.assertEqual(0, exit_code)
        self.assertEqual(expected, json.loads(stdout.getvalue()))
        self.assertIn("sdk log", stderr.getvalue())

    def test_worker_invalid_request_returns_nonzero(self) -> None:
        stdin = io.StringIO(json.dumps({"qasm": QASM, "shots": True}))
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch.object(spinq_worker.sys, "stdin", stdin), mock.patch.object(
            spinq_worker.sys, "stdout", stdout
        ), mock.patch.object(spinq_worker.sys, "stderr", stderr):
            exit_code = spinq_worker.main()

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("positive integer", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
