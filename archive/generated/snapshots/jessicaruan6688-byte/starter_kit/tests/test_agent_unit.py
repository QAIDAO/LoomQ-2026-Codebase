#!/usr/bin/env python3
"""Unit tests for L2 helpers (no live LLM required)."""

from __future__ import annotations

import sys
import os
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loomq.agent import (  # noqa: E402
    agent_chat,
    extract_backend_id,
    extract_qasm,
    _verify_qasm,
)

GHZ3 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
measure q -> c;
"""


class ExtractTests(unittest.TestCase):
    def test_extract_qasm_fence(self) -> None:
        text = "here\n```qasm\n" + GHZ3 + "\n```\n"
        qasm = extract_qasm(text)
        self.assertIsNotNone(qasm)
        assert qasm is not None
        self.assertIn("OPENQASM 2.0", qasm)
        self.assertIn("h q[0]", qasm)

    def test_extract_backend_id(self) -> None:
        self.assertEqual(
            extract_backend_id("I recommend braket_local_simulator for zero wait."),
            "braket_local_simulator",
        )

    def test_verify_ghz(self) -> None:
        ok, reason = _verify_qasm(GHZ3, "生成 GHZ 并全测量")
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_verify_requires_measure_when_asked(self) -> None:
        no_measure = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];
"""
        ok, reason = _verify_qasm(no_measure, "生成贝尔态并进行测量")
        self.assertFalse(ok)
        self.assertIn("measure", reason)


class AgentLoopTests(unittest.TestCase):
    def test_retries_then_accepts_valid_qasm(self) -> None:
        bad = "Sorry, here is broken code:\n```\nH q[0]\n```\n"
        good = "Fixed:\n```qasm\n" + GHZ3 + "\n```\n"
        responses = iter([bad, good])

        def fake_chat(messages, **extra):  # noqa: ANN001, ANN003
            content = next(responses)
            return {"choices": [{"message": {"content": content}}]}

        with mock.patch("llm_client.chat_completion", side_effect=fake_chat):
            reply = agent_chat("生成一个 3 比特的最大纠缠态 (GHZ 态)，并进行全测量")
        self.assertIn("OPENQASM 2.0", reply)
        self.assertIn("measure", reply.lower())

    def test_backend_answer_passthrough(self) -> None:
        def fake_chat(messages, **extra):  # noqa: ANN001, ANN003
            return {
                "choices": [
                    {
                        "message": {
                            "content": "选 braket_local_simulator，本地零排队。"
                        }
                    }
                ]
            }

        with mock.patch("llm_client.chat_completion", side_effect=fake_chat):
            reply = agent_chat("我需要运行一个 15 比特电路，且零排队等待，选哪个平台？")
        self.assertEqual(extract_backend_id(reply), "braket_local_simulator")

    def test_backend_retries_when_capacity_too_small(self) -> None:
        responses = iter(
            [
                "用 spinq_cloud_qpu 吧",
                "更合适的是 originq_local_simulator",
            ]
        )

        def fake_chat(messages, **extra):  # noqa: ANN001, ANN003
            return {"choices": [{"message": {"content": next(responses)}}]}

        with mock.patch("llm_client.chat_completion", side_effect=fake_chat):
            reply = agent_chat("我需要运行一个 15 比特电路，且零排队等待，选哪个平台？")
        self.assertEqual(extract_backend_id(reply), "originq_local_simulator")

    def test_exhausted_qasm_retries_return_error_not_illegal(self) -> None:
        bad = "```qasm\nOPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[1];\nu3(0,0,0) q[0];\n```\n"

        def fake_chat(messages, **extra):  # noqa: ANN001, ANN003
            return {"choices": [{"message": {"content": bad}}]}

        with mock.patch.dict(os.environ, {"LOOMQ_LLM_MAX_CALLS": "2"}, clear=False):
            with mock.patch("llm_client.chat_completion", side_effect=fake_chat):
                reply = agent_chat("生成一个 3 比特 GHZ 态并全测量")
        self.assertIn("[LoomQ Agent]", reply)
        self.assertIn("上限", reply)
        # Must not pass through the illegal program as a successful answer.
        self.assertNotIn("```", reply)
        self.assertIsNone(extract_qasm(bad))

    def test_extract_rejects_non_whitelist_gate(self) -> None:
        bad = "```qasm\nOPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[1];\nu3(0,0,0) q[0];\n```\n"
        self.assertIsNone(extract_qasm(bad))


if __name__ == "__main__":
    cases = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(cases)
    raise SystemExit(0 if result.wasSuccessful() else 1)
