from __future__ import annotations

from io import BytesIO, TextIOWrapper
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from starter_kit import prepare_submission


class PrepareSubmissionEncodingTests(unittest.TestCase):
    def test_successful_preflight_writes_to_an_ascii_console(self):
        output_bytes = BytesIO()
        ascii_stdout = TextIOWrapper(output_bytes, encoding="ascii")
        remote = subprocess.CompletedProcess(
            args=["git", "ls-remote"], returncode=0,
            stdout="a" * 40 + "\trefs/heads/final-polish/first-place-runtime\n", stderr="",
        )
        with mock.patch.object(sys, "argv", ["prepare_submission.py", "--team-id", "wayneyu1212"]), \
             mock.patch.object(prepare_submission, "git", side_effect=["", "a" * 40, "https://github.com/WayneYu1212/LoomQ-2026"]), \
             mock.patch.object(prepare_submission.subprocess, "run", return_value=remote), \
             mock.patch.object(sys, "stdout", ascii_stdout):
            try:
                result = prepare_submission.main()
            except UnicodeEncodeError:
                result = 1
        ascii_stdout.flush()
        self.assertEqual(result, 0)
        self.assertIn(b"preflight passed", output_bytes.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
