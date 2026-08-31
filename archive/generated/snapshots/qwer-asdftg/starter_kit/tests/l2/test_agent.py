import os
import unittest
from unittest import mock

from starter_kit import adapter
from starter_kit.loomq_l1.parser import parse_qasm


GHZ_QASM = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0], q[1];
cx q[1], q[2];
measure q -> c;
'''


BELL_QASM = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
'''


PRODUCT_BELL_QASM = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q -> c;
'''


def completion(content):
    return {"choices": [{"message": {"content": content}}]}


class AgentChatTests(unittest.TestCase):
    def test_valid_qasm_reply_is_returned_after_one_model_call(self):
        with mock.patch(
            "starter_kit.loomq_l2._request", return_value=completion(GHZ_QASM)
        ) as chat:
            reply = adapter.agent_chat("生成三比特 GHZ 并全测量")

        self.assertEqual(reply, GHZ_QASM.strip())
        self.assertEqual(chat.call_count, 1)
        self.assertEqual(parse_qasm(reply).num_qubits, 3)

    def test_invalid_qasm_is_repaired_once(self):
        with mock.patch(
            "starter_kit.loomq_l2._request",
            side_effect=[completion("OPENQASM 2.0; broken"), completion(BELL_QASM)],
        ) as chat:
            reply = adapter.agent_chat("修复一个 Bell 电路的 QASM")

        self.assertEqual(chat.call_count, 2)
        self.assertEqual(parse_qasm(reply).num_qubits, 2)

    def test_canonical_backend_id_is_accepted(self):
        with mock.patch(
            "starter_kit.loomq_l2._request",
            return_value=completion("推荐：originq_wukong，满足 50 比特真机需求。"),
        ) as chat:
            reply = adapter.agent_chat("需要至少 50 比特的真机")

        self.assertIn("originq_wukong", reply)
        self.assertEqual(chat.call_count, 1)

    def test_unknown_backend_is_repaired_to_a_canonical_id(self):
        with mock.patch(
            "starter_kit.loomq_l2._request",
            side_effect=[completion("推荐 quantum_magic_backend"), completion("braket_local_simulator")],
        ) as chat:
            reply = adapter.agent_chat("选一个本地免费模拟器")

        self.assertEqual(reply, "braket_local_simulator")
        self.assertEqual(chat.call_count, 2)

    def test_invalid_completion_never_echoes_api_key(self):
        with mock.patch.dict(os.environ, {"LOOMQ_LLM_API_KEY": "private-test-key"}):
            with mock.patch(
                "starter_kit.loomq_l2._request", return_value={"choices": []}
            ):
                with self.assertRaises(RuntimeError) as caught:
                    adapter.agent_chat("hello")

        self.assertNotIn("private-test-key", str(caught.exception))

    def test_final_invalid_reply_exposes_a_precise_validation_error(self):
        from starter_kit.l2_errors import L2ValidationError

        with mock.patch(
            "starter_kit.loomq_l2._request",
            side_effect=[completion("not a circuit"), completion("still not a circuit")],
        ):
            with self.assertRaises(L2ValidationError) as caught:
                adapter.agent_chat("generate a Bell circuit")

        self.assertEqual(
            caught.exception.reason,
            "model response did not satisfy the requested requirement after one repair attempt",
        )

    def test_semantically_wrong_bell_reply_is_repaired_once_without_candidate_text(self):
        with mock.patch(
            "starter_kit.loomq_l2._request",
            side_effect=[completion(PRODUCT_BELL_QASM), completion(BELL_QASM)],
        ) as request:
            reply = adapter.agent_chat("生成一个 Bell 态并进行全测量")

        self.assertEqual(reply, BELL_QASM.strip())
        self.assertEqual(request.call_count, 2)
        repair_messages = request.call_args_list[1].args[0]
        repair_text = "\n".join(message["content"] for message in repair_messages)
        self.assertIn("生成一个 Bell 态并进行全测量", repair_text)
        self.assertIn("semantic_requirement_not_met", repair_text)
        self.assertNotIn(PRODUCT_BELL_QASM, repair_text)
        self.assertFalse(any(message["role"] == "assistant" for message in repair_messages))

    def test_general_explanation_remains_a_single_call(self):
        with mock.patch(
            "starter_kit.loomq_l2._request",
            return_value=completion("量子叠加表示一个量子态可以是多个基态的线性组合。"),
        ) as request:
            reply = adapter.agent_chat("解释量子叠加是什么")

        self.assertIn("线性组合", reply)
        self.assertEqual(request.call_count, 1)

    def test_generate_prose_explanation_is_not_treated_as_a_structured_task(self):
        prose = "量子叠加像一枚在观察前同时保留多种可能性的硬币。"
        with mock.patch(
            "starter_kit.loomq_l2._request", return_value=completion(prose)
        ) as request:
            reply = adapter.agent_chat("生成一段关于量子叠加的通俗说明")

        self.assertEqual(reply, prose)
        self.assertEqual(request.call_count, 1)

    def test_request_uses_the_current_client_function_after_module_import(self):
        with mock.patch(
            "starter_kit.llm_client.chat_completion", return_value=completion(GHZ_QASM)
        ) as request:
            reply = adapter.agent_chat("生成三比特 GHZ 并全测量")

        self.assertEqual(reply, GHZ_QASM.strip())
        self.assertEqual(request.call_count, 1)

    def test_two_semantically_invalid_replies_fail_safely(self):
        from starter_kit.l2_errors import L2ValidationError

        marker = "UNIQUE_CANDIDATE_MARKER"
        candidate = marker + "\n" + PRODUCT_BELL_QASM
        with mock.patch(
            "starter_kit.loomq_l2._request",
            side_effect=[completion(candidate), completion(candidate)],
        ) as request:
            with self.assertRaises(L2ValidationError) as caught:
                adapter.agent_chat("生成一个 Bell 态并进行全测量")

        self.assertEqual(request.call_count, 2)
        self.assertEqual(
            caught.exception.reason,
            "model response did not satisfy the requested requirement after one repair attempt",
        )
        self.assertNotIn(marker, str(caught.exception))
        repair_text = "\n".join(message["content"] for message in request.call_args_list[1].args[0])
        self.assertNotIn(marker, repair_text)

    def test_prompt_and_remote_exceptions_do_not_expose_secret_or_response_text(self):
        from starter_kit.l2_errors import L2ValidationError

        marker = "UNIQUE_REMOTE_RESPONSE_MARKER"
        with mock.patch.dict(os.environ, {"LOOMQ_LLM_API_KEY": "private-test-key"}):
            with self.assertRaises(TypeError) as prompt_error:
                adapter.agent_chat(None)
            with mock.patch(
                "starter_kit.loomq_l2._request",
                side_effect=RuntimeError(marker + ": private-test-key"),
            ):
                with self.assertRaises(L2ValidationError) as remote_error:
                    adapter.agent_chat("解释量子叠加是什么")

        self.assertNotIn("private-test-key", str(prompt_error.exception))
        self.assertNotIn("private-test-key", str(remote_error.exception))
        self.assertNotIn(marker, str(remote_error.exception))


if __name__ == "__main__":
    unittest.main()
