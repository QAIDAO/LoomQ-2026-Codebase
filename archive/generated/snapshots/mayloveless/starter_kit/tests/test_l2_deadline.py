"""Task 15B tests for the shared per-case L2 deadline."""

import json
import os
import unittest
from unittest import mock

import adapter
import llm_client
from loomq.l2_agent import CASE_DEADLINE_SECONDS
from loomq.semantic_verifier import SemanticVerificationResult


BELL_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];"""
WRONG_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
h q[1];"""


def completion(payload):
    return {
        "choices": [
            {"message": {"content": json.dumps(payload, ensure_ascii=False)}}
        ]
    }


def candidate(qasm=BELL_QASM, task_type="generate_qasm"):
    return completion(
        {"task_type": task_type, "qasm": qasm, "explanation": "candidate"}
    )


def target():
    return completion(
        {
            "verification_mode": "statevector",
            "pure_state_requested": True,
            "qubit_count": 2,
            "amplitudes": [
                {"basis": "00", "real": 2 ** -0.5, "imag": 0.0},
                {"basis": "11", "real": 2 ** -0.5, "imag": 0.0},
            ],
            "explanation": "Bell target",
        }
    )


def backend():
    return completion(
        {
            "task_type": "select_backend",
            "qasm": None,
            "backend_constraints": {
                "min_qubits": None,
                "require_qpu": False,
                "require_no_queue": True,
                "cost_policy": "free_only",
                "allow_account_required": False,
            },
            "explanation": "constraints",
        }
    )


class L2DeadlineTests(unittest.TestCase):
    def test_internal_budget_keeps_five_second_margin(self):
        self.assertEqual(CASE_DEADLINE_SECONDS, 115.0)
        self.assertLess(CASE_DEADLINE_SECONDS, 120.0)

    @mock.patch(
        "loomq.l2_agent.time.monotonic",
        side_effect=[100.0, 105.0, 106.0],
    )
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_backend_one_call_receives_remaining_budget(self, chat, _clock):
        chat.return_value = backend()

        adapter.agent_chat("不用真机，免费、不要账号且零排队")

        chat.assert_called_once()
        self.assertEqual(
            chat.call_args.kwargs["request_timeout_seconds"],
            110.0,
        )

    @mock.patch("loomq.l2_agent.verify_semantics")
    @mock.patch(
        "loomq.l2_agent.time.monotonic",
        side_effect=[100.0, 105.0, 130.0, 131.0],
    )
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_generate_two_calls_share_one_decreasing_budget(
        self, chat, _clock, verifier
    ):
        chat.side_effect = [candidate(), target()]
        verifier.return_value = SemanticVerificationResult(1.0, True, "statevector")

        adapter.agent_chat("制备一个 EPR pair")

        self.assertEqual(chat.call_count, 2)
        self.assertEqual(
            [call.kwargs["request_timeout_seconds"] for call in chat.call_args_list],
            [110.0, 85.0],
        )

    @mock.patch("loomq.l2_agent.verify_semantics")
    @mock.patch(
        "loomq.l2_agent.time.monotonic",
        side_effect=[100.0, 105.0, 130.0, 180.0, 181.0],
    )
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_bounded_repair_three_calls_share_one_deadline(
        self, chat, _clock, verifier
    ):
        chat.side_effect = [
            candidate(WRONG_QASM),
            target(),
            candidate(BELL_QASM, task_type="repair_qasm"),
        ]
        verifier.side_effect = [
            SemanticVerificationResult(0.5, False, "statevector"),
            SemanticVerificationResult(1.0, True, "statevector"),
        ]

        adapter.agent_chat("制备 Bell+ 态")

        self.assertEqual(chat.call_count, 3)
        self.assertEqual(
            [call.kwargs["request_timeout_seconds"] for call in chat.call_args_list],
            [110.0, 85.0, 35.0],
        )

    @mock.patch("loomq.l2_agent.verify_semantics")
    @mock.patch(
        "loomq.l2_agent.time.monotonic",
        side_effect=[100.0, 105.0, 130.0, 216.0],
    )
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_exhausted_budget_stops_before_third_request(
        self, chat, _clock, verifier
    ):
        chat.side_effect = [candidate(WRONG_QASM), target()]
        verifier.return_value = SemanticVerificationResult(
            0.5, False, "statevector"
        )

        with self.assertRaisesRegex(RuntimeError, "deadline exhausted"):
            adapter.agent_chat("制备 Bell+ 态")

        self.assertEqual(chat.call_count, 2)

    @mock.patch("loomq.l2_agent.verify_semantics")
    @mock.patch(
        "loomq.l2_agent.time.monotonic",
        side_effect=[100.0, 101.0, 102.0, 216.0],
    )
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_budget_is_checked_after_local_verification_before_success(
        self, chat, _clock, verifier
    ):
        chat.side_effect = [candidate(), target()]
        verifier.return_value = SemanticVerificationResult(1.0, True, "statevector")

        with self.assertRaisesRegex(RuntimeError, "deadline exhausted"):
            adapter.agent_chat("制备 Bell+ 态")

        self.assertEqual(chat.call_count, 2)

    @mock.patch("loomq.l2_agent.time.monotonic", side_effect=[100.0, 101.0])
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_transport_failure_is_redacted(self, chat, _clock):
        secret = "deadline-secret-api-key"
        chat.side_effect = RuntimeError(
            "Authorization: Bearer %s; raw response body" % secret
        )

        with self.assertRaisesRegex(RuntimeError, "model request failed") as caught:
            adapter.agent_chat("选择后端")

        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn("Authorization", str(caught.exception))
        self.assertNotIn("response body", str(caught.exception))


class LLMClientTimeoutOverrideTests(unittest.TestCase):
    @mock.patch("llm_client.urllib.request.urlopen")
    def test_transport_uses_smaller_override_without_payload_leak(self, urlopen):
        response = mock.MagicMock()
        response.read.return_value = b'{"choices": []}'
        urlopen.return_value.__enter__.return_value = response
        environment = {
            "LOOMQ_LLM_BASE_URL": "https://llm.invalid/v1",
            "LOOMQ_LLM_API_KEY": "test-key",
            "LOOMQ_LLM_MODEL": "test-model",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "80",
        }

        with mock.patch.dict(os.environ, environment, clear=True):
            llm_client.chat_completion(
                [{"role": "user", "content": "hello"}],
                request_timeout_seconds=12.5,
            )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 12.5)
        self.assertNotIn("request_timeout_seconds", payload)

    @mock.patch("llm_client.urllib.request.urlopen")
    def test_configured_timeout_caps_larger_override(self, urlopen):
        response = mock.MagicMock()
        response.read.return_value = b'{"choices": []}'
        urlopen.return_value.__enter__.return_value = response
        environment = {
            "LOOMQ_LLM_BASE_URL": "https://llm.invalid/v1",
            "LOOMQ_LLM_API_KEY": "test-key",
            "LOOMQ_LLM_MODEL": "test-model",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "8",
        }

        with mock.patch.dict(os.environ, environment, clear=True):
            llm_client.chat_completion(
                [{"role": "user", "content": "hello"}],
                request_timeout_seconds=30.0,
            )

        self.assertEqual(urlopen.call_args.kwargs["timeout"], 8.0)

    def test_invalid_override_fails_before_transport(self):
        environment = {
            "LOOMQ_LLM_BASE_URL": "https://llm.invalid/v1",
            "LOOMQ_LLM_API_KEY": "test-key",
            "LOOMQ_LLM_MODEL": "test-model",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(RuntimeError, "override must be positive"):
                llm_client.chat_completion(
                    [{"role": "user", "content": "hello"}],
                    request_timeout_seconds=0,
                )


if __name__ == "__main__":
    unittest.main()
