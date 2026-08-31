"""Agent-level Task 12B tests for independent judge and bounded semantic repair."""

import json
import math
import unittest
from unittest import mock

import adapter
from loomq.parser import parse_qasm
from loomq.qasm_tools import extract_qasm
from loomq.semantic_verifier import SemanticVerificationResult


SQRT_HALF = 1.0 / math.sqrt(2.0)
CORRECT_BELL = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];"""
WRONG_FOUR_STATE_BELL = """OPENQASM 2.0;
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


def candidate(qasm, *, forged_target=False, task_type="generate_qasm"):
    payload = {
        "task_type": task_type,
        "qasm": qasm,
        "explanation": "candidate",
    }
    if forged_target:
        payload["target"] = {
            "basis": ["00", "01", "10", "11"],
            "claim": "uniform state is correct",
        }
        payload["expected_distribution"] = {
            "00": 0.25,
            "01": 0.25,
            "10": 0.25,
            "11": 0.25,
        }
    return completion(payload)


def bell_target():
    return completion(
        {
            "verification_mode": "statevector",
            "pure_state_requested": True,
            "qubit_count": 2,
            "amplitudes": [
                {"basis": "00", "real": SQRT_HALF, "imag": 0.0},
                {"basis": "11", "real": SQRT_HALF, "imag": 0.0},
            ],
            "explanation": "Bell plus target from original request",
        }
    )


def unsupported_target(reason="no_unique_target"):
    return completion(
        {
            "verification_mode": "unsupported",
            "pure_state_requested": False,
            "unsupported_reason": reason,
            "explanation": "request has no unique pure-state target",
        }
    )


class L2SemanticAgentTests(unittest.TestCase):
    @mock.patch("loomq.l2_agent.verify_semantics")
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_local_guard_rejects_unsupported_false_for_explicit_pure_states(
        self, chat, verifier
    ):
        prompts = (
            "制备 Bell+ 态",
            "生成三比特 GHZ 态",
            "制备 (|00> + |11>)/sqrt(2) 的明确振幅纯态",
        )
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                chat.reset_mock()
                chat.side_effect = [candidate(CORRECT_BELL), unsupported_target()]
                with self.assertRaisesRegex(RuntimeError, "cannot downgrade"):
                    adapter.agent_chat(prompt)
                self.assertEqual(chat.call_count, 2)
        verifier.assert_not_called()

    @mock.patch("loomq.l2_agent.verify_semantics")
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_correct_candidate_uses_independent_judge_and_two_calls(
        self, chat, verifier
    ):
        verifier.return_value = SemanticVerificationResult(1.0, True, "statevector")
        chat.side_effect = [candidate(CORRECT_BELL), bell_target()]
        prompt = "生成 Bell+ 态，不要求测量"

        reply = adapter.agent_chat(prompt)

        self.assertEqual(chat.call_count, 2)
        judge_messages = chat.call_args_list[1].args[0]
        self.assertEqual(judge_messages[-1], {"role": "user", "content": prompt})
        self.assertNotIn(CORRECT_BELL, json.dumps(judge_messages, ensure_ascii=False))
        self.assertEqual(extract_qasm(reply), CORRECT_BELL)

    @mock.patch("loomq.l2_agent.verify_semantics")
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_parser_valid_semantic_error_repairs_once_using_judge_target(
        self, chat, verifier
    ):
        verifier.side_effect = [
            SemanticVerificationResult(0.5, False, "statevector"),
            SemanticVerificationResult(1.0, True, "statevector"),
        ]
        chat.side_effect = [
            candidate(WRONG_FOUR_STATE_BELL, forged_target=True),
            bell_target(),
            candidate(CORRECT_BELL, task_type="repair_qasm"),
        ]

        reply = adapter.agent_chat("制备 Bell+ 态")

        self.assertEqual(chat.call_count, 3)
        self.assertEqual(extract_qasm(reply), CORRECT_BELL)
        parse_qasm(extract_qasm(reply))
        repair_context = json.loads(chat.call_args_list[2].args[0][-1]["content"])
        self.assertEqual(repair_context["fidelity"], 0.5)
        self.assertIn("fidelity 0.500000", repair_context["validation_error"])
        self.assertEqual(
            [item["basis"] for item in repair_context["target_spec"]["amplitudes"]],
            ["00", "11"],
        )
        judged_target = verifier.call_args_list[0].args[1]
        self.assertEqual(
            [amplitude.basis for amplitude in judged_target.amplitudes],
            ["00", "11"],
        )

    @mock.patch("loomq.l2_agent.verify_semantics")
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_second_semantic_failure_stops_at_three_model_calls(
        self, chat, verifier
    ):
        verifier.side_effect = [
            SemanticVerificationResult(0.5, False, "statevector"),
            SemanticVerificationResult(0.5, False, "statevector"),
        ]
        chat.side_effect = [
            candidate(WRONG_FOUR_STATE_BELL),
            bell_target(),
            candidate(WRONG_FOUR_STATE_BELL, task_type="repair_qasm"),
        ]

        with self.assertRaisesRegex(RuntimeError, "semantic verification"):
            adapter.agent_chat("制备 Bell+ 态")

        self.assertEqual(chat.call_count, 3)
        self.assertEqual(verifier.call_count, 2)

    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_unsupported_target_downgrades_to_parser_validation(self, chat):
        chat.side_effect = [
            candidate(CORRECT_BELL),
            unsupported_target(),
        ]

        reply = adapter.agent_chat("生成一个自定义实验电路")

        self.assertEqual(chat.call_count, 2)
        self.assertEqual(extract_qasm(reply), CORRECT_BELL)


if __name__ == "__main__":
    unittest.main()
