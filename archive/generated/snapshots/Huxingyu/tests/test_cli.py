import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from starter_kit import loomq_cli
from starter_kit.loomq_cli import histogram


ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def test_histogram_is_sorted_and_reports_percentages(self):
        output = histogram({"11": 75, "00": 25}, 100, width=10)
        self.assertLess(output.index("|11>"), output.index("|00>"))
        self.assertIn("75.00%", output)
        self.assertIn("25.00%", output)

    def test_offline_bell_first_run_needs_no_environment_or_dependencies(self):
        completed = subprocess.run(
            [sys.executable, "loomq_cli.py", "--demo", "bell", "--shots", "256"],
            cwd=ROOT / "starter_kit",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("LoomQ offline demo: Bell pair", completed.stdout)
        self.assertIn("|00>", completed.stdout)
        self.assertIn("|11>", completed.stdout)
        self.assertIn("What this means:", completed.stdout)

    def test_interactive_onboarding_has_examples_help_and_offline_path(self):
        completed = subprocess.run(
            [sys.executable, "loomq_cli.py", "--shots", "32"],
            cwd=ROOT / "starter_kit",
            input="/help\n/demo bell\n/quit\n",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("你不需要量子物理背景", completed.stdout)
        self.assertIn("/demo bell", completed.stdout)
        self.assertIn("LoomQ offline demo: Bell pair", completed.stdout)
        self.assertIn("|00>", completed.stdout)

    def test_missing_model_configuration_has_actionable_safe_recovery(self):
        environment = os.environ.copy()
        for name in tuple(environment):
            if name.startswith("LOOMQ_LLM_"):
                del environment[name]
        environment["PRIVATE_TEST_VALUE"] = "must-not-leak"
        completed = subprocess.run(
            [sys.executable, "loomq_cli.py", "--prompt", "生成 Bell 态"],
            cwd=ROOT / "starter_kit",
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("LOOMQ_LLM_BASE_URL", completed.stderr)
        self.assertIn("--demo bell", completed.stderr)
        self.assertNotIn("must-not-leak", completed.stderr)

    def test_zero_count_does_not_draw_a_misleading_bar(self):
        output = histogram({"00": 10, "01": 0}, 10, width=4)
        zero_line = next(line for line in output.splitlines() if "|01>" in line)
        self.assertNotIn("#", zero_line)

    def test_interactive_follow_up_reuses_only_the_immediately_previous_turn(self):
        with mock.patch("builtins.input", side_effect=[
            "生成一个 3 比特 GHZ 态",
            "改成 5 比特",
            "/quit",
        ]), mock.patch.object(
            loomq_cli,
            "handle_prompt",
            side_effect=["previous complete GHZ response", "updated response"],
        ) as handle, mock.patch("sys.stdout", new_callable=io.StringIO):
            loomq_cli.interactive("braket", 32)

        first_prompt = handle.call_args_list[0].args[0]
        second_prompt = handle.call_args_list[1].args[0]
        self.assertEqual(first_prompt, "生成一个 3 比特 GHZ 态")
        self.assertLess(second_prompt.index("改成 5 比特"), second_prompt.index("生成一个 3 比特 GHZ 态"))
        self.assertIn("previous complete GHZ response", second_prompt)


if __name__ == "__main__":
    unittest.main()
