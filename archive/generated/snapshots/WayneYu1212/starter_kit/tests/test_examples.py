from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = {
    "spinq": ROOT / "starter_kit" / "examples" / "run_spinq.py",
    "originq": ROOT / "starter_kit" / "examples" / "run_originq.py",
    "braket": ROOT / "starter_kit" / "examples" / "run_braket.py",
}


class RunnableExampleTests(unittest.TestCase):
    def test_examples_use_real_adapter_and_return_valid_schema(self):
        for target, script in EXAMPLES.items():
            with self.subTest(target=target):
                completed = subprocess.run(
                    [sys.executable, str(script)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn('"bit_order": "little"', completed.stdout)
                self.assertIn('"backend":', completed.stdout)
                self.assertNotIn("mock", completed.stdout.lower())

    def test_missing_sdks_never_fall_back_to_mock_counts(self):
        for target in ("spinq", "originq"):
            with self.subTest(target=target):
                completed = subprocess.run(
                    [sys.executable, "-S", str(EXAMPLES[target])],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertNotIn("mock-job", completed.stdout.lower())
                self.assertNotIn('"counts"', completed.stdout)


if __name__ == "__main__":
    unittest.main()
