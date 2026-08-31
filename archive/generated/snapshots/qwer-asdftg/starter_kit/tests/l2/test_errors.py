import io
import os
import unittest
import urllib.error
from unittest import mock


class L2ErrorContractTests(unittest.TestCase):
    def test_client_exposes_actionable_error_types(self):
        from starter_kit import llm_client

        self.assertTrue(hasattr(llm_client, "L2ConfigurationError"))

    def test_missing_configuration_names_the_variable_without_echoing_a_key(self):
        from starter_kit.llm_client import L2ConfigurationError, chat_completion

        with mock.patch.dict(os.environ, {"LOOMQ_LLM_API_KEY": "private-test-key"}, clear=True):
            with self.assertRaises(L2ConfigurationError) as caught:
                chat_completion([])

        self.assertEqual(
            caught.exception.variable_names,
            ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_MODEL"),
        )
        self.assertNotIn("private-test-key", str(caught.exception))

    def test_http_error_exposes_status_and_request_id_without_response_body(self):
        from starter_kit.l2_errors import L2ApiError
        from starter_kit.llm_client import chat_completion

        headers = {"x-request-id": "request-123"}
        error = urllib.error.HTTPError(
            "https://example.test/v1/chat/completions",
            429,
            "Too Many Requests",
            headers,
            io.BytesIO(b"private-response-body"),
        )
        environment = {
            "LOOMQ_LLM_BASE_URL": "https://example.test/v1",
            "LOOMQ_LLM_API_KEY": "private-test-key",
            "LOOMQ_LLM_MODEL": "test-model",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            with mock.patch("starter_kit.llm_client._open_request", side_effect=error):
                with self.assertRaises(L2ApiError) as caught:
                    chat_completion([])

        self.assertEqual(caught.exception.status, 429)
        self.assertEqual(caught.exception.host, "example.test")
        self.assertEqual(caught.exception.request_id, "request-123")
        self.assertNotIn("private-response-body", str(caught.exception))
        self.assertNotIn("private-test-key", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
