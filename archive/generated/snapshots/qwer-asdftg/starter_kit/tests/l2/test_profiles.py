import importlib.util
import os
import unittest
from unittest import mock


class ProviderProfileTests(unittest.TestCase):
    def test_provider_profile_module_is_available(self):
        self.assertIsNotNone(importlib.util.find_spec("starter_kit.l2_profiles"))

    def test_bailian_profile_uses_compatible_endpoint_and_dashscope_key(self):
        from starter_kit.l2_profiles import local_settings

        with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "dashscope-secret"}, clear=True):
            settings = local_settings("bailian-token-plan")

        self.assertEqual(
            settings["LOOMQ_LLM_BASE_URL"],
            "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        )
        self.assertEqual(settings["LOOMQ_LLM_MODEL"], "qwen3.8-max")
        self.assertEqual(settings["LOOMQ_LLM_API_KEY"], "dashscope-secret")

    def test_explicit_model_and_endpoint_override_profile_defaults(self):
        from starter_kit.l2_profiles import local_settings

        with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "dashscope-secret"}, clear=True):
            settings = local_settings(
                "dashscope",
                model="qwen-custom",
                base_url="https://gateway.example/v1",
            )

        self.assertEqual(settings["LOOMQ_LLM_MODEL"], "qwen-custom")
        self.assertEqual(settings["LOOMQ_LLM_BASE_URL"], "https://gateway.example/v1")

    def test_temporary_environment_restores_existing_value(self):
        from starter_kit.l2_profiles import temporary_environment

        with mock.patch.dict(os.environ, {"LOOMQ_LLM_MODEL": "formal-model"}, clear=True):
            with temporary_environment({"LOOMQ_LLM_MODEL": "local-model"}):
                self.assertEqual(os.environ["LOOMQ_LLM_MODEL"], "local-model")
            self.assertEqual(os.environ["LOOMQ_LLM_MODEL"], "formal-model")

    def test_profile_never_falls_back_to_a_residual_formal_key(self):
        from starter_kit.l2_errors import L2ConfigurationError
        from starter_kit.l2_profiles import local_settings

        with mock.patch.dict(
            os.environ,
            {
                "LOOMQ_LLM_API_KEY": "formal-key",
                "LOOMQ_LLM_MODEL": "formal-model",
                "LOOMQ_LLM_BASE_URL": "https://formal.example/v1",
            },
            clear=True,
        ):
            with self.assertRaises(L2ConfigurationError) as caught:
                local_settings("dashscope")

        self.assertEqual(caught.exception.variable_names, ("DASHSCOPE_API_KEY",))


if __name__ == "__main__":
    unittest.main()
