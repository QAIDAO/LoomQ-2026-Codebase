from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "starter_kit" / "scripts" / "compute_bell_witness.py"
OUTPUT = ROOT / "starter_kit" / "evidence" / "files" / "bell-witness-analysis.json"
STATS_SCRIPT = ROOT / "starter_kit" / "scripts" / "compute_hardware_statistics.py"
STATS_OUTPUT = ROOT / "starter_kit" / "evidence" / "files" / "hardware-statistics.json"


class BellWitnessEvidenceTests(unittest.TestCase):
    def test_probability_only_runtime_evidence_has_no_statistical_confidence_claim(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        analysis = json.loads(OUTPUT.read_text(encoding="utf-8"))

        self.assertEqual(analysis.get("statistical_inference"), "not_computed")
        self.assertNotIn("lower_bound_95", analysis["two_setting_witness"])
        self.assertNotIn("lower_bound_95", analysis["bell_state_fidelity"])
        self.assertFalse(analysis["two_setting_witness"]["establishes_entanglement"])
        self.assertFalse(analysis["bell_state_fidelity"]["establishes_fidelity_threshold"])

    def test_probability_only_runtime_results_have_no_wilson_intervals(self):
        completed = subprocess.run(
            [sys.executable, str(STATS_SCRIPT)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        analysis = json.loads(STATS_OUTPUT.read_text(encoding="utf-8"))
        runtime_jobs = [job for job in analysis["jobs"] if job["job_id"] != "D0C7F490B43D9B04FDF19ABF3DB8B342"]
        self.assertTrue(runtime_jobs)
        for job in runtime_jobs:
            with self.subTest(job_id=job["job_id"]):
                self.assertEqual(job.get("statistical_inference"), "not_computed")
                self.assertNotIn("target_support", job)


if __name__ == "__main__":
    unittest.main()
