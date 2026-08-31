"""SpinQ Cloud 证据脚本的离线行为测试。"""

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "submit_spinq_cloud.py"
SPEC = importlib.util.spec_from_file_location("submit_spinq_cloud", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
cloud = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cloud)


class SpinQCloudSubmissionTest(unittest.TestCase):
    def test_remove_measurements_keeps_cloud_program(self):
        source = "OPENQASM 2.0;\nqreg q[2];\ncreg c[2];\nh q[0];\nmeasure q -> c;\n"
        self.assertEqual(
            "OPENQASM 2.0;\nqreg q[2];\ncreg c[2];\nh q[0];\n",
            cloud._remove_measurements(source),
        )

    def test_extract_nested_task_code(self):
        self.assertEqual("task-123", cloud._task_code({"data": {"taskCode": "task-123"}}))

    def test_extract_nested_status(self):
        self.assertEqual("S", cloud._task_status({"data": {"taskStatus": "S"}}))

    def test_parse_probability_result(self):
        result = cloud._parse_result({"data": {"run": {"module": [0.5, 0.0, 0.0, 0.5]}}})
        self.assertEqual({"00": 0.5, "11": 0.5}, {
            key: value for key, value in result["probabilities"].items() if value
        })

    def test_record_submission_writes_required_metadata(self):
        output = Path(self.id().replace(".", "_"))
        output = Path("/private/tmp") / output
        try:
            _input, _submitted, metadata, _raw, _parsed = cloud._record_submission(
                output, "task-123", "source", "program", "gemini", "2026-01-01T00:00:00Z",
                1000, "starter_kit/circuits/bell.qasm",
            )
            import json
            actual = json.loads(metadata.read_text(encoding="utf-8"))
            self.assertEqual(
                {"platform", "backend", "job_id", "submitted_at", "shots", "source_file"},
                set(actual),
            )
            self.assertEqual("task-123", actual["job_id"])
        finally:
            for path in output.glob("*") if output.exists() else ():
                path.unlink()
            if output.exists():
                output.rmdir()


if __name__ == "__main__":
    unittest.main()
