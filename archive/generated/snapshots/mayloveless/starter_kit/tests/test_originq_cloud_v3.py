"""新版 OriginQ Cloud 证据工具的离线测试。"""

from __future__ import annotations

import unittest

from scripts import submit_originq_cloud_v3


class _JobWithMethod:
    def job_id(self) -> str:
        return "WK-C180-task-1"


class OriginQCloudV3Tests(unittest.TestCase):
    def test_job_id_accepts_pyqpanda3_method(self) -> None:
        self.assertEqual("WK-C180-task-1", submit_originq_cloud_v3._job_id(_JobWithMethod()))


if __name__ == "__main__":
    unittest.main()
