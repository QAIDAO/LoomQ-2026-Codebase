import json
import os
import unittest
from unittest import mock

from starter_kit import adapter
from starter_kit.l2_agent.gateway import OpenAICompatibleLLMGateway
from starter_kit.qasm_L1.parser import parse_qasm


ENVIRONMENT = {
    "LOOMQ_LLM_BASE_URL": "https://placeholder.invalid/v1",
    "LOOMQ_LLM_API_KEY": "placeholder-key",
    "LOOMQ_LLM_MODEL": "placeholder-model",
    "LOOMQ_LLM_TIMEOUT_SECONDS": "120",
}

BELL_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;"""


def completion(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def fake_l1_run(_qasm, target, shots):
    parse_qasm(_qasm)
    return {
        "backend": target,
        "job_id": "local-mocked-spinq-job",
        "shots": shots,
        "counts": {"00": shots // 2, "11": shots - shots // 2},
        "bit_order": "little",
    }


def intent_payload(**updates):
    payload = {
        "task_type": "generate_qasm",
        "user_goal": "生成并测量贝尔态",
        "response_language": "zh",
        "circuit": {"target_state": "bell", "qubits": 2, "measure_all": True},
        "source_qasm": None,
        "backend_constraints": None,
        "candidate_qasm": BELL_QASM,
        "explanation": "创建两比特纠缠态。",
    }
    payload.update(updates)
    return payload


class GatewayParsingTests(unittest.TestCase):
    def test_gateway_parses_json_fence_and_passes_a_request_timeout(self):
        gateway = OpenAICompatibleLLMGateway()
        response = completion("```json\n%s\n```" % json.dumps(intent_payload()))

        with mock.patch.dict(os.environ, ENVIRONMENT, clear=True), mock.patch(
            "starter_kit.l2_agent.gateway.chat_completion", return_value=response
        ) as mocked_call:
            gateway.begin_request()
            intent = gateway.understand("生成贝尔态")

        self.assertEqual(intent.task_type, "generate_qasm")
        self.assertEqual(intent.candidate_qasm, BELL_QASM)
        messages = mocked_call.call_args.args[0]
        self.assertEqual(messages[-1]["content"], "生成贝尔态")
        self.assertGreater(
            mocked_call.call_args.kwargs["request_timeout_seconds"], 0
        )

    def test_gateway_rejects_invalid_json(self):
        gateway = OpenAICompatibleLLMGateway()
        with mock.patch.dict(os.environ, ENVIRONMENT, clear=True), mock.patch(
            "starter_kit.l2_agent.gateway.chat_completion",
            return_value=completion("not-json"),
        ):
            gateway.begin_request()
            with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
                gateway.understand("生成一个电路")

    def test_gateway_rejects_invalid_response_structure(self):
        gateway = OpenAICompatibleLLMGateway()
        with mock.patch.dict(os.environ, ENVIRONMENT, clear=True), mock.patch(
            "starter_kit.l2_agent.gateway.chat_completion", return_value={}
        ):
            gateway.begin_request()
            with self.assertRaisesRegex(RuntimeError, "response structure"):
                gateway.understand("生成一个电路")


class AdapterGatewayIntegrationTests(unittest.TestCase):
    def test_adapter_generation_flow_uses_gateway_and_real_validator(self):
        model_response = completion(json.dumps(intent_payload(), ensure_ascii=False))

        with mock.patch.dict(os.environ, ENVIRONMENT, clear=True), mock.patch(
            "starter_kit.l2_agent.gateway.chat_completion",
            return_value=model_response,
        ) as mocked_call, mock.patch("starter_kit.adapter.run", side_effect=fake_l1_run):
            reply = adapter.agent_chat("生成一个贝尔态并测量")

        self.assertEqual(mocked_call.call_count, 1)
        self.assertIn("OPENQASM 2.0;", reply)
        self.assertIn("cx q[0],q[1];", reply)
        self.assertIn("运行验证：", reply)
        self.assertNotIn("Run validation:", reply)

    def test_adapter_english_request_produces_fully_english_output(self):
        payload = intent_payload(
            user_goal="Generate and measure a Bell state",
            response_language="en",
            explanation="Creates a two-qubit entangled state.",
        )
        model_response = completion(json.dumps(payload, ensure_ascii=False))

        with mock.patch.dict(os.environ, ENVIRONMENT, clear=True), mock.patch(
            "starter_kit.l2_agent.gateway.chat_completion",
            return_value=model_response,
        ), mock.patch("starter_kit.adapter.run", side_effect=fake_l1_run):
            reply = adapter.agent_chat("Generate and measure a Bell state")

        self.assertIn("Generated and validated successfully", reply)
        self.assertIn("Run validation:", reply)
        self.assertIn("Executed 4096 shots", reply)
        self.assertIn("Explanation: Creates a two-qubit entangled state.", reply)
        self.assertNotIn("已生成", reply)

    def test_adapter_backend_flow_uses_gateway_and_real_selector(self):
        payload = intent_payload(
            task_type="recommend_backend",
            user_goal="运行 26 比特电路，免费且无排队",
            circuit=None,
            backend_constraints={
                "min_qubits": 26,
                "kind": None,
                "queue": "none",
                "cost": "free",
                "requires_account": None,
                "platform": None,
            },
            candidate_qasm=None,
            explanation=None,
        )

        with mock.patch.dict(os.environ, ENVIRONMENT, clear=True), mock.patch(
            "starter_kit.l2_agent.gateway.chat_completion",
            return_value=completion(json.dumps(payload, ensure_ascii=False)),
        ) as mocked_call:
            reply = adapter.agent_chat("26 比特、免费、不能排队")

        self.assertEqual(mocked_call.call_count, 1)
        self.assertIn("originq_local_simulator", reply)

    def test_adapter_english_backend_request_uses_english_templates(self):
        payload = intent_payload(
            task_type="recommend_backend",
            user_goal="Run 26 qubits for free without a queue",
            response_language="en",
            circuit=None,
            backend_constraints={
                "min_qubits": 26,
                "kind": None,
                "queue": "none",
                "cost": "free",
                "requires_account": None,
                "platform": None,
            },
            candidate_qasm=None,
            explanation=None,
        )

        with mock.patch.dict(os.environ, ENVIRONMENT, clear=True), mock.patch(
            "starter_kit.l2_agent.gateway.chat_completion",
            return_value=completion(json.dumps(payload)),
        ):
            reply = adapter.agent_chat("Run 26 qubits for free without a queue")

        self.assertIn("Recommended backend: originq_local_simulator", reply)
        self.assertIn("Reason:", reply)
        self.assertNotIn("推荐后端", reply)

    def test_adapter_invalid_candidate_triggers_one_repair_call(self):
        first = intent_payload(
            task_type="repair_qasm",
            user_goal="保持贝尔态目标并修复代码",
            source_qasm="H q[0]; CX q[0] q[1]",
            candidate_qasm="BROKEN",
        )
        responses = [
            completion(json.dumps(first, ensure_ascii=False)),
            completion(json.dumps({"qasm": BELL_QASM}, ensure_ascii=False)),
        ]

        with mock.patch.dict(os.environ, ENVIRONMENT, clear=True), mock.patch(
            "starter_kit.l2_agent.gateway.chat_completion",
            side_effect=responses,
        ) as mocked_call, mock.patch("starter_kit.adapter.run", side_effect=fake_l1_run):
            reply = adapter.agent_chat("保持贝尔态目标并修复这段错误代码")

        self.assertEqual(mocked_call.call_count, 2)
        repair_messages = mocked_call.call_args_list[1].args[0]
        repair_input = json.loads(repair_messages[-1]["content"])
        self.assertEqual(repair_input["original_source_qasm"], "H q[0]; CX q[0] q[1]")
        self.assertIn("OpenQASM 2.0", repair_input["validator_error"])
        self.assertIn(BELL_QASM, reply)

    def test_adapter_missing_environment_fails_without_network_access(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "LOOMQ_LLM_BASE_URL"):
                adapter.agent_chat("生成贝尔态")


if __name__ == "__main__":
    unittest.main()
