from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "starter_kit" / "scripts" / "validate_runtime_evidence.py"


class SupplementalRuntimeEvidenceTests(unittest.TestCase):
    def test_runtime_packages_are_probability_only_and_separated(self):
        completed = subprocess.run(
            [sys.executable, str(VALIDATOR)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["package_count"], 5)
        self.assertEqual(result["unique_job_count"], 5)
        self.assertEqual(result["provider_timestamps"], "unavailable")
        self.assertEqual(result["per_shot_counts"], "unavailable")


if __name__ == "__main__":
    unittest.main()
