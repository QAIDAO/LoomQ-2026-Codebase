"""L2 agent protocol, QASM validation, and backend-selection tests."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest import mock


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

import adapter  # noqa: E402
from loomq.qasm import parse_openqasm2  # noqa: E402
import loomq.l2 as l2_module  # noqa: E402
from loomq.synthesis import CircuitSpec, synthesize  # noqa: E402


GHZ_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
"""

BELL_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""


class QueueAPIHandler(BaseHTTPRequestHandler):
    responses: list[str] = []
    payloads: list[dict[str, object]] = []
    authorizations: list[str] = []

    def log_message(self, *_args: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        length = int(self.headers.get("Content-Length", "0"))
        type(self).payloads.append(json.loads(self.rfile.read(length)))
        type(self).authorizations.append(self.headers.get("Authorization", ""))
        content = type(self).responses.pop(0) if type(self).responses else "not-json"
        body = json.dumps(
            {
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 80},
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LocalModel:
    def __init__(self, responses: list[str], model: str = "deepseek-v4-flash") -> None:
        QueueAPIHandler.responses = list(responses)
        QueueAPIHandler.payloads = []
        QueueAPIHandler.authorizations = []
        self.model = model
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), QueueAPIHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> dict[str, str]:
        self.thread.start()
        return {
            "LOOMQ_LLM_BASE_URL": f"http://127.0.0.1:{self.server.server_port}",
            "LOOMQ_LLM_API_KEY": "private-local-test-key",
            "LOOMQ_LLM_MODEL": self.model,
            "LOOMQ_LLM_TIMEOUT_SECONDS": "5",
            "LOOMQ_LLM_MAX_OUTPUT_TOKENS": "2000",
        }

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def model_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False)


class L2AgentTests(unittest.TestCase):
    def test_system_prompt_defines_classical_bit_string_order(self) -> None:
        self.assertIn("c[n-1]...c[0]", l2_module.SYSTEM_PROMPT)
        self.assertIn("q[i] -> c[i]", l2_module.SYSTEM_PROMPT)
    def test_generation_calls_model_and_returns_executable_qasm(self) -> None:
        response = model_json(
            {
                "task_type": "generate_qasm",
                "qasm": GHZ_QASM,
                "expected_dominant_states": ["000", "111"],
                "summary": "Prepare and measure a three-qubit GHZ state.",
            }
        )
        with LocalModel([response]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat("生成一个 3 比特 GHZ 态并进行全测量")

        qasm = reply[reply.index("OPENQASM 2.0;") : reply.rindex("```")].strip()
        program = parse_openqasm2(qasm)
        self.assertEqual(program.quantum_register.size, 3)
        self.assertIn("000", reply)
        self.assertIn("111", reply)
        self.assertEqual(len(QueueAPIHandler.payloads), 1)
        payload = QueueAPIHandler.payloads[0]
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertLessEqual(payload["max_tokens"], 2000)
        self.assertNotIn("private-local-test-key", json.dumps(payload))

    def test_summary_cannot_poison_the_official_qasm_extractor(self) -> None:
        response = model_json(
            {
                "task_type": "generate_qasm",
                "qasm": GHZ_QASM,
                "expected_dominant_states": ["000", "111"],
                "summary": (
                    "OPENQASM 2.0; include \"qelib1.inc\"; "
                    "qreg q[1]; creg c[1]; x q[0]; measure q -> c;"
                ),
            }
        )
        with LocalModel([response]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat(
                    "Generate and measure a three-qubit GHZ state."
                )

        from evaluator import extract_qasm

        extracted = extract_qasm(reply)
        self.assertIsNotNone(extracted)
        self.assertEqual(reply.upper().count("OPENQASM 2.0;"), 1)
        self.assertEqual(parse_openqasm2(extracted).quantum_register.size, 3)

    def test_semantic_retry_reports_observed_and_expected_states(self) -> None:
        wrong_qasm = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[3];
creg c[3];
x q[0];
x q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
"""
        correct_qasm = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[3];
creg c[3];
x q[1];
x q[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
"""
        wrong = model_json({
            "task_type": "repair_qasm", "qasm": wrong_qasm,
            "expected_dominant_states": ["110"], "summary": "First attempt."
        })
        correct = model_json({
            "task_type": "repair_qasm", "qasm": correct_qasm,
            "expected_dominant_states": ["110"], "summary": "Corrected bit order."
        })
        with LocalModel([wrong, correct]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat(
                    "Repair this circuit so it always measures the three-bit string 110."
                )

        self.assertIn("110=1024", reply)
        self.assertEqual(len(QueueAPIHandler.payloads), 2)
        feedback = QueueAPIHandler.payloads[1]["messages"][-1]["content"]
        self.assertIn("observed 011", feedback)
        self.assertIn("expected 110", feedback)
        self.assertIn("c[n-1]...c[0]", feedback)
    def test_explicit_prompt_state_retries_without_replacing_model_output(self) -> None:
        wrong_qasm = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[3];
creg c[3];
x q[0];
x q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
"""
        wrong = model_json({
            "task_type": "generate_qasm", "qasm": wrong_qasm,
            "expected_dominant_states": ["011"], "summary": "Wrong but self-consistent."
        })
        correct_qasm = wrong_qasm.replace(
            "x q[0];\nx q[1];",
            "x q[1];\nx q[2];",
        )
        correct = model_json({
            "task_type": "generate_qasm", "qasm": correct_qasm,
            "expected_dominant_states": ["110"], "summary": "Correct model output."
        })
        with LocalModel([wrong, correct]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat("Return a measured 3-qubit state that always yields 110.")

        self.assertIn("110=1024", reply)
        self.assertIn("x q[1];", reply)
        self.assertIn("x q[2];", reply)
        self.assertNotIn("x q[0];", reply)
        self.assertEqual(len(QueueAPIHandler.payloads), 2)
    def test_prompt_oracle_rejects_self_consistent_wrong_bell_distribution(self) -> None:
        product_qasm = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[2];
creg c[2];
h q[0];
measure q -> c;
"""
        wrong = model_json({
            "task_type": "generate_qasm", "qasm": product_qasm,
            "expected_dominant_states": ["00", "01"], "summary": "Not actually Bell."
        })
        correct = model_json({
            "task_type": "generate_qasm", "qasm": BELL_QASM,
            "expected_dominant_states": ["00", "11"], "summary": "Correct Bell pair."
        })
        with LocalModel([wrong, correct]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat("Prepare a Bell state and fully measure it.")

        self.assertIn("00", reply)
        self.assertIn("11", reply)
        self.assertEqual(len(QueueAPIHandler.payloads), 2)
        self.assertIn("cx q[0],q[1];", reply)

    def test_prompt_oracle_rejects_self_consistent_wrong_ghz_width(self) -> None:
        wrong = model_json({
            "task_type": "generate_qasm", "qasm": GHZ_QASM,
            "expected_dominant_states": ["000", "111"], "summary": "Wrong width."
        })
        ghz4 = GHZ_QASM.replace("q[3]", "q[4]").replace("c[3]", "c[4]").replace(
            "cx q[1],q[2];", "cx q[1],q[2];\ncx q[2],q[3];"
        ).replace(
            "measure q[2] -> c[2];",
            "measure q[2] -> c[2];\nmeasure q[3] -> c[3];",
        )
        correct = model_json({
            "task_type": "generate_qasm", "qasm": ghz4,
            "expected_dominant_states": ["0000", "1111"], "summary": "Correct width."
        })
        with LocalModel([wrong, correct]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat("Generate and fully measure a 4-qubit GHZ state.")

        self.assertIn("qreg q[4]", reply)
        self.assertEqual(len(QueueAPIHandler.payloads), 2)

    def test_ghz_target_takes_priority_when_prompt_mentions_bell_source(self) -> None:
        wrong = model_json({
            "task_type": "generate_qasm", "qasm": BELL_QASM,
            "expected_dominant_states": ["00", "11"], "summary": "Kept the Bell source."
        })
        correct = model_json({
            "task_type": "generate_qasm", "qasm": GHZ_QASM,
            "expected_dominant_states": ["000", "111"], "summary": "Expanded by the model."
        })
        with LocalModel([wrong, correct]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat("把 Bell 实验改成 3 qubit GHZ，并解释结果")

        self.assertIn("qreg q[3]", reply)
        self.assertIn("cx q[1],q[2];", reply)
        self.assertEqual(len(QueueAPIHandler.payloads), 2)

    def test_prompt_oracle_rejects_self_consistent_nonuniform_answer(self) -> None:
        zero_qasm = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[2];
creg c[2];
measure q -> c;
"""
        wrong = model_json({
            "task_type": "generate_qasm", "qasm": zero_qasm,
            "expected_dominant_states": ["00"], "summary": "Not uniform."
        })
        uniform_qasm = zero_qasm.replace(
            "measure q -> c;",
            "h q[0];\nh q[1];\nmeasure q -> c;",
        )
        correct = model_json({
            "task_type": "generate_qasm", "qasm": uniform_qasm,
            "expected_dominant_states": ["00", "01", "10", "11"],
            "summary": "Uniform model output."
        })
        with LocalModel([wrong, correct]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat("Make all four outcomes of a 2-qubit measurement equally likely.")

        self.assertIn("h q[0]", reply)
        self.assertIn("h q[1]", reply)
        self.assertEqual(len(QueueAPIHandler.payloads), 2)
    def test_prompt_oracle_rejects_wrong_phase_interference(self) -> None:
        wrong_qasm = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[1];
creg c[1];
measure q -> c;
"""
        wrong = model_json({
            "task_type": "generate_qasm", "qasm": wrong_qasm,
            "expected_dominant_states": ["0"], "summary": "Wrong interference."
        })
        correct_qasm = wrong_qasm.replace(
            "measure q -> c;",
            "h q[0];\nrz(pi) q[0];\nh q[0];\nmeasure q -> c;",
        )
        correct = model_json({
            "task_type": "generate_qasm", "qasm": correct_qasm,
            "expected_dominant_states": ["1"], "summary": "Correct model output."
        })
        with LocalModel([wrong, correct]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat(
                    "Generate the one-qubit interference H-RZ(pi)-H that must measure 1."
                )

        self.assertIn("rz(pi)", reply)
        self.assertIn("1=1024", reply)
        self.assertEqual(len(QueueAPIHandler.payloads), 2)

    def test_deterministic_w_reference_guides_retry_but_never_replaces_qasm(self) -> None:
        wrong_qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
measure q -> c;
"""
        correct_qasm = synthesize(CircuitSpec("w", 3)).qasm
        spec = {"family": "w", "qubits": 3}
        wrong = model_json({
            "task_type": "generate_qasm",
            "circuit_spec": spec,
            "qasm": wrong_qasm,
            "expected_dominant_states": ["000"],
            "summary": "Wrong first model output.",
        })
        correct = model_json({
            "task_type": "generate_qasm",
            "circuit_spec": spec,
            "qasm": correct_qasm,
            "expected_dominant_states": ["001", "010", "100"],
            "summary": "Corrected W state.",
        })
        with LocalModel([wrong, correct]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat(
                    "Generate and fully measure a 3-qubit W state."
                )

        self.assertEqual(len(QueueAPIHandler.payloads), 2)
        self.assertIn("ry(", reply)
        feedback = QueueAPIHandler.payloads[1]["messages"][-1]["content"]
        self.assertIn("deterministic-reference-w", feedback)

    def test_deterministic_basis_targets_retry_without_algorithmic_answer_fallback(self) -> None:
        wrong_qasm = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[5];
creg c[5];
x q[0];
x q[2];
measure q -> c;
"""
        wrong = model_json({
            "task_type": "repair_qasm", "qasm": wrong_qasm,
            "expected_dominant_states": ["00101"], "summary": "Still missing a high bit."
        })
        correct_qasm = wrong_qasm.replace("measure q -> c;", "x q[4];\nmeasure q -> c;")
        correct = model_json({
            "task_type": "repair_qasm", "qasm": correct_qasm,
            "expected_dominant_states": ["10101"], "summary": "Corrected by the model."
        })
        with LocalModel([wrong, correct]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat(
                    "Repair this circuit so a measured 5-qubit state always returns 10101."
                )

        self.assertEqual(len(QueueAPIHandler.payloads), 2)
        self.assertIn("x q[0];", reply)
        self.assertIn("x q[2];", reply)
        self.assertIn("x q[4];", reply)
        self.assertIn("10101=1024", reply)

    def test_agent_uses_an_explicit_validated_synthesis_layer(self) -> None:
        source = Path(l2_module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("_canonical_basis_state_qasm", source)
        self.assertNotIn('plan["qasm"] =', source)
        self.assertIn("normalize_circuit_spec", source)
        self.assertIn("synthesize(spec)", source)
        self.assertIn("reference_distribution", source)

    def test_invalid_qasm_is_repaired_within_the_call_budget(self) -> None:
        invalid = model_json(
            {
                "task_type": "repair_qasm",
                "qasm": "H q[0]; CX q[0] q[1]",
                "expected_dominant_states": ["00", "11"],
                "summary": "First attempt.",
            }
        )
        valid = model_json(
            {
                "task_type": "repair_qasm",
                "qasm": BELL_QASM,
                "expected_dominant_states": ["00", "11"],
                "summary": "Corrected Bell-state circuit.",
            }
        )
        with LocalModel([invalid, valid]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat(
                    "我想制备贝尔态，请保持意图并修复：H q[0]; CX q[0] q[1]"
                )

        self.assertIn("OPENQASM 2.0;", reply)
        self.assertEqual(len(QueueAPIHandler.payloads), 2)
        retry_messages = QueueAPIHandler.payloads[1]["messages"]
        self.assertIn("validation", retry_messages[-1]["content"].lower())

    def test_backend_selection_uses_canonical_capability_ids(self) -> None:
        response = model_json(
            {
                "task_type": "select_backend",
                "constraints": {
                    "min_qubits": 15,
                    "require_real_hardware": False,
                    "require_zero_queue": True,
                    "avoid_paid": True,
                    "require_no_account": True,
                    "allowed_platforms": [],
                },
                "summary": "The user needs a free zero-queue backend.",
            }
        )
        with LocalModel([response]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat("15 比特、免费、零排队、无需账号，推荐后端")

        self.assertIn("spinq_taurus_simulator", reply)
        self.assertNotIn("spinq_cloud_qpu", reply)
        self.assertEqual(len(QueueAPIHandler.payloads), 1)

    def test_backend_selection_reports_an_honest_no_solution(self) -> None:
        response = model_json(
            {
                "task_type": "select_backend",
                "constraints": {
                    "min_qubits": 200,
                    "require_real_hardware": True,
                    "require_zero_queue": True,
                    "avoid_paid": True,
                    "require_no_account": False,
                    "allowed_platforms": [],
                },
                "summary": "No published backend can satisfy every constraint.",
            }
        )
        with LocalModel([response]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                reply = adapter.agent_chat("我要 200 比特真机、免费且零排队")

        self.assertIn("没有满足全部约束", reply)
        self.assertIn("200", reply)

    def test_malformed_responses_stop_after_three_calls(self) -> None:
        with LocalModel(["bad one", "bad two", "bad three"]) as environment:
            with mock.patch.dict(os.environ, environment, clear=True):
                with self.assertRaisesRegex(RuntimeError, "three model attempts"):
                    adapter.agent_chat("生成一个单比特叠加态并测量")
        self.assertEqual(len(QueueAPIHandler.payloads), 3)

    def test_missing_configuration_names_variables_without_secret_values(self) -> None:
        with mock.patch.dict(os.environ, {"PRIVATE_VALUE": "never-print-me"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "LOOMQ_LLM_BASE_URL") as caught:
                adapter.agent_chat("hello")
        self.assertNotIn("never-print-me", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
