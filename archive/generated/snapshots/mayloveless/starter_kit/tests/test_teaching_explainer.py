"""Task 13C tests for the optional Web-only Teaching Explainer."""

import json
import unittest
from unittest import mock

from loomq.debug_trace import TraceRecorder
from loomq.l2_agent import agent_chat
from loomq.teaching_explainer import (
    explain_validated_circuit,
    parse_teaching_response,
)


def completion(payload):
    return {
        "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]
    }


def circuit_events():
    recorder = TraceRecorder()
    recorder.emit(
        layer="circuit",
        stage="gate_step",
        executor="local",
        status="ok",
        summary="H",
        data={
            "operation_index": 0,
            "gate": "h",
            "qubits": ["q[0]"],
            "parameters": [],
            "state_before": [
                {"basis": "00", "real": 1.0, "imag": 0.0, "probability": 1.0}
            ],
            "state_after": [
                {"basis": "00", "real": 0.707, "imag": 0.0, "probability": 0.5},
                {"basis": "10", "real": 0.707, "imag": 0.0, "probability": 0.5},
            ],
        },
    )
    recorder.emit(
        layer="circuit",
        stage="gate_step",
        executor="local",
        status="ok",
        summary="CX",
        data={
            "operation_index": 1,
            "gate": "cx",
            "qubits": ["q[0]", "q[1]"],
            "parameters": [],
            "state_before": [],
            "state_after": [],
        },
    )
    return recorder.events


class TeachingExplainerTests(unittest.TestCase):
    def test_parser_ignores_unknown_indices_and_empty_concepts(self):
        explanation = parse_teaching_response(
            completion(
                {
                    "circuit_goal": "制备 Bell 态",
                    "steps": [
                        {
                            "operation_index": 0,
                            "purpose": "为纠缠准备两条路径。",
                            "concept": "叠加",
                            "concept_explanation": "多个基态共同描述当前状态。",
                        },
                        {
                            "operation_index": 99,
                            "purpose": "不存在的门。",
                            "concept": None,
                            "concept_explanation": None,
                        },
                        {
                            "operation_index": 1,
                            "purpose": "关联两个量子位。",
                            "concept": "纠缠",
                            "concept_explanation": None,
                        },
                    ],
                }
            ),
            {0, 1},
        )

        self.assertEqual([step.operation_index for step in explanation.steps], [0, 1])
        self.assertEqual(explanation.steps[0].concept, "叠加")
        self.assertIsNone(explanation.steps[1].concept)

    @mock.patch("loomq.teaching_explainer.llm_client.chat_completion")
    def test_explainer_calls_once_with_minimal_final_circuit_payload(self, chat):
        chat.return_value = completion(
            {
                "circuit_goal": "制备 Bell 态",
                "steps": [
                    {
                        "operation_index": 0,
                        "purpose": "建立两条路径。",
                        "concept": None,
                        "concept_explanation": None,
                    }
                ],
            }
        )

        result = explain_validated_circuit(
            "Bell", "OPENQASM 2.0;\n// final validated", circuit_events()
        )

        self.assertIsNotNone(result)
        self.assertEqual(chat.call_count, 1)
        user_payload = json.loads(chat.call_args.args[0][1]["content"])
        self.assertEqual(
            user_payload["final_validated_qasm"],
            "OPENQASM 2.0;\n// final validated",
        )
        self.assertEqual(
            [step["operation_index"] for step in user_payload["circuit_steps"]],
            [0, 1],
        )
        serialized = json.dumps(user_payload)
        self.assertNotIn("API_KEY", serialized)
        self.assertNotIn("Authorization", serialized)

    @mock.patch("loomq.teaching_explainer.llm_client.chat_completion")
    def test_invalid_or_failed_explainer_safely_returns_none(self, chat):
        chat.return_value = {"choices": []}
        self.assertIsNone(explain_validated_circuit("Bell", "final", circuit_events()))
        self.assertEqual(chat.call_count, 1)

        chat.reset_mock()
        chat.side_effect = RuntimeError("secret at /Users/private")
        self.assertIsNone(explain_validated_circuit("Bell", "final", circuit_events()))
        self.assertEqual(chat.call_count, 1)

    @mock.patch("loomq.teaching_explainer.explain_validated_circuit")
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_production_agent_never_calls_teaching_explainer(self, chat, explain):
        chat.side_effect = RuntimeError("stop before parsing")
        with self.assertRaises(RuntimeError):
            agent_chat("Bell")
        explain.assert_not_called()


if __name__ == "__main__":
    unittest.main()
