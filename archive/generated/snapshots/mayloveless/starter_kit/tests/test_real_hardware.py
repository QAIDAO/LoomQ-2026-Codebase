"""SpinQ 真机 Web 服务的离线边界测试。"""

import os
from pathlib import Path
import subprocess
import unittest
from unittest import mock

from loomq import real_hardware


class RealHardwareServiceTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_default_backend_is_online_spinq_hardware(self):
        self.assertEqual("gemini_vp", real_hardware._backend())

    @mock.patch.dict(os.environ, {"SPINQ_BACKEND": "triangulum_vp"})
    def test_vp_backend_code_is_allowed_when_the_cloud_marks_it_non_simulated(self):
        self.assertEqual("triangulum_vp", real_hardware._backend())

    @mock.patch.dict(
        os.environ,
        {
            "SPINQ_USERNAME": "",
            "SPINQCLOUDUSERNAME": "",
            "SPINQ_KEY_PATH": "",
            "PRIVATEKEYPATH": "",
        },
    )
    def test_missing_credentials_are_reported_without_sensitive_details(self):
        self.assertEqual(
            {"spinq": {"available": False, "reason": "真实量子设备未配置"}},
            real_hardware.capability_status(),
        )

    @mock.patch("loomq.real_hardware._run_cloud_worker", return_value={"job_id": "task-123"})
    @mock.patch("loomq.real_hardware._configured", return_value=(True, ""))
    @mock.patch("loomq.real_hardware._backend", return_value="gemini_vp")
    def test_submit_bell_reuses_script_submission(
        self, backend, configured, worker
    ):
        payload = real_hardware.submit_bell()

        self.assertEqual(
            {"job_id": "task-123", "status": "submitted", "platform": "spinq"}, payload
        )
        worker.assert_called_once_with(
            "submit", real_hardware.RUNTIME_OUTPUT,
            "--input", str(real_hardware.submit_spinq_cloud.DEFAULT_INPUT),
            "--backend", "gemini_vp", "--shots", "1000",
        )

    @mock.patch(
        "loomq.real_hardware._run_cloud_worker",
        return_value={"status": "completed", "result": {"counts": {"00": 1}}},
    )
    @mock.patch("loomq.real_hardware._require_configured", return_value="gemini_vp")
    def test_get_job_returns_normalized_status(self, configured, worker):
        self.assertEqual(
            {"job_id": "task-123", "status": "completed", "result": {"counts": {"00": 1}}},
            real_hardware.get_job("task-123"),
        )
        worker.assert_called_once_with("query", real_hardware.RUNTIME_OUTPUT, "--job-id", "task-123")

    @mock.patch("loomq.real_hardware._cloud_python")
    @mock.patch("loomq.real_hardware.subprocess.run")
    def test_worker_uses_final_json_line_after_sdk_output(self, run, cloud_python):
        cloud_python.return_value = Path("/opt/spinq-cloud-venv/bin/python")
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="SpinQ SDK: task accepted\n{\"job_id\": \"task-123\"}\n",
            stderr="",
        )

        result = real_hardware._run_cloud_worker("submit", Path("/tmp/runtime"))

        self.assertEqual({"job_id": "task-123"}, result)


if __name__ == "__main__":
    unittest.main()
