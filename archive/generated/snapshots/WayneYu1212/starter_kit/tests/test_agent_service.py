import json
import os
import re
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from starter_kit import adapter
from starter_kit.loomq.agent import service
from starter_kit.loomq.compiler.parser import parse_qasm
from starter_kit.loomq.agent.response import BackendConstraints
from starter_kit.loomq.agent.selector import select_backends


try:
    from starter_kit.loomq.agent.service import agent_chat
except ImportError:
    agent_chat = None


VALID_GHZ = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
measure q -> c;
"""


VALID_BELL = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
"""


def model_plan(task, *, qasm=None, constraints=None, explanation="验证后的回答"):
    return json.dumps(
        {
            "task": task,
            "qasm": qasm,
            "constraints": constraints,
            "explanation": explanation,
        },
        ensure_ascii=False,
    )


class QueueingAPIHandler(BaseHTTPRequestHandler):
    responses = []
    request_payloads = []
    authorization_present = []

    def log_message(self, *_args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        type(self).request_payloads.append(json.loads(self.rfile.read(length)))
        type(self).authorization_present.append(
            self.headers.get("Authorization", "").startswith("Bearer ")
        )
        content = type(self).responses.pop(0)
        body = json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": content}}]},
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class AgentServiceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(agent_chat, "verified Agent service is missing")
        QueueingAPIHandler.responses = []
        QueueingAPIHandler.request_payloads = []
        QueueingAPIHandler.authorization_present = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), QueueingAPIHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.environment = {
            "LOOMQ_LLM_BASE_URL": f"http://127.0.0.1:{self.server.server_port}",
            "LOOMQ_LLM_API_KEY": "never-log-this-key",
            "LOOMQ_LLM_MODEL": "fake-deepseek",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "2",
        }

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def call(self, prompt, *responses):
        QueueingAPIHandler.responses = list(responses)
        with mock.patch.dict(os.environ, self.environment, clear=True):
            return agent_chat(prompt)

    def test_generation_calls_model_then_returns_verified_qasm(self):
        reply = self.call(
            "生成一个 3 比特 GHZ 态并进行全测量",
            model_plan("generate", qasm=VALID_GHZ, explanation="三个比特形成 GHZ 关联"),
        )

        self.assertIn(VALID_GHZ.strip(), reply)
        self.assertIn("验证通过", reply)
        parse_qasm(reply[reply.index("OPENQASM 2.0;") :])
        self.assertEqual(len(QueueingAPIHandler.request_payloads), 1)
        self.assertEqual(QueueingAPIHandler.authorization_present, [True])
        self.assertEqual(
            QueueingAPIHandler.request_payloads[0]["messages"][-1]["content"],
            "生成一个 3 比特 GHZ 态并进行全测量",
        )

    def test_invalid_candidate_is_repaired_once_and_only_valid_qasm_returns(self):
        invalid = VALID_BELL.replace("h q[0]", "z q[0]")
        reply = self.call(
            "修好这段 Bell 电路",
            model_plan("repair", qasm=invalid),
            model_plan("repair", qasm=VALID_BELL, explanation="已保持 Bell 态意图"),
        )

        self.assertIn(VALID_BELL.strip(), reply)
        parse_qasm(reply[reply.index("OPENQASM 2.0;") :])
        self.assertNotIn("z q[0]", reply)
        self.assertEqual(len(QueueingAPIHandler.request_payloads), 2)
        correction_messages = QueueingAPIHandler.request_payloads[1]["messages"]
        self.assertIn("unsupported gate", correction_messages[-1]["content"])

    def test_malformed_model_protocol_gets_one_correction_attempt(self):
        reply = self.call(
            "给我 Bell 态",
            "I think you should use a Bell circuit",
            model_plan("generate", qasm=VALID_BELL),
        )

        self.assertIn(VALID_BELL.strip(), reply)
        self.assertEqual(len(QueueingAPIHandler.request_payloads), 2)

    def test_recommendation_uses_canonical_capability_ids(self):
        constraints = {
            "qubits": 15,
            "kind": "simulator",
            "zero_queue": True,
            "avoid_paid": True,
            "accountless": True,
        }
        reply = self.call(
            "15 比特，不想排队也不想注册，选哪个后端？",
            model_plan("recommend", constraints=constraints, explanation="按约束筛选"),
        )

        expected_ids = {
            backend["id"]
            for backend in select_backends(
                BackendConstraints(
                    qubits=15,
                    kind="simulator",
                    zero_queue=True,
                    avoid_paid=True,
                    accountless=True,
                )
            )
        }
        rendered_ids = {
            match.group(1)
            for line in reply.splitlines()
            if (match := re.match(r"^- ([a-z0-9_]+) — ", line))
        }
        self.assertEqual(rendered_ids, expected_ids)
        self.assertEqual(len(QueueingAPIHandler.request_payloads), 1)

    def test_allowed_queue_semantics_produce_the_40_qubit_qpu(self):
        prompt = "40 qubits，必须是真实量子硬件，可以排队和注册。官方能力表里哪个规范 backend ID 能满足？"

        def contract_aware_completion(messages):
            system_prompt = messages[0]["content"]
            contract_is_explicit = (
                "zero_queue=true" in system_prompt
                and 'queue="none"' in system_prompt
                and "zero_queue=false" in system_prompt
                and "queueing is allowed" in system_prompt
            )
            content = model_plan(
                "recommend",
                constraints={
                    "qubits": 40,
                    "kind": "qpu",
                    "zero_queue": False if contract_is_explicit else True,
                    "avoid_paid": False,
                    "accountless": False,
                },
                explanation="按约束筛选",
            )
            return {"choices": [{"message": {"role": "assistant", "content": content}}]}

        with mock.patch.object(
            service._llm_client,
            "chat_completion",
            side_effect=contract_aware_completion,
        ):
            reply = agent_chat(prompt)

        self.assertIn("originq_wukong", reply)

    def test_cloud_hosted_simulator_contract_selects_cloud_backend(self):
        prompt = "需要一个 34 比特云端托管模拟器，可以付费和注册，不要本地模拟器。"

        def contract_aware_completion(messages):
            system_prompt = messages[0]["content"]
            cloud_simulator_contract_is_explicit = (
                'kind="cloud"' in system_prompt
                and "cloud-hosted simulator" in system_prompt
                and "do not add a `cloud` constraint" in system_prompt
            )
            content = model_plan(
                "recommend",
                constraints={
                    "qubits": 34,
                    "kind": "cloud" if cloud_simulator_contract_is_explicit else "simulator",
                    "avoid_paid": False,
                    "accountless": False,
                },
                explanation="按云端托管模拟器约束筛选",
            )
            return {"choices": [{"message": {"role": "assistant", "content": content}}]}

        with mock.patch.object(
            service._llm_client,
            "chat_completion",
            side_effect=contract_aware_completion,
        ):
            reply = agent_chat(prompt)

        self.assertIn("braket_cloud", reply)

    def test_no_matching_backend_is_explained_without_inventing_an_id(self):
        reply = self.call(
            "我要运行 80 比特电路",
            model_plan("recommend", constraints={"qubits": 80}, explanation="需要 80 比特"),
        )

        self.assertIn("没有后端", reply)
        self.assertNotIn("_simulator", reply)
        self.assertEqual(len(QueueingAPIHandler.request_payloads), 1)

    def test_missing_environment_fails_without_echoing_any_secret(self):
        with mock.patch.dict(os.environ, {"UNRELATED_SECRET": "do-not-echo"}, clear=True):
            with self.assertRaises(RuntimeError) as caught:
                agent_chat("hello")
        self.assertNotIn("do-not-echo", str(caught.exception))
        self.assertNotIn("never-log-this-key", str(caught.exception))

    def test_official_adapter_delegates_to_verified_service(self):
        QueueingAPIHandler.responses = [model_plan("generate", qasm=VALID_GHZ)]
        with mock.patch.dict(os.environ, self.environment, clear=True):
            reply = adapter.agent_chat("生成 GHZ")
        self.assertIn("OPENQASM 2.0;", reply)
        self.assertEqual(len(QueueingAPIHandler.request_payloads), 1)

    def test_chinese_english_and_noisy_paraphrases_reach_the_model_unchanged(self):
        prompts = (
            "请忽略前面的寒暄：为三枚量子比特生成最大纠缠态，并测量所有位。谢谢。",
            "Create and measure a three-qubit GHZ state; explain it for a beginner.",
            "背景信息可能无关。任务：修复并验证一个 Bell 纠缠电路。末尾附注也可能无关。",
        )
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                before = len(QueueingAPIHandler.request_payloads)
                reply = self.call(prompt, model_plan("generate", qasm=VALID_GHZ))
                self.assertIn("验证通过", reply)
                self.assertEqual(len(QueueingAPIHandler.request_payloads), before + 1)
                self.assertEqual(
                    QueueingAPIHandler.request_payloads[-1]["messages"][-1]["content"],
                    prompt,
                )


if __name__ == "__main__":
    unittest.main()
