import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

try:
    from starter_kit import adapter
    from starter_kit.loomq_agent import service
except ModuleNotFoundError:
    import adapter
    from loomq_agent import service


VALID_RESPONSE = """这是完整线路：
```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
measure q -> c;
```
"""

WRONG_GHZ_RESPONSE = """```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
h q[1];
h q[2];
measure q -> c;
```"""


class CompatibleHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        json.loads(self.rfile.read(length))
        body = json.dumps(
            {"choices": [{"message": {"content": VALID_RESPONSE}}]},
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class L2AgentTests(unittest.TestCase):
    def test_generation_response_is_validated(self):
        completion = {"choices": [{"message": {"content": VALID_RESPONSE}}]}
        with mock.patch.object(service, "chat_completion", return_value=completion) as call:
            answer = service.respond("生成一个 3 比特 GHZ 态")
        self.assertIn("OPENQASM 2.0", answer)
        system = call.call_args.args[0][0]["content"]
        self.assertIn("originq_local_simulator", system)
        self.assertIn("braket_local_simulator", system)
        self.assertIn("回复的第一个内容必须是", system)
        self.assertIn("禁止使用 u、u1、u2、u3", system)
        self.assertIn("q[N-1]...q[0]", system)
        self.assertIn("后端选择回答不得包含 OpenQASM", system)
        self.assertIn("包括 A[i]=1 的分歧位", system)
        self.assertLess(call.call_args.kwargs["request_timeout_seconds"], 120)

    def test_structured_generation_contains_visualization_artifacts(self):
        completion = {"choices": [{"message": {"content": VALID_RESPONSE}}]}
        with mock.patch.object(service, "chat_completion", return_value=completion):
            response = service.respond_structured("生成一个 3 比特 GHZ 态")
        payload = response.to_dict()
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["task"], "generate")
        self.assertIn("OPENQASM 2.0", payload["artifacts"]["qasm"])
        circuit = payload["artifacts"]["circuit"]
        self.assertEqual(circuit["qubit_count"], 3)
        self.assertEqual(len(circuit["operations"]), 3)
        self.assertEqual(circuit["operations"][1]["qubits"], (0, 1))
        simulation = payload["artifacts"]["simulation"]
        self.assertEqual(simulation["method"], "local_ideal_statevector")
        self.assertEqual(sum(simulation["counts"].values()), 8192)
        json.dumps(payload)

    def test_unified_history_is_forwarded_without_task_selection(self):
        completion = {"choices": [{"message": {"content": VALID_RESPONSE}}]}
        history = [
            {"role": "user", "content": "生成一个 GHZ 态"},
            {"role": "assistant", "content": "上一版是 2 比特"},
        ]
        with mock.patch.object(service, "chat_completion", return_value=completion) as call:
            response = service.respond_structured(
                "改成 3 比特",
                history=history,
            )
        messages = call.call_args.args[0]
        self.assertEqual(response.task, "generate")
        self.assertEqual(messages[-3:], history + [{"role": "user", "content": "改成 3 比特"}])
        self.assertEqual(messages[0]["role"], "system")
        self.assertNotIn("明确选择为线路生成", " ".join(item["content"] for item in messages))

    def test_backend_task_hint_enables_constraint_only_prompt(self):
        completion = {"choices": [{"message": {"content": "ignored"}}]}
        with mock.patch.object(service, "chat_completion", return_value=completion):
            response = service.respond_structured(
                "15 比特、本地、免费、不排队",
                task_hint="select_backend",
            )
        self.assertEqual(response.task, "select_backend")
        self.assertEqual(
            {item["id"] for item in response.artifacts.backend_selection.candidates},
            {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"},
        )

    def test_backend_followup_preserves_prior_constraints(self):
        completion = {"choices": [{"message": {"content": "ignored"}}]}
        history = [
            {"role": "user", "content": "必须使用真实量子硬件"},
            {"role": "assistant", "content": "请继续补充费用约束"},
        ]
        with mock.patch.object(service, "chat_completion", return_value=completion):
            response = service.respond_structured(
                "还必须免费",
                history=history,
            )
        self.assertEqual(
            {item["id"] for item in response.artifacts.backend_selection.candidates},
            {"spinq_cloud_qpu", "originq_wukong"},
        )

    def test_new_generation_request_overrides_backend_history(self):
        completion = {"choices": [{"message": {"content": VALID_RESPONSE}}]}
        history = [
            {"role": "user", "content": "帮我选择一个免费的量子后端"},
            {"role": "assistant", "content": "可以使用本地模拟器"},
        ]
        with mock.patch.object(service, "chat_completion", return_value=completion):
            response = service.respond_structured(
                "现在生成一个 3 比特 GHZ 态",
                history=history,
            )
        self.assertEqual(response.task, "generate")
        self.assertIsNotNone(response.artifacts.qasm)

    def test_structured_retry_reports_corrected_artifact(self):
        wrong = {"choices": [{"message": {"content": WRONG_GHZ_RESPONSE}}]}
        corrected = {"choices": [{"message": {"content": VALID_RESPONSE}}]}
        with mock.patch.object(
            service, "chat_completion", side_effect=[wrong, corrected]
        ):
            response = service.respond_structured("生成一个 3 比特 GHZ 态")
        self.assertEqual(response.diagnostics[0].code, "local_validation_retried")
        self.assertIn("cx q[0],q[1]", response.artifacts.qasm)
        self.assertEqual(response.artifacts.circuit.qubit_count, 3)

    def test_structured_repair_is_classified_and_validated(self):
        completion = {"choices": [{"message": {"content": VALID_RESPONSE}}]}
        with mock.patch.object(service, "chat_completion", return_value=completion):
            response = service.respond_structured("修复这段 OPENQASM 代码并生成 3 比特 GHZ")
        self.assertEqual(response.task, "repair")
        self.assertEqual(response.diagnostics[0].code, "local_validation_passed")

    def test_structured_backend_selection_exposes_official_candidates(self):
        completion = {"choices": [{"message": {"content": "ignored"}}]}
        with mock.patch.object(service, "chat_completion", return_value=completion):
            response = service.respond_structured("5 比特真实量子硬件，不能付费")
        payload = response.to_dict()
        self.assertEqual(payload["task"], "select_backend")
        candidates = payload["artifacts"]["backend_selection"]["candidates"]
        self.assertEqual(
            {candidate["id"] for candidate in candidates},
            {"spinq_cloud_qpu", "originq_wukong"},
        )
        self.assertIsNone(payload["artifacts"]["qasm"])

    def test_structured_explanation_has_no_fabricated_artifacts(self):
        completion = {"choices": [{"message": {"content": "量子叠加是状态的线性组合。"}}]}
        with mock.patch.object(service, "chat_completion", return_value=completion):
            payload = service.respond_structured("解释什么是量子叠加").to_dict()
        self.assertEqual(payload["task"], "explain")
        self.assertIsNone(payload["artifacts"]["qasm"])
        self.assertIsNone(payload["artifacts"]["simulation"])

    def test_semantically_wrong_ghz_is_retried(self):
        wrong = {"choices": [{"message": {"content": WRONG_GHZ_RESPONSE}}]}
        corrected = {"choices": [{"message": {"content": VALID_RESPONSE}}]}
        with mock.patch.object(service, "chat_completion", side_effect=[wrong, corrected]) as call:
            answer = service.respond("生成一个 3 比特 GHZ 态并进行全测量")
        self.assertIn("cx q[0],q[1]", answer)
        self.assertEqual(call.call_count, 2)
        retry_messages = call.call_args.args[0]
        self.assertIn("does not match", retry_messages[-1]["content"])

    def test_second_semantic_failure_is_rejected(self):
        wrong = {"choices": [{"message": {"content": WRONG_GHZ_RESPONSE}}]}
        with mock.patch.object(service, "chat_completion", side_effect=[wrong, wrong]):
            with self.assertRaisesRegex(RuntimeError, "failed local circuit validation"):
                service.respond("生成一个 3 比特 GHZ 态并进行全测量")

    def test_english_qubit_width_is_validated(self):
        with self.assertRaisesRegex(ValueError, "requested 4"):
            service.validate_generated_qasm("Create a 4-qubit GHZ state", VALID_RESPONSE.split("```qasm", 1)[1].split("```", 1)[0])

    def test_single_basis_state_is_validated(self):
        qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
x q[0];
x q[2];
measure q -> c;
"""
        result = service.validate_generated_qasm("制备 |101> 并测量", qasm)
        self.assertGreaterEqual(result.fidelity, 0.97)

    def test_generic_pair_construction_pattern_is_validated(self):
        qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
x q[0];
h q[1];
cx q[1], q[0];
cx q[1], q[2];
measure q -> c;
"""
        result = service.validate_generated_qasm("等概率测得 001 和 110", qasm)
        self.assertGreaterEqual(result.fidelity, 0.97)

    def test_pair_retry_guidance_uses_rightmost_bit_as_q_zero(self):
        guidance = service.qasm_correction_guidance("等概率测得 001 和 110")
        self.assertIn("x q[0];", guidance)
        self.assertIn("h q[2];", guidance)
        self.assertIn("cx q[2], q[1];", guidance)
        self.assertIn("cx q[2], q[0];", guidance)
        self.assertNotIn("x q[1];", guidance)

    def test_empty_prompt_is_rejected_before_api_call(self):
        with mock.patch.object(service, "chat_completion") as call:
            with self.assertRaisesRegex(ValueError, "non-empty"):
                service.respond("  ")
        call.assert_not_called()

    def test_backend_answer_uses_deterministic_capability_filter(self):
        completion = {"choices": [{"message": {"content": "OPENQASM 2.0; 错误回答"}}]}
        with mock.patch.object(service, "chat_completion", return_value=completion) as call:
            with mock.patch.object(service, "validate_generated_qasm") as validation:
                answer = service.respond("5 比特必须使用真实量子硬件，而且不能付费")
        self.assertIn("spinq_cloud_qpu", answer)
        self.assertIn("originq_wukong", answer)
        self.assertNotIn("没有后端满足", answer)
        self.assertEqual(call.call_count, 1)
        validation.assert_not_called()

    def test_adapter_uses_environment_only_compatible_transport(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), CompatibleHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        environment = {
            "LOOMQ_LLM_BASE_URL": f"http://127.0.0.1:{server.server_port}",
            "LOOMQ_LLM_API_KEY": "local-test-value",
            "LOOMQ_LLM_MODEL": "local-test-model",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "2",
        }
        try:
            with mock.patch.dict(os.environ, environment, clear=True):
                answer = adapter.agent_chat("生成 GHZ 态")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertIn("OPENQASM 2.0", answer)
        self.assertNotIn("local-test-value", answer)


if __name__ == "__main__":
    unittest.main()
