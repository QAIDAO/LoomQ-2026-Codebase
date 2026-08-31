import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


STARTER = Path(__file__).resolve().parents[1]
CHILD_MARKER = "LOOMQ_ARCHIVE_ISOLATION_CHILD"


class ArchiveIsolationTests(unittest.TestCase):
    def test_submission_tree_contains_the_scoring_regressions(self):
        expected = {
            "test_l1_core.py",
            "test_l1_spinq.py",
            "test_l1_originq.py",
            "test_l1_braket.py",
            "test_l1_regression.py",
            "test_l2_contract.py",
            "test_l2_agent.py",
            "test_l2_web.py",
            "test_l2_audit_regressions.py",
            "test_l3_and_quantum_riscv.py",
            "test_l3_differential.py",
            "test_quantum_riscv_e2e.py",
        }
        present = {path.name for path in (STARTER / "tests").glob("test_*.py")}
        self.assertEqual(set(), expected - present)

        evidence = (STARTER / "evidence" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("../../tests/", evidence)

    def test_full_suite_runs_after_only_starter_kit_is_copied(self):
        if os.environ.get(CHILD_MARKER) == "1":
            self.skipTest("already running inside the isolated archive copy")

        with tempfile.TemporaryDirectory() as temporary:
            isolated = Path(temporary) / "starter_kit"
            shutil.copytree(
                STARTER,
                isolated,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    "*.env",
                    ".env*",
                    ".hardware-private",
                    ".browser-audit",
                    "report.json",
                ),
            )
            environment = os.environ.copy()
            environment[CHILD_MARKER] = "1"
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["PYTHONIOENCODING"] = "utf-8"
            environment.pop("PYTHONPATH", None)
            secret_prefixes = (
                "AWS_",
                "GH_",
                "GITHUB_",
                "LOOMQ_LLM_",
                "OPENAI_",
                "ORIGINQ_",
                "SPINQ_",
            )
            for name in tuple(environment):
                if name.upper().startswith(secret_prefixes):
                    environment.pop(name, None)

            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-v",
                ],
                cwd=isolated,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                check=False,
            )
            if result.returncode:
                self.fail(
                    "isolated starter_kit suite failed:\n" + result.stdout[-12000:]
                )
            self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
