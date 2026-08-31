import os
import socket
import threading
import time
import unittest
from unittest.mock import patch

from starter_kit.llm_client import _configuration, chat_completion


class TransportTimeoutTests(unittest.TestCase):
    def _base_environment(self, timeout):
        return {
            "LOOMQ_LLM_BASE_URL": "http://127.0.0.1:1",
            "LOOMQ_LLM_API_KEY": "local-test",
            "LOOMQ_LLM_MODEL": "test",
            "LOOMQ_LLM_TIMEOUT_SECONDS": timeout,
        }

    def test_official_120_second_case_budget_is_capped_per_attempt(self):
        with patch.dict(os.environ, self._base_environment("120"), clear=True):
            self.assertEqual(_configuration()[3], 55.0)

    def test_smaller_configured_timeout_is_preserved(self):
        with patch.dict(os.environ, self._base_environment("12.5"), clear=True):
            self.assertEqual(_configuration()[3], 12.5)

    def test_nonfinite_timeout_is_rejected_before_network(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value), patch.dict(
                os.environ, self._base_environment(value), clear=True
            ), patch("urllib.request.urlopen") as urlopen:
                with self.assertRaisesRegex(RuntimeError, "finite"):
                    chat_completion([{"role": "user", "content": "x"}])
                urlopen.assert_not_called()

    def test_accepted_connection_without_response_respects_timeout(self):
        server = socket.socket(); server.bind(("127.0.0.1", 0)); server.listen()
        port = server.getsockname()[1]
        def stall():
            connection, _ = server.accept(); time.sleep(5); connection.close(); server.close()
        threading.Thread(target=stall, daemon=True).start()
        env = {"LOOMQ_LLM_BASE_URL": f"http://127.0.0.1:{port}", "LOOMQ_LLM_API_KEY": "local-test", "LOOMQ_LLM_MODEL": "test", "LOOMQ_LLM_TIMEOUT_SECONDS": "1"}
        with patch.dict(os.environ, env, clear=False):
            start = time.monotonic()
            with self.assertRaises(TimeoutError): chat_completion([{"role":"user","content":"x"}])
        self.assertLess(time.monotonic() - start, 4)
