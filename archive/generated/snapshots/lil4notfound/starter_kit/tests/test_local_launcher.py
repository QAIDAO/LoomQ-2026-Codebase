import os
import unittest
from unittest import mock

try:
    from starter_kit import run_local
except ModuleNotFoundError:
    import run_local


class LocalLauncherTests(unittest.TestCase):
    def test_credentials_are_collected_at_runtime(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("builtins.input", side_effect=["https://example.invalid", "test-model"]):
                with mock.patch.object(run_local.getpass, "getpass", return_value="test-key"):
                    added = run_local.configure_environment()
            self.assertEqual(set(added), set(run_local.REQUIRED_ENVIRONMENT))
            self.assertEqual(os.environ["LOOMQ_LLM_API_KEY"], "test-key")

    def test_existing_environment_is_not_replaced(self):
        environment = {
            "LOOMQ_LLM_BASE_URL": "https://example.invalid",
            "LOOMQ_LLM_API_KEY": "existing-key",
            "LOOMQ_LLM_MODEL": "existing-model",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            with mock.patch("builtins.input") as input_prompt:
                with mock.patch.object(run_local.getpass, "getpass") as key_prompt:
                    added = run_local.configure_environment()
        self.assertEqual(added, set())
        input_prompt.assert_not_called()
        key_prompt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
