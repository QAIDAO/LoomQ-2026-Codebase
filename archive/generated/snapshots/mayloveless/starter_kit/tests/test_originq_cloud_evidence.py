"""OriginQ 真机证据脚本的离线安全测试。"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import submit_originq_cloud


class _FakeCPUQVM:
    def __init__(self) -> None:
        self.initialized = False
        self.finalized = False

    def init_qvm(self) -> None:
        self.initialized = True

    def finalize(self) -> None:
        self.finalized = True


class _FakeSDK:
    CPUQVM = _FakeCPUQVM

    class QCloud:
        def init_qvm(self, _token: str) -> None:
            return None

        def async_batch_real_chip_measure(self, *_args: object) -> str:
            return "not-called"

        def query_batch_task_state_result(self, _task_id: str) -> list[object]:
            return []

        def finalize(self) -> None:
            return None

    class real_chip_type:
        origin_72 = "origin-72"

    @staticmethod
    def convert_originir_to_qprog(path: str, _machine: _FakeCPUQVM):
        source = Path(path).read_text(encoding="utf-8")
        if not source.startswith("QINIT 2\nCREG 2\n"):
            raise AssertionError("unexpected OriginIR")
        return ("qprog", [], [])


class OriginQCloudEvidenceTests(unittest.TestCase):
    def test_dry_run_validates_token_sdk_and_qprog_without_cloud_submit(self) -> None:
        input_path = submit_originq_cloud.DEFAULT_INPUT
        with patch.dict(os.environ, {"ORIGINQ_API_TOKEN": "test-token"}, clear=False):
            with patch.object(submit_originq_cloud, "_load_sdk", return_value=_FakeSDK):
                qprog, originir = submit_originq_cloud.validate_dry_run(input_path)

        self.assertEqual("qprog", qprog)
        self.assertIn("H q[0]", originir)
        self.assertIn("CNOT q[0], q[1]", originir)

    def test_legacy_chip_enum_is_resolved(self) -> None:
        self.assertEqual(
            "origin-72", submit_originq_cloud._resolve_chip(_FakeSDK, "ORIGIN_72")
        )

    def test_evidence_metadata_never_contains_token(self) -> None:
        with tempfile.TemporaryDirectory(dir=submit_originq_cloud.STARTER_KIT_ROOT) as path:
            output = Path(path)
            submit_originq_cloud._write_evidence(
                output_directory=output,
                job_id="task/42",
                qasm="OPENQASM 2.0;\n",
                originir="QINIT 0\nCREG 0\n",
                raw_result=[{"00": 1.0}],
                backend="ORIGIN_72",
                submitted_at="2026-08-21T00:00:00Z",
                shots=1000,
            )
            metadata = (output / "task_42-metadata.json").read_text(encoding="utf-8")
            raw_result = (output / "task_42-raw-result.json").read_text(
                encoding="utf-8"
            )

        self.assertNotIn("test-token", metadata)
        self.assertNotIn("ORIGINQ_API_TOKEN", metadata)
        self.assertEqual('[\n  {\n    "00": 1.0\n  }\n]\n', raw_result)


if __name__ == "__main__":
    unittest.main()
