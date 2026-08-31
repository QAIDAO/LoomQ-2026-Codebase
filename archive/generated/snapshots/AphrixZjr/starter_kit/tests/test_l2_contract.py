import importlib.util
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "llm_client.py"
POLICY = ROOT / "l2_policy.json"


def load_client():
    spec = importlib.util.spec_from_file_location("loomq_public_llm_client", CLIENT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CompatibleAPIHandler(BaseHTTPRequestHandler):
    request_payload = None
    response_body = None

    def log_message(self, *_args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        type(self).request_payload = json.loads(self.rfile.read(length))
        body = type(self).response_body or json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ErrorAPIHandler(BaseHTTPRequestHandler):
    requests = 0

    def log_message(self, *_args):
        return

    def do_POST(self):
        type(self).requests += 1
        self.send_response(429)
        self.send_header("Content-Length", "0")
        self.end_headers()


class PublicL2ContractTests(unittest.TestCase):
    def test_policy_is_the_published_formal_deepseek_budget(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(policy["formal_model"], "deepseek-v4-flash")
        self.assertEqual(policy["thinking"], {"type": "disabled"})
        self.assertEqual(
            policy["per_case"],
            {
                "timeout_seconds": 120,
                "max_attempts": 3,
                "max_input_tokens": 8000,
                "max_output_tokens": 2000,
                "default_max_tokens_per_request": 900,
                "max_tokens_per_request": 1000,
            },
        )
        self.assertFalse(policy["organizer_api_available_before_scoring"])

    def test_missing_environment_fails_without_echoing_secrets(self):
        client = load_client()
        with mock.patch.dict(os.environ, {"UNRELATED_SECRET": "do-not-echo"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "LOOMQ_LLM_BASE_URL") as caught:
                client.chat_completion([{"role": "user", "content": "hello"}])
        self.assertNotIn("do-not-echo", str(caught.exception))

    def test_client_works_with_an_openai_compatible_endpoint(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), CompatibleAPIHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            environment = {
                "LOOMQ_LLM_BASE_URL": "http://127.0.0.1:%d" % server.server_port,
                "LOOMQ_LLM_API_KEY": "local-key",
                "LOOMQ_LLM_MODEL": "local-model",
                "LOOMQ_LLM_TIMEOUT_SECONDS": "2",
            }
            with mock.patch.dict(os.environ, environment, clear=True):
                client = load_client()
                response = client.chat_completion([{"role": "user", "content": "hello"}])
                default_payload = dict(CompatibleAPIHandler.request_payload)
                client.chat_completion(
                    [{"role": "user", "content": "hello"}],
                    request_max_tokens=200,
                )
                lowered_payload = dict(CompatibleAPIHandler.request_payload)
                with self.assertRaisesRegex(ValueError, "request_max_tokens"):
                    client.chat_completion(
                        [{"role": "user", "content": "hello"}],
                        request_max_tokens=901,
                    )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(response["choices"][0]["message"]["content"], "ok")
        self.assertEqual(default_payload["model"], "local-model")
        self.assertEqual(default_payload["temperature"], 0)
        self.assertEqual(default_payload["max_tokens"], 900)
        self.assertEqual(lowered_payload["max_tokens"], 200)

    def test_transport_rejects_oversized_response(self):
        client = load_client()
        server = ThreadingHTTPServer(("127.0.0.1", 0), CompatibleAPIHandler)
        CompatibleAPIHandler.response_body = b"x" * (client.MAX_RESPONSE_BYTES + 1)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            environment = {
                "LOOMQ_LLM_BASE_URL": "http://127.0.0.1:%d" % server.server_port,
                "LOOMQ_LLM_API_KEY": "local-key",
                "LOOMQ_LLM_MODEL": "local-model",
                "LOOMQ_LLM_TIMEOUT_SECONDS": "2",
            }
            with mock.patch.dict(os.environ, environment, clear=True):
                with self.assertRaisesRegex(RuntimeError, "size limit"):
                    client.chat_completion([])
        finally:
            CompatibleAPIHandler.response_body = None
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_formal_request_fields_cannot_be_overridden(self):
        client = load_client()
        environment = {
            "LOOMQ_LLM_BASE_URL": "http://127.0.0.1:1",
            "LOOMQ_LLM_API_KEY": "local-key",
            "LOOMQ_LLM_MODEL": "deepseek-v4-flash",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "cannot be overridden"):
                client.chat_completion([], temperature=1)

    def test_deepseek_request_disables_thinking_and_streaming(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), CompatibleAPIHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            environment = {
                "LOOMQ_LLM_BASE_URL": "http://127.0.0.1:%d" % server.server_port,
                "LOOMQ_LLM_API_KEY": "local-key",
                "LOOMQ_LLM_MODEL": "deepseek-v4-flash",
                "LOOMQ_LLM_TIMEOUT_SECONDS": "2",
            }
            with mock.patch.dict(os.environ, environment, clear=True):
                load_client().chat_completion([])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        payload = CompatibleAPIHandler.request_payload
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["temperature"], 0)

    def test_http_error_is_not_implicitly_retried(self):
        client = load_client()
        ErrorAPIHandler.requests = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), ErrorAPIHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            environment = {
                "LOOMQ_LLM_BASE_URL": "http://127.0.0.1:%d" % server.server_port,
                "LOOMQ_LLM_API_KEY": "local-key", "LOOMQ_LLM_MODEL": "local-model",
                "LOOMQ_LLM_TIMEOUT_SECONDS": "2",
            }
            with mock.patch.dict(os.environ, environment, clear=True):
                with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
                    client.chat_completion([])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(ErrorAPIHandler.requests, 1)


if __name__ == "__main__":
    unittest.main()
