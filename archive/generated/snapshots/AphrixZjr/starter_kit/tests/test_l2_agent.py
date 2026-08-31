import json
import os
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT
sys.path.insert(0, str(STARTER))
import loomq_l2
import llm_client
import evaluator


def response(content):
    return {"choices": [{"message": {"content": content}}]}


class AgentAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        request = json.loads(self.rfile.read(length))
        user = request["messages"][-1]["content"]
        if "GHZ" in user:
            qasm = (
                "OPENQASM 2.0; qreg q[3]; creg c[3]; h q[0]; "
                "cx q[0],q[1]; cx q[0],q[2]; measure q -> c;"
            )
            content = json.dumps({"task": "qasm_generate", "qasm": qasm})
        else:
            content = json.dumps({
                "task": "backend_select",
                "hard_constraints": {
                    "queue": {"value": "none", "evidence": "no queue"}
                }, "soft_preferences": {}, "forbidden": {}, "unresolved": [],
            })
        body = json.dumps(response(content)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class L2AgentTests(unittest.TestCase):
    def test_qasm_json_is_validated_and_formatted(self):
        qasm = "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[1];\ncreg c[1];\nh q[0];\nmeasure q[0] -> c[0];"
        body = "explanation\n```json\n%s\n```" % json.dumps(
            {"task": "qasm_generate", "qasm": qasm}
        )
        with mock.patch.object(loomq_l2, "chat_completion", return_value=response(body)) as call:
            result = loomq_l2.agent_chat("make a circuit")
        self.assertEqual(result, qasm + "\n")
        self.assertEqual(call.call_count, 1)

    def test_invalid_qasm_is_rejected(self):
        body = json.dumps({"task": "qasm_repair", "qasm": "OPENQASM 2.0; h q[0];"})
        with mock.patch.object(loomq_l2, "chat_completion", return_value=response(body)) as call:
            with self.assertRaises(Exception):
                loomq_l2.agent_chat("repair this")
        self.assertEqual(call.call_count, 2)

    def test_backend_selection_uses_local_capability_table(self):
        body = json.dumps({
            "task": "backend_select",
            "hard_constraints": {
                "min_qubits": {"value": 15, "evidence": "15 qubits"},
                "queue": {"value": "none", "evidence": "no queue"},
            },
            "soft_preferences": {}, "forbidden": {}, "unresolved": []
        })
        with mock.patch.object(loomq_l2, "chat_completion", return_value=response(body)):
            result = loomq_l2.agent_chat("15 qubits and no queue")
        self.assertEqual(result, "spinq_taurus_simulator")
        self.assertEqual(sum(name in result for name in [b.id for b in loomq_l2._capabilities()]), 1)

    def test_missing_or_empty_model_content_fails(self):
        for malformed in ({}, response(""), response("not json")):
            with self.subTest(malformed=malformed):
                with mock.patch.object(loomq_l2, "chat_completion", return_value=malformed):
                    with self.assertRaises(RuntimeError):
                        loomq_l2.agent_chat("hello")

    def test_resource_limits_fail_before_expensive_work(self):
        with mock.patch.object(loomq_l2, "chat_completion") as call:
            with self.assertRaisesRegex(ValueError, "resource limit"):
                loomq_l2.agent_chat("x" * (loomq_l2.MAX_PROMPT_CHARS + 1))
        call.assert_not_called()

        oversized = response("x" * (loomq_l2.MAX_RESPONSE_CHARS + 1))
        with mock.patch.object(loomq_l2, "chat_completion", return_value=oversized):
            with self.assertRaisesRegex(RuntimeError, "response exceeds"):
                loomq_l2.agent_chat("hello")

    def test_json_depth_and_fence_limits_are_bounded(self):
        nested = value = {}
        for _ in range(loomq_l2.MAX_JSON_DEPTH + 2):
            value["x"] = {}
            value = value["x"]
        nested["task"] = "backend_select"
        with self.assertRaisesRegex(RuntimeError, "depth limit"):
            loomq_l2._json_object(json.dumps(nested))
        with self.assertRaisesRegex(RuntimeError, "code fences"):
            loomq_l2._json_object("```\n" * (loomq_l2.MAX_CODE_FENCES * 2 + 1))
        wide = {"task": "backend_select", "unresolved": list(range(loomq_l2.MAX_JSON_ITEMS))}
        with self.assertRaisesRegex(RuntimeError, "item limit"):
            loomq_l2._json_object(json.dumps(wide))

    def test_each_request_has_an_independent_context_and_timeout(self):
        body = json.dumps({
            "task": "backend_select",
            "hard_constraints": {"queue": {"value": "none", "evidence": "no queue"}},
            "soft_preferences": {}, "forbidden": {}, "unresolved": []
        })
        timeouts = []
        def fake(_messages, **kwargs):
            timeouts.append(kwargs["transport_timeout"])
            return response(body)
        with mock.patch.object(loomq_l2, "chat_completion", side_effect=fake):
            loomq_l2.agent_chat("first no queue")
            loomq_l2.agent_chat("second no queue")
        self.assertEqual(len(timeouts), 2)
        self.assertTrue(all(0 < value < loomq_l2.OVERALL_DEADLINE_SECONDS for value in timeouts))

    def test_parallel_requests_do_not_share_prompt_or_selection(self):
        def fake(messages, **_kwargs):
            prompt = messages[-1]["content"]
            platform = "spinq" if "spinq" in prompt else "braket"
            body = {
                "task": "backend_select",
                "hard_constraints": {
                    "platform": {"value": platform, "evidence": platform}
                }, "soft_preferences": {}, "forbidden": {}, "unresolved": [],
            }
            return response(json.dumps(body))

        prompts = ["use spinq" if index % 2 == 0 else "use braket" for index in range(20)]
        with mock.patch.object(loomq_l2, "chat_completion", side_effect=fake):
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(loomq_l2.agent_chat, prompts))
        for prompt, result in zip(prompts, results):
            self.assertTrue(result.startswith("spinq_") if "spinq" in prompt else result.startswith("braket_"))

    def test_qasm_qubit_limit_is_checked_after_static_parse(self):
        qasm = "OPENQASM 2.0; qreg q[%d];" % (loomq_l2.MAX_QUBITS + 1)
        body = json.dumps({"task": "qasm_generate", "qasm": qasm})
        with mock.patch.object(loomq_l2, "chat_completion", return_value=response(body)):
            with self.assertRaisesRegex(RuntimeError, "qubit limit"):
                loomq_l2.agent_chat("large circuit")

    def test_huge_register_is_rejected_before_parser_expansion(self):
        qasm = "OPENQASM 2.0; qreg q[1000000000]; creg c[1000000000]; measure q -> c;"
        with mock.patch.object(loomq_l2, "parse_qasm") as parser:
            with self.assertRaisesRegex(RuntimeError, "qubit limit"):
                loomq_l2._validated_candidate(qasm)
        parser.assert_not_called()

    def test_deep_parameter_expression_is_rejected_before_parser(self):
        angle = "(" * (loomq_l2.MAX_EXPRESSION_DEPTH + 1) + "pi" + ")" * (
            loomq_l2.MAX_EXPRESSION_DEPTH + 1
        )
        qasm = "OPENQASM 2.0; qreg q[1]; rz(%s) q[0];" % angle
        with mock.patch.object(loomq_l2, "parse_qasm") as parser:
            with self.assertRaisesRegex(RuntimeError, "expression depth"):
                loomq_l2._validated_candidate(qasm)
        parser.assert_not_called()

    def test_raw_markdown_qasm_is_accepted_and_wrapper_removed(self):
        qasm = "OPENQASM 2.0;\nqreg q[1];\nx q[0];"
        with mock.patch.object(
            loomq_l2, "chat_completion",
            return_value=response("Here it is:\n```qasm\n" + qasm + "\n```\nDone"),
        ):
            result = loomq_l2.agent_chat("generate x")
        self.assertEqual(result, "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[1];\nx q[0];\n")
        self.assertNotIn("```", result)

    def test_equivalent_candidates_deduplicate_but_distinct_candidates_fail(self):
        first = "OPENQASM 2.0; qreg q[1]; x q[0];"
        equivalent = "OPENQASM 2.0;\nqreg q[1];\n// same\nx q[0];"
        distinct = "OPENQASM 2.0; qreg q[1]; h q[0];"
        self.assertIn("x q[0]", loomq_l2._qasm({"qasm": first + "\n" + equivalent}))
        with self.assertRaisesRegex(RuntimeError, "multiple distinct"):
            loomq_l2._qasm({"qasm": first + "\n" + distinct})

    def test_too_many_qasm_candidates_are_rejected(self):
        source = "\n".join(
            "OPENQASM 2.0; qreg q%d[1];" % index
            for index in range(loomq_l2.MAX_QASM_CANDIDATES + 1)
        )
        with self.assertRaisesRegex(RuntimeError, "too many"):
            loomq_l2._qasm({"qasm": source})

    def test_backend_constraints_require_prompt_evidence(self):
        payload = {
            "task": "backend_select",
            "hard_constraints": {"cost": {"value": "free", "evidence": "free"}},
            "soft_preferences": {}, "forbidden": {}, "unresolved": [],
        }
        with self.assertRaisesRegex(RuntimeError, "absent"):
            loomq_l2._select_backend(payload, "use any backend")
        payload["hard_constraints"]["cost"] = {"value": "paid", "evidence": "free"}
        with self.assertRaisesRegex(RuntimeError, "not supported"):
            loomq_l2._select_backend(payload, "must be free")

    def test_backend_constraint_parse_failure_gets_one_correction(self):
        invalid = {
            "task": "backend_select",
            "hard_constraints": {"queue": {"value": "none", "evidence": "invented"}},
            "soft_preferences": {}, "forbidden": {}, "unresolved": [],
        }
        valid = {
            "task": "backend_select",
            "hard_constraints": {"queue": {"value": "none", "evidence": "无需排队"}},
            "soft_preferences": {}, "forbidden": {}, "unresolved": [],
        }
        replies = [response(json.dumps(invalid)), response(json.dumps(valid))]
        with mock.patch.object(loomq_l2, "chat_completion", side_effect=replies) as call:
            result = loomq_l2.agent_chat("我要一个无需排队的后端")
        self.assertEqual(call.call_count, 2)
        self.assertEqual(result, "spinq_taurus_simulator")

    def test_live_model_backend_synonyms_are_normalized(self):
        qpu_payload = {
            "hard_constraints": {
                "min_qubits": {"value": 70, "evidence": "70 比特"},
                "kind": {"value": "real", "evidence": "必须使用真机"},
            }, "soft_preferences": {}, "forbidden": {},
        }
        self.assertEqual(
            loomq_l2._select_backend(qpu_payload, "我要运行 70 比特电路，必须使用真机。"),
            "originq_wukong",
        )
        account_payload = {
            "hard_constraints": {
                "platform": {"value": "braket", "evidence": "Braket platform"},
                "requires_account": {"value": True, "evidence": "requires an account"},
                "cost": {"value": "paid", "evidence": "paid cloud backend"},
            }, "soft_preferences": {}, "forbidden": {},
        }
        self.assertEqual(
            loomq_l2._select_backend(
                account_payload,
                "Use the Braket platform; a paid cloud backend that requires an account is acceptable.",
            ),
            "braket_cloud",
        )

    def test_raw_prompt_locally_recovers_omitted_backend_constraints(self):
        empty = {
            "hard_constraints": {}, "soft_preferences": {}, "forbidden": {},
        }
        cases = (
            ("选择支持 34 比特的云端后端。", "braket_cloud"),
            ("Choose a QPU for a 9-qubit circuit.", "originq_wukong"),
            ("必须是 SpinQ 平台的 QPU 真机。", "spinq_cloud_qpu"),
            ("25 比特模拟器，但不要 AWS 或 Braket。", "originq_local_simulator"),
        )
        for prompt, expected in cases:
            with self.subTest(prompt=prompt):
                self.assertEqual(loomq_l2._select_backend(empty, prompt), expected)

    def test_invalid_model_constraint_can_degrade_to_local_prompt_facts(self):
        payload = {
            "hard_constraints": {
                "min_qubits": {"value": 8, "evidence": "8 比特真机"},
                "requires_account": {"value": False, "evidence": "免费额度可以接受"},
            }, "soft_preferences": {}, "forbidden": {},
        }
        result = loomq_l2._select_backend(
            payload, "8 比特真机，免费额度可以接受。", tolerate_invalid=True
        )
        self.assertIn(result, {"spinq_cloud_qpu", "originq_wukong"})

    def test_backend_forbidden_and_no_solution(self):
        payload = {
            "task": "backend_select",
            "hard_constraints": {
                "min_qubits": {"value": 30, "evidence": "30 qubits"},
                "kind": {"value": "simulator", "evidence": "simulator"},
            },
            "soft_preferences": {},
            "forbidden": {"platform": [
                {"value": "originq", "evidence": "not originq"}
            ]}, "unresolved": [],
        }
        with self.assertRaisesRegex(RuntimeError, "no backend"):
            loomq_l2._select_backend(payload, "30 qubits simulator, not originq")

    def test_backend_solver_matches_independent_exhaustive_oracle(self):
        values = {
            "min_qubits": [1, 8, 25, 72, 73],
            "kind": ["simulator", "qpu", "cloud"],
            "queue": ["none", "hours"],
            "cost": ["free", "paid"],
            "requires_account": [False, True],
            "platform": ["spinq", "originq", "braket"],
        }
        backends = loomq_l2._capabilities()
        for key, options in values.items():
            for required in options:
                if key == "min_qubits":
                    evidence = "%s qubits" % required
                elif key == "requires_account":
                    evidence = "requires account" if required else "no account"
                else:
                    evidence = {
                        "simulator": "simulator", "qpu": "qpu", "cloud": "cloud",
                        "none": "no queue", "hours": "hours", "free": "free",
                        "paid": "paid", "spinq": "spinq", "originq": "originq",
                        "braket": "braket",
                    }[required]
                payload = {
                    "hard_constraints": {key: {"value": required, "evidence": evidence}},
                    "soft_preferences": {}, "forbidden": {},
                }
                actual = {
                    item.backend.id for item in loomq_l2._evaluate_backends(payload, evidence)
                    if item.eligible
                }
                if key == "min_qubits":
                    expected = {item.id for item in backends if item.max_qubits >= required}
                else:
                    expected = {item.id for item in backends if getattr(item, key) == required}
                self.assertEqual(actual, expected, (key, required))

    def test_trusted_ghz_target_triggers_one_directed_repair(self):
        wrong = "OPENQASM 2.0; qreg q[3]; creg c[3]; h q[0]; measure q -> c;"
        right = (
            "OPENQASM 2.0; qreg q[3]; creg c[3]; h q[0]; "
            "cx q[0],q[1]; cx q[0],q[2]; measure q -> c;"
        )
        replies = [
            response(json.dumps({"task": "qasm_generate", "qasm": wrong})),
            response(json.dumps({"task": "qasm_repair", "qasm": right})),
        ]
        with mock.patch.object(loomq_l2, "chat_completion", side_effect=replies) as call:
            result = loomq_l2.agent_chat("生成一个 3 比特 GHZ 态并进行全测量")
        self.assertEqual(call.call_count, 2)
        self.assertIn("cx q[0],q[2]", result)

    def test_failed_repair_uses_oracle_verified_canonical_target(self):
        wrong = "OPENQASM 2.0; qreg q[3]; h q[0];"
        replies = [
            response(json.dumps({"task": "qasm_generate", "qasm": wrong})),
            RuntimeError("temporary repair failure"),
        ]
        with mock.patch.object(loomq_l2, "chat_completion", side_effect=replies):
            result = loomq_l2.agent_chat("make a 3-qubit GHZ state")
        target = loomq_l2._target_spec("make a 3-qubit GHZ state")
        self.assertIsNone(loomq_l2._semantic_diagnostic(
            loomq_l2._validated_candidate(result), target
        ))
        self.assertIn("cx q[0],q[2];", result)

    def test_transient_retry_does_not_consume_semantic_repair(self):
        wrong = "OPENQASM 2.0; qreg q[3]; creg c[3]; h q[0]; measure q -> c;"
        right = (
            "OPENQASM 2.0; qreg q[3]; creg c[3]; h q[0]; "
            "cx q[0],q[1]; cx q[0],q[2]; measure q -> c;"
        )
        replies = [
            RuntimeError("LoomQ L2 API returned HTTP 503"),
            response(json.dumps({"task": "qasm_generate", "qasm": wrong})),
            response(json.dumps({"task": "qasm_repair", "qasm": right})),
        ]
        with mock.patch.object(loomq_l2, "chat_completion", side_effect=replies) as call, \
                mock.patch.object(loomq_l2.time, "sleep"):
            result = loomq_l2.agent_chat("make a 3-qubit GHZ state and measure all")
        self.assertEqual(call.call_count, 3)
        self.assertIn("cx q[0],q[2];", result)

    def test_correct_trusted_target_uses_one_call(self):
        qasm = (
            "OPENQASM 2.0; qreg q[2]; creg c[2]; h q[0]; "
            "cx q[0],q[1]; measure q -> c;"
        )
        body = response(json.dumps({"task": "qasm_generate", "qasm": qasm}))
        with mock.patch.object(loomq_l2, "chat_completion", return_value=body) as call:
            loomq_l2.agent_chat("Make a Bell state and measure all qubits")
        self.assertEqual(call.call_count, 1)

    def test_target_parser_handles_common_qubit_variants(self):
        self.assertEqual(loomq_l2._target_spec("生成 4 个量子比特 GHZ 态").qubits, 4)
        self.assertEqual(loomq_l2._target_spec("Generate GHZ-5").qubits, 5)

    def test_untrusted_open_target_skips_semantic_rejection(self):
        qasm = "OPENQASM 2.0; qreg q[1]; x q[0];"
        body = response(json.dumps({"task": "qasm_generate", "qasm": qasm}))
        with mock.patch.object(loomq_l2, "chat_completion", return_value=body) as call:
            result = loomq_l2.agent_chat("Prepare my custom research state")
        self.assertIn("x q[0]", result)
        self.assertEqual(call.call_count, 1)

    def test_local_openai_compatible_server_end_to_end(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), AgentAPIHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        environment = {
            "LOOMQ_LLM_BASE_URL": "http://127.0.0.1:%d" % server.server_port,
            "LOOMQ_LLM_API_KEY": "test-only",
            "LOOMQ_LLM_MODEL": "local-model",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "2",
        }
        try:
            with mock.patch.dict(os.environ, environment, clear=True), mock.patch.object(
                loomq_l2, "chat_completion", wraps=llm_client.chat_completion
            ):
                result = loomq_l2.agent_chat("生成一个 3 比特 GHZ 态并进行全测量")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertIn("OPENQASM 2.0;", result)
        self.assertIn("cx q[0],q[2];", result)

    def test_public_evaluator_passes_against_local_compatible_server(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), AgentAPIHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        environment = {
            "LOOMQ_LLM_BASE_URL": "http://127.0.0.1:%d" % server.server_port,
            "LOOMQ_LLM_API_KEY": "test-only",
            "LOOMQ_LLM_MODEL": "local-model",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "2",
        }
        try:
            with mock.patch.dict(os.environ, environment, clear=True):
                cases = evaluator.evaluate_l2()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(cases[0]["status"], "PASS", cases)


if __name__ == "__main__":
    unittest.main()
