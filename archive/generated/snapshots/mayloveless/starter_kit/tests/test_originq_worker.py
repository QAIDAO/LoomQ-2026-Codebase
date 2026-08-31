"""OriginQ Worker 的 JSON 协议与 CPUQVM 资源释放测试。"""

import io
import json
import unittest
from unittest import mock

from loomq.workers import originq_worker


ORIGINIR = "QINIT 1\nCREG 1\nMEASURE q[0], c[0]\n"


class OriginQWorkerProtocolTests(unittest.TestCase):
    def test_worker_writes_only_counts_json_to_stdout(self) -> None:
        stdin = io.StringIO(json.dumps({"originir": ORIGINIR, "shots": 2}))
        stdout = io.StringIO()
        stderr = io.StringIO()

        def execute(originir, shots):  # type: ignore[no-untyped-def]
            print("sdk log")
            self.assertEqual(ORIGINIR, originir)
            self.assertEqual(2, shots)
            return {"0": 2}

        with mock.patch.object(originq_worker.sys, "stdin", stdin), mock.patch.object(
            originq_worker.sys, "stdout", stdout
        ), mock.patch.object(
            originq_worker.sys, "stderr", stderr
        ), mock.patch.object(
            originq_worker, "_execute_originir", side_effect=execute
        ):
            exit_code = originq_worker.main()

        self.assertEqual(0, exit_code)
        self.assertEqual({"counts": {"0": 2}}, json.loads(stdout.getvalue()))
        self.assertIn("sdk log", stderr.getvalue())

    def test_invalid_request_returns_nonzero(self) -> None:
        stdin = io.StringIO(json.dumps({"originir": ORIGINIR, "shots": True}))
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(originq_worker.sys, "stdin", stdin), mock.patch.object(
            originq_worker.sys, "stdout", stdout
        ), mock.patch.object(originq_worker.sys, "stderr", stderr):
            exit_code = originq_worker.main()

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("positive integer", stderr.getvalue())

    def test_execute_uses_probed_api_and_finalizes_machine(self) -> None:
        machine = mock.Mock()
        machine.run_with_configuration.return_value = {"0": 3}
        sdk = mock.Mock()
        sdk.CPUQVM.return_value = machine
        sdk.convert_originir_to_qprog.return_value = ["prog", ["q0"], ["c0"]]

        with mock.patch.object(
            originq_worker.importlib, "import_module", return_value=sdk
        ):
            counts = originq_worker._execute_originir(ORIGINIR, 3)

        self.assertEqual({"0": 3}, counts)
        machine.init_qvm.assert_called_once_with()
        sdk.convert_originir_to_qprog.assert_called_once_with(mock.ANY, machine)
        machine.run_with_configuration.assert_called_once_with("prog", ["c0"], 3)
        machine.finalize.assert_called_once_with()

    def test_execute_finalizes_machine_after_conversion_error(self) -> None:
        machine = mock.Mock()
        sdk = mock.Mock()
        sdk.CPUQVM.return_value = machine
        sdk.convert_originir_to_qprog.side_effect = RuntimeError("parse failed")

        with mock.patch.object(
            originq_worker.importlib, "import_module", return_value=sdk
        ):
            with self.assertRaisesRegex(RuntimeError, "parse failed"):
                originq_worker._execute_originir(ORIGINIR, 1)

        machine.finalize.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
