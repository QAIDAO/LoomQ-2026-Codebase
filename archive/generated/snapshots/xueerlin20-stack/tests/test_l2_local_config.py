import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from starter_kit import run_l2


class L2LocalConfigurationTests(unittest.TestCase):
    def write_environment(self, directory, api_key="test-secret-key"):
        path = Path(directory) / ".env.l2"
        path.write_text(
            "\n".join(
                [
                    "# test configuration",
                    "LOOMQ_LLM_BASE_URL=https://api.deepseek.com",
                    "LOOMQ_LLM_API_KEY=%s" % api_key,
                    "LOOMQ_LLM_MODEL=deepseek-v4-flash",
                    "LOOMQ_LLM_TIMEOUT_SECONDS=120",
                    "LOOMQ_LLM_MAX_OUTPUT_TOKENS=4096",
                ]
            ),
            encoding="utf-8",
        )
        return path

    def test_loader_sets_expected_deepseek_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_environment(directory)
            with mock.patch.dict(os.environ, {}, clear=True):
                configuration = run_l2.load_environment(path)

        self.assertEqual(configuration["LOOMQ_LLM_MODEL"], "deepseek-v4-flash")
        self.assertEqual(
            configuration["LOOMQ_LLM_BASE_URL"], "https://api.deepseek.com"
        )

    def test_existing_process_environment_takes_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_environment(directory, api_key="file-key")
            existing = {"LOOMQ_LLM_API_KEY": "process-key"}
            with mock.patch.dict(os.environ, existing, clear=True):
                configuration = run_l2.load_environment(path)

        self.assertEqual(configuration["LOOMQ_LLM_API_KEY"], "process-key")

    def test_placeholder_key_is_rejected_before_model_call(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_environment(directory, api_key="placeholder")
            with mock.patch.dict(os.environ, {}, clear=True):
                configuration = run_l2.load_environment(path)
                with self.assertRaisesRegex(RuntimeError, "placeholder"):
                    run_l2.validate_ready(configuration)

    def test_configuration_summary_never_prints_key(self):
        configuration = {
            "LOOMQ_LLM_BASE_URL": "https://api.deepseek.com",
            "LOOMQ_LLM_API_KEY": "do-not-print-this-key",
            "LOOMQ_LLM_MODEL": "deepseek-v4-flash",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "120",
            "LOOMQ_LLM_MAX_OUTPUT_TOKENS": "4096",
        }

        summary = run_l2.configuration_summary(configuration)

        self.assertNotIn("do-not-print-this-key", summary)
        self.assertIn("deepseek-v4-flash", summary)

    def test_check_mode_does_not_call_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_environment(directory)
            output = StringIO()
            with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
                run_l2, "agent_chat"
            ) as mocked_agent, redirect_stdout(output):
                status = run_l2.main(["--env-file", str(path), "--check"])

        self.assertEqual(status, 0)
        mocked_agent.assert_not_called()
        self.assertIn("配置已加载", output.getvalue())

    def test_bundled_environment_preserves_the_original_entrypoint(self):
        with mock.patch.object(run_l2.importlib.util, "find_spec", return_value=None), \
             mock.patch.object(run_l2.Path, "is_file", return_value=True), \
             mock.patch.object(run_l2.os, "execv") as execv, \
             mock.patch.object(run_l2.sys, "argv", ["starter_kit/web_app.py", "--no-browser"]), \
             mock.patch.object(run_l2.sys, "executable", "/usr/bin/python3"):
            run_l2.reexec_with_bundled_venv_if_needed()

        arguments = execv.call_args.args[1]
        self.assertTrue(arguments[1].endswith("starter_kit/web_app.py"))
        self.assertEqual(arguments[-1], "--no-browser")

    def test_unknown_environment_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.l2"
            path.write_text("UNRELATED_SECRET=value\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "不支持的字段"):
                run_l2.read_env_file(path)


if __name__ == "__main__":
    unittest.main()
