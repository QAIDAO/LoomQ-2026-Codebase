import os
import unittest
from unittest import mock

try:
    from starter_kit import run_docker_l2
except ModuleNotFoundError:
    import run_docker_l2


class DockerLauncherTests(unittest.TestCase):
    def test_secret_value_is_not_in_docker_arguments(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("builtins.input", side_effect=["https://example.invalid", "test-model"]):
                with mock.patch.object(run_docker_l2.getpass, "getpass", return_value="test-secret"):
                    environment = run_docker_l2.collect_environment()
        command = run_docker_l2.docker_command("test-image")
        self.assertNotIn("test-secret", command)
        self.assertEqual(environment["LOOMQ_LLM_API_KEY"], "test-secret")
        self.assertEqual(command[-4:], ["python", "evaluator.py", "--level", "l2"])

    def test_quality_command_mounts_report_without_secret(self):
        command = run_docker_l2.docker_command(
            "test-image",
            quality_eval=True,
            quality_versions="v2",
            quality_mode="agent",
            quality_report="final.json",
        )
        self.assertIn("prompt_quality.py", command)
        self.assertIn("v2", command)
        self.assertIn("agent", command)
        self.assertIn("/results/final.json", command)
        self.assertIn(f"{run_docker_l2.RUNTIME_DIRECTORY}:/results", command)
        self.assertNotIn("LOOMQ_LLM_API_KEY=", " ".join(command))


if __name__ == "__main__":
    unittest.main()
