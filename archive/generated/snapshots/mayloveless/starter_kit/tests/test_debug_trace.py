"""Task 13A tests for additive Agent Trace events."""

import contextlib
import io
import json
import math
import os
import unittest
from unittest import mock

from loomq.debug_trace import TraceRecorder
from loomq.l2_agent import _run_agent, agent_chat
from loomq.semantic_verifier import SemanticVerificationResult


SQRT_HALF = 1.0 / math.sqrt(2.0)
BELL_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];"""


def completion(payload):
    return {
        "choices": [
            {"message": {"content": json.dumps(payload, ensure_ascii=False)}}
        ]
    }


def candidate(qasm=BELL_QASM, task_type="generate_qasm"):
    return completion(
        {"task_type": task_type, "qasm": qasm, "explanation": "test candidate"}
    )


def target():
    return completion(
        {
            "verification_mode": "statevector",
            "pure_state_requested": True,
            "qubit_count": 2,
            "amplitudes": [
                {"basis": "00", "real": SQRT_HALF, "imag": 0.0},
                {"basis": "11", "real": SQRT_HALF, "imag": 0.0},
            ],
            "explanation": "Bell target",
        }
    )


def backend_response():
    return completion(
        {
            "task_type": "select_backend",
            "qasm": None,
            "backend_constraints": {
                "min_qubits": 15,
                "require_qpu": None,
                "require_no_queue": True,
                "cost_policy": "unspecified",
                "allow_account_required": None,
            },
            "explanation": "constraints only",
        }
    )


class AgentTraceTests(unittest.TestCase):
    @mock.patch("loomq.l2_agent.verify_semantics")
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_trace_disabled_preserves_reply_and_has_no_console_output(
        self, chat, verifier
    ):
        verifier.return_value = SemanticVerificationResult(1.0, True, "statevector")
        chat.side_effect = [candidate(), target(), candidate(), target()]
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            production_reply = agent_chat("制备 Bell+ 态")
            traced_reply = _run_agent("制备 Bell+ 态", TraceRecorder())

        self.assertEqual(production_reply, traced_reply)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(chat.call_count, 4)

    @mock.patch("loomq.l2_agent.verify_semantics")
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_normal_qasm_trace_order_and_data(self, chat, verifier):
        verifier.return_value = SemanticVerificationResult(1.0, True, "statevector")
        chat.side_effect = [candidate(), target()]
        recorder = TraceRecorder()

        _run_agent("制备 Bell+ 态", recorder)

        self.assertEqual(chat.call_count, 2)
        self.assertEqual(
            [event.stage for event in recorder.events],
            [
                "intent",
                "qasm_candidate",
                "target_spec",
                "parser_validation",
                "semantic_verification",
                "agent_result",
            ],
        )
        self.assertEqual(
            [event.seq for event in recorder.events], list(range(1, 7))
        )
        self.assertEqual(recorder.events[1].data["qasm"], BELL_QASM)
        self.assertTrue(recorder.events[1].data["pure_state_guard"])
        self.assertEqual(recorder.events[2].data["qubit_count"], 2)
        self.assertEqual(recorder.events[4].data["fidelity"], 1.0)

    @mock.patch("loomq.l2_agent.verify_semantics")
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_repair_trace_stops_at_three_calls(self, chat, verifier):
        verifier.side_effect = [
            SemanticVerificationResult(0.5, False, "statevector"),
            SemanticVerificationResult(1.0, True, "statevector"),
        ]
        chat.side_effect = [
            candidate(),
            target(),
            candidate(task_type="repair_qasm"),
        ]
        recorder = TraceRecorder()

        _run_agent("制备 Bell+ 态", recorder)

        self.assertEqual(chat.call_count, 3)
        stages = [event.stage for event in recorder.events]
        self.assertIn("repair_started", stages)
        self.assertIn("repair_candidate", stages)
        self.assertEqual(stages[-1], "agent_result")
        self.assertTrue(recorder.events[-1].data["repaired"])

    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_backend_trace_selects_locally_with_one_call(self, chat):
        chat.return_value = backend_response()
        recorder = TraceRecorder()

        _run_agent("需要至少 15 比特、零排队的后端", recorder)

        self.assertEqual(chat.call_count, 1)
        self.assertEqual(
            [event.stage for event in recorder.events],
            ["intent", "backend_constraints", "backend_selected", "agent_result"],
        )
        self.assertEqual(
            recorder.events[2].data["backend_ids"],
            [
                "spinq_taurus_simulator",
                "originq_local_simulator",
                "braket_local_simulator",
            ],
        )

    def test_trace_recorder_redacts_credentials_environment_and_paths(self):
        recorder = TraceRecorder()
        secret = "trace-test-api-key"
        with mock.patch.dict(os.environ, {"LOOMQ_LLM_API_KEY": secret}):
            recorder.emit(
                layer="agent",
                stage="safe",
                executor="local",
                status="error",
                summary="Authorization: Bearer %s" % secret,
                data={
                    "secret": secret,
                    "environment": "LOOMQ_LLM_API_KEY",
                    "file": "/Users/test/project/.env.l2.local",
                    "angle": "pi/2",
                    "formula": "(|00>+|11>)/sqrt(2)",
                },
            )
        serialized = json.dumps(recorder.events[0].as_dict())
        self.assertNotIn(secret, serialized)
        self.assertNotIn("Bearer", serialized)
        self.assertNotIn("LOOMQ_LLM", serialized)
        self.assertNotIn("/Users/test", serialized)
        self.assertNotIn(".env.l2.local", serialized)
        self.assertIn("pi/2", serialized)
        self.assertIn("/sqrt(2)", serialized)

    @mock.patch("loomq.circuit_trace.simulate_statevector")
    @mock.patch("loomq.l2_agent.verify_semantics")
    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_production_agent_never_runs_prefix_simulation(
        self, chat, verifier, prefix_simulator
    ):
        verifier.return_value = SemanticVerificationResult(1.0, True, "statevector")
        chat.side_effect = [candidate(), target()]

        agent_chat("制备 Bell+ 态")

        prefix_simulator.assert_not_called()


if __name__ == "__main__":
    unittest.main()
