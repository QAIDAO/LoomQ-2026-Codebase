import io
import json
import os
import unittest
from unittest import mock


class L2CliTests(unittest.TestCase):
    def test_local_only_flags_are_mutually_exclusive_usage_error(self):
        from starter_kit import l2_cli

        usage = io.StringIO()
        with mock.patch.object(l2_cli.sys, "stderr", usage):
            with mock.patch("starter_kit.l2_cli.agent_chat") as agent:
                with self.assertRaises(SystemExit) as raised:
                    l2_cli.main(
                        ["--guide", "--explain-counts", '{"00":1}'],
                        stdin=io.StringIO(),
                        stdout=io.StringIO(),
                        stderr=io.StringIO(),
                    )

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("usage:", usage.getvalue())
        agent.assert_not_called()

    def test_local_only_flags_reject_a_positional_prompt_as_usage_error(self):
        from starter_kit import l2_cli

        for arguments in (
            ["--guide", "please ignore me"],
            ["--explain-counts", '{"00":1}', "please ignore me"],
        ):
            with self.subTest(arguments=arguments):
                usage = io.StringIO()
                with mock.patch.object(l2_cli.sys, "stderr", usage):
                    with mock.patch("starter_kit.l2_cli.agent_chat") as agent:
                        with self.assertRaises(SystemExit) as raised:
                            l2_cli.main(arguments, stdin=io.StringIO(), stdout=io.StringIO(), stderr=io.StringIO())

                self.assertEqual(raised.exception.code, 2)
                self.assertIn("usage:", usage.getvalue())
                agent.assert_not_called()

    def test_local_only_flags_reject_nonempty_stdin_as_usage_error(self):
        from starter_kit import l2_cli

        for arguments in (["--guide"], ["--explain-counts", '{"00":1}']):
            with self.subTest(arguments=arguments):
                usage = io.StringIO()
                with mock.patch.object(l2_cli.sys, "stderr", usage):
                    with mock.patch("starter_kit.l2_cli.agent_chat") as agent:
                        with self.assertRaises(SystemExit) as raised:
                            l2_cli.main(arguments, stdin=io.StringIO("please ignore me\n"), stdout=io.StringIO(), stderr=io.StringIO())

                self.assertEqual(raised.exception.code, 2)
                self.assertIn("usage:", usage.getvalue())
                agent.assert_not_called()

    def test_beginner_mode_uses_utf8_for_the_real_console_stream(self):
        from starter_kit import l2_cli

        raw = io.BytesIO()
        terminal = io.TextIOWrapper(raw, encoding="gbk", errors="replace")
        with mock.patch.object(l2_cli.sys, "stdout", terminal):
            code = l2_cli.main(["--guide"])
            terminal.flush()

        self.assertEqual(code, 0)
        self.assertEqual(terminal.encoding.lower(), "utf-8")
        self.assertIn("五分钟", raw.getvalue().decode("utf-8"))

    def test_beginner_mode_explains_the_first_experiment_without_a_key(self):
        from starter_kit import l2_cli

        stdout = io.StringIO()
        with mock.patch("starter_kit.l2_cli.agent_chat") as agent:
            code = l2_cli.main(["--guide"], stdin=io.StringIO(), stdout=stdout, stderr=io.StringIO())

        self.assertEqual(code, 0)
        guide = stdout.getvalue()
        self.assertIn("五分钟", guide)
        self.assertIn("QASM", guide)
        self.assertIn("后端", guide)
        self.assertIn("模拟器", guide)
        self.assertIn("shots", guide)
        self.assertIn("真机", guide)
        agent.assert_not_called()

    def test_result_explanation_maps_bell_counts_to_plain_language(self):
        from starter_kit import l2_cli

        stdout = io.StringIO()
        with mock.patch("starter_kit.l2_cli.agent_chat") as agent:
            code = l2_cli.main(
                ["--explain-counts", '{"00":4102,"11":4090}'],
                stdin=io.StringIO(),
                stdout=stdout,
                stderr=io.StringIO(),
            )

        self.assertEqual(code, 0)
        explanation = stdout.getvalue()
        self.assertIn("00", explanation)
        self.assertIn("11", explanation)
        self.assertIn("#", explanation)
        self.assertIn("关联", explanation)
        self.assertIn("下一步", explanation)
        agent.assert_not_called()

    def test_positional_prompt_prints_agent_response(self):
        from starter_kit import l2_cli

        stdout = io.StringIO()
        with mock.patch("starter_kit.l2_cli.agent_chat", return_value="answer"):
            code = l2_cli.main(["generate bell"], stdin=io.StringIO(), stdout=stdout, stderr=io.StringIO())

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "answer\n")

    def test_stdin_prompt_is_used_when_argument_is_omitted(self):
        from starter_kit import l2_cli

        stdout = io.StringIO()
        with mock.patch("starter_kit.l2_cli.agent_chat", return_value="from stdin") as agent:
            code = l2_cli.main([], stdin=io.StringIO("select a backend\n"), stdout=stdout, stderr=io.StringIO())

        self.assertEqual(code, 0)
        agent.assert_called_once_with("select a backend")

    def test_configuration_error_is_actionable_and_secret_free(self):
        from starter_kit import l2_cli

        stderr = io.StringIO()
        with mock.patch(
            "starter_kit.l2_cli.agent_chat",
            side_effect=RuntimeError("missing LOOMQ_LLM_API_KEY, not private-key"),
        ):
            code = l2_cli.main(["hello"], stdin=io.StringIO(), stdout=io.StringIO(), stderr=stderr)

        self.assertEqual(code, 2)
        self.assertIn("LOOMQ_LLM_API_KEY", stderr.getvalue())
        self.assertNotIn("private-key", stderr.getvalue())

    def test_explicit_provider_uses_only_temporary_local_settings(self):
        from starter_kit import l2_cli

        stdout = io.StringIO()
        observed = {}

        def local_agent(_prompt):
            observed["base_url"] = os.environ["LOOMQ_LLM_BASE_URL"]
            observed["model"] = os.environ["LOOMQ_LLM_MODEL"]
            observed["api_key"] = os.environ["LOOMQ_LLM_API_KEY"]
            return "answer"

        with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "profile-key"}, clear=True):
            with mock.patch("starter_kit.l2_cli.agent_chat", side_effect=local_agent):
                code = l2_cli.main(
                    ["--provider", "dashscope", "--model", "qwen-local", "hello"],
                    stdin=io.StringIO(),
                    stdout=stdout,
                    stderr=io.StringIO(),
                )

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "answer\n")
        self.assertEqual(observed["base_url"], "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.assertEqual(observed["model"], "qwen-local")
        self.assertEqual(observed["api_key"], "profile-key")

    def test_probe_is_dry_run_until_execute_is_supplied(self):
        from starter_kit import l2_cli

        stdout = io.StringIO()
        with mock.patch("starter_kit.l2_cli.agent_chat") as agent:
            code = l2_cli.main(
                [
                    "--provider",
                    "dashscope",
                    "--probe",
                    "--all",
                    "--model",
                    "qwen-a",
                    "--model",
                    "qwen-b",
                    "--json",
                ],
                stdin=io.StringIO(),
                stdout=stdout,
                stderr=io.StringIO(),
            )

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["total_calls"], 6)
        agent.assert_not_called()

    def test_validation_error_reports_the_actionable_reason(self):
        from starter_kit import l2_cli
        from starter_kit.l2_errors import L2ValidationError

        stderr = io.StringIO()
        with mock.patch("starter_kit.l2_cli.agent_chat", side_effect=L2ValidationError("line 7: missing cbit")):
            code = l2_cli.main(["hello"], stdin=io.StringIO(), stdout=io.StringIO(), stderr=stderr)

        self.assertEqual(code, 2)
        self.assertIn("line 7: missing cbit", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
