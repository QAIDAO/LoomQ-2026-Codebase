import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from starter_kit import agent_engine


GHZ_REPLY = '''Here is the validated circuit:
```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0], q[1];
cx q[1], q[2];
measure q -> c;
```
'''


class SequenceHandler(BaseHTTPRequestHandler):
    replies = []
    requests = []

    def log_message(self, *_args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        type(self).requests.append(json.loads(self.rfile.read(length)))
        content = type(self).replies.pop(0)
        body = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class AgentTests(unittest.TestCase):
    def setUp(self):
        SequenceHandler.replies = []
        SequenceHandler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), SequenceHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.environment = {
            "LOOMQ_LLM_BASE_URL": f"http://127.0.0.1:{self.server.server_port}",
            "LOOMQ_LLM_API_KEY": "test-key",
            "LOOMQ_LLM_MODEL": "test-model",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "3",
        }

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def chat(self, prompt, replies):
        SequenceHandler.replies = list(replies)
        with mock.patch.dict(os.environ, self.environment, clear=True):
            return agent_engine.agent_chat(prompt)

    def test_valid_ghz_response_passes_after_one_real_api_call(self):
        reply = self.chat("生成一个 3 比特 GHZ 态并进行全测量", [GHZ_REPLY])
        self.assertIn("OPENQASM 2.0;", reply)
        self.assertEqual(len(SequenceHandler.requests), 1)
        self.assertIn("braket_local_simulator", SequenceHandler.requests[0]["messages"][0]["content"])

    def test_invalid_semantics_are_returned_to_model_for_one_retry(self):
        wrong = GHZ_REPLY.replace("cx q[1], q[2];", "x q[2];")
        reply = self.chat("生成一个 3 比特 GHZ 态并进行全测量", [wrong, GHZ_REPLY])
        self.assertEqual(reply, GHZ_REPLY.strip())
        self.assertEqual(len(SequenceHandler.requests), 2)
        feedback = SequenceHandler.requests[1]["messages"][-1]["content"]
        self.assertIn("fidelity", feedback)

    def test_backend_answer_is_checked_against_machine_readable_table(self):
        reply = self.chat(
            "我需要运行一个 15 比特电路，要求零排队，推荐哪个后端？",
            ["Use originq_wukong.", "Candidates include braket_local_simulator and originq_local_simulator."],
        )
        self.assertIn("braket_local_simulator", reply)
        self.assertNotIn("originq_local_simulator", reply)
        self.assertEqual(len(SequenceHandler.requests), 2)

    def test_backend_fallback_still_occurs_after_required_model_calls(self):
        reply = self.chat(
            "Need a free local simulator for 25 qubits with no account and no queue",
            ["I am unsure.", "Still unsure."],
        )
        self.assertIn("braket_local_simulator", reply)
        self.assertEqual(len(SequenceHandler.requests), 2)

    def test_incompatible_model_recommendations_do_not_override_no_solution(self):
        reply = self.chat(
            "8 比特真机，但不愿注册账号",
            ["Use spinq_cloud_qpu.", "Use originq_wukong."],
        )
        self.assertIn("没有兼容后端", reply)
        self.assertNotIn("spinq_cloud_qpu", reply)
        self.assertNotIn("originq_wukong", reply)
        self.assertEqual(len(SequenceHandler.requests), 2)

    def test_missing_configuration_fails_without_leaking_other_environment(self):
        with mock.patch.dict(os.environ, {"PRIVATE_VALUE": "never-print-me"}, clear=True):
            with self.assertRaises(RuntimeError) as caught:
                agent_engine.agent_chat("生成 Bell 态")
        self.assertNotIn("never-print-me", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
