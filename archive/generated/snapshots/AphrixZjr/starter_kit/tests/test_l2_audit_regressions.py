import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


STARTER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STARTER))

import llm_client
import loomq_l2
from loomq_l1 import parse_qasm
from web.app import (
    ConflictError,
    GUIDE_FALLBACK_REPLIES,
    STAGES,
    ExperimentStore,
    _circuit_ir,
    _description,
    _validation,
)


BELL_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""


class RetryThenSuccessHandler(BaseHTTPRequestHandler):
    requests = 0

    def log_message(self, *_args):
        return

    def do_POST(self):
        type(self).requests += 1
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if type(self).requests == 1:
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        qasm = "OPENQASM 2.0; qreg q[1]; x q[0];"
        content = json.dumps({"task": "qasm_generate", "qasm": qasm})
        body = json.dumps({
            "choices": [{"message": {"role": "assistant", "content": content}}]
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class L2ObjectiveAuditRegressions(unittest.TestCase):
    def test_full_measurement_requires_a_classical_bijection(self):
        target = loomq_l2._target_spec("Make a Bell state and measure all qubits")
        duplicate = BELL_QASM.replace("measure q[1] -> c[1]", "measure q[1] -> c[0]")
        diagnostic = loomq_l2._semantic_diagnostic(
            loomq_l2._validated_candidate(duplicate), target
        )
        self.assertIn("distinct classical bit", diagnostic)

        extra_classical = BELL_QASM.replace("creg c[2]", "creg c[3]")
        diagnostic = loomq_l2._semantic_diagnostic(
            loomq_l2._validated_candidate(extra_classical), target
        )
        self.assertIn("classical register width", diagnostic)

    def test_full_measurement_accepts_multi_register_permutations(self):
        qasm = """OPENQASM 2.0;
qreg left[1]; qreg right[1];
creg low[1]; creg high[1];
h left[0]; cx left[0],right[0];
measure left[0] -> high[0];
measure right[0] -> low[0];
"""
        target = loomq_l2._target_spec("制备贝尔态并读出所有线路")
        self.assertIsNone(loomq_l2._semantic_diagnostic(
            loomq_l2._validated_candidate(qasm), target
        ))

    def test_agent_repairs_a_lossy_measurement_map(self):
        wrong = BELL_QASM.replace("measure q[1] -> c[1]", "measure q[1] -> c[0]")
        replies = [
            {"choices": [{"message": {"content": json.dumps(
                {"task": "qasm_generate", "qasm": wrong}
            )}}]},
            {"choices": [{"message": {"content": json.dumps(
                {"task": "qasm_repair", "qasm": BELL_QASM}
            )}}]},
        ]
        with mock.patch.object(loomq_l2, "chat_completion", side_effect=replies) as call:
            result = loomq_l2.agent_chat("Make a Bell state and measure all qubits")
        self.assertEqual(call.call_count, 2)
        self.assertIn("measure q[1] -> c[1]", result)

    def test_controlled_aliases_chinese_numbers_and_readout_synonyms(self):
        target = loomq_l2._target_spec("三比特最大纠缠态，读出所有线路")
        self.assertEqual((target.family, target.qubits, target.require_full_measurement),
                         ("ghz", 3, True))
        cat = loomq_l2._target_spec("制备五比特猫态并读出全部量子位")
        self.assertEqual((cat.family, cat.qubits, cat.require_full_measurement),
                         ("ghz", 5, True))
        constraints, _ = loomq_l2._local_backend_constraints("选择支持二十六比特的模拟器")
        self.assertEqual(constraints["min_qubits"], 26)
        self.assertEqual(constraints["kind"], "simulator")
        self.assertEqual(
            loomq_l2._values_supported_by_evidence("min_qubits", "至少十五比特"),
            {15},
        )

    def test_without_charge_can_only_mean_free(self):
        prompt = "Select a simulator without charge"
        paid = {
            "hard_constraints": {
                "cost": {"value": "paid", "evidence": "without charge"},
            },
            "soft_preferences": {}, "forbidden": {},
        }
        with self.assertRaisesRegex(RuntimeError, "not supported"):
            loomq_l2._select_backend(paid, prompt)
        self.assertEqual(
            loomq_l2._local_backend_constraints(prompt)[0]["cost"], "free"
        )

    def test_adversarial_backend_phrases_are_directly_recovered(self):
        empty = {"hard_constraints": {}, "soft_preferences": {}, "forbidden": {}}
        cases = (
            ("Use AWS without an account for 20 qubits.", "braket_local_simulator"),
            (
                "Use AWS without requiring an account for 20 qubits.",
                "braket_local_simulator",
            ),
            ("Use AWS but no paid services for 20 qubits.", "braket_local_simulator"),
            (
                "I don't want AWS; choose a 25-qubit simulator.",
                "originq_local_simulator",
            ),
            (
                "Choose any 25-qubit simulator except AWS.",
                "originq_local_simulator",
            ),
            ("Run 20 qubits without using AWS.", "spinq_taurus_simulator"),
            ("Use a real machine for 8 qubits.", "spinq_cloud_qpu"),
            (
                "Use a physical quantum computer for 9 qubits.",
                "originq_wukong",
            ),
        )
        for prompt, expected in cases:
            with self.subTest(prompt=prompt):
                self.assertEqual(loomq_l2._select_backend(empty, prompt), expected)

    def test_local_platform_relationship_overrides_model_misclassification(self):
        positive_misread = {
            "hard_constraints": {}, "soft_preferences": {},
            "forbidden": {"platform": [
                {"value": "braket", "evidence": "AWS"},
            ]},
        }
        self.assertEqual(
            loomq_l2._select_backend(
                positive_misread, "Use AWS without an account for 20 qubits."
            ),
            "braket_local_simulator",
        )
        negative_misread = {
            "hard_constraints": {
                "platform": {"value": "braket", "evidence": "AWS"},
            },
            "soft_preferences": {}, "forbidden": {},
        }
        self.assertEqual(
            loomq_l2._select_backend(
                negative_misread, "Run 20 qubits without using AWS."
            ),
            "spinq_taurus_simulator",
        )

    def test_429_or_503_gets_one_budgeted_retry_without_real_wait(self):
        RetryThenSuccessHandler.requests = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), RetryThenSuccessHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        environment = {
            "LOOMQ_LLM_BASE_URL": "http://127.0.0.1:%d" % server.server_port,
            "LOOMQ_LLM_API_KEY": "local-key",
            "LOOMQ_LLM_MODEL": "local-model",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "2",
        }
        try:
            with mock.patch.dict(os.environ, environment, clear=True), \
                    mock.patch.object(loomq_l2.time, "sleep") as sleep:
                result = loomq_l2.agent_chat("Prepare my custom one-qubit state")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertIn("x q[0]", result)
        self.assertEqual(RetryThenSuccessHandler.requests, 2)
        sleep.assert_called_once()

    def test_default_output_budget_is_900_and_explicit_limit_is_bounded(self):
        base = {
            "LOOMQ_LLM_BASE_URL": "http://127.0.0.1:1",
            "LOOMQ_LLM_API_KEY": "local-key",
            "LOOMQ_LLM_MODEL": "local-model",
        }
        with mock.patch.dict(os.environ, base, clear=True):
            self.assertEqual(llm_client._configuration()[4], 900)
        with mock.patch.dict(os.environ, {
            **base, "LOOMQ_LLM_MAX_OUTPUT_TOKENS": "1001",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "must not exceed 1000"):
                llm_client._configuration()


class L2WebAuditRegressions(unittest.TestCase):
    def test_qasm_creation_preserves_valid_and_invalid_states(self):
        store = ExperimentStore()
        valid = store.create(mode="qasm", qasm=BELL_QASM)
        invalid = store.create(mode="qasm", qasm="OPENQASM 2.0\nqreg q[1];")
        self.assertEqual(valid["state"], "runnable")
        self.assertEqual(invalid["state"], "invalid")

    def test_rejected_qasm_input_does_not_mutate_history_or_revision(self):
        store = ExperimentStore()
        session = store.create()
        live = store.get(session["session_id"])
        history_before = len(live.history)
        future_before = len(live.future)
        revision_before = live.workbench_revision

        with self.assertRaisesRegex(ValueError, "QASM must be text"):
            store.update_qasm(
                session["session_id"], None, session["circuit_revision"]
            )

        self.assertEqual(len(live.history), history_before)
        self.assertEqual(len(live.future), future_before)
        self.assertEqual(live.workbench_revision, revision_before)

    def test_bell_guide_completes_without_model_configuration(self):
        store = ExperimentStore()
        session = store.create()
        environment = {
            "LOOMQ_LLM_BASE_URL": "", "LOOMQ_LLM_API_KEY": "",
            "LOOMQ_LLM_MODEL": "",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            for _ in range(8):
                previous_index = session["guide"]["index"]
                value = store.agent_turn(
                    session["session_id"], session["guide"]["preset_instruction"]
                )
                self.assertEqual(value["status"], "fallback")
                self.assertEqual(value["source"], "preset")
                self.assertIsNone(value["model"])
                self.assertFalse(value["model_attempted"])
                self.assertFalse(value["model_generated"])
                self.assertEqual(value["understanding"], "")
                self.assertEqual(value["fallback_reason"], "not_configured")
                self.assertIn("本地预置回复｜未调用模型", value["response"])
                session = value["session"]
                if not session["guide"]["complete"]:
                    self.assertEqual(session["guide"]["index"], previous_index + 1)
        self.assertTrue(session["guide"]["complete"])
        self.assertEqual(session["state"], "draft")
        self.assertNotIn("cx q[0],q[1]", session["qasm"])

    def test_exact_guide_instruction_falls_back_when_model_connection_fails(self):
        def unavailable(_messages):
            raise RuntimeError("simulated connection failure")

        store = ExperimentStore(agent_transport=unavailable)
        session = store.create()
        value = store.agent_turn(
            session["session_id"], session["guide"]["preset_instruction"]
        )
        self.assertEqual(value["status"], "fallback")
        self.assertEqual(value["source"], "preset")
        self.assertEqual(value["fallback_reason"], "model_response_unavailable")
        self.assertTrue(value["model_attempted"])
        self.assertFalse(value["model_generated"])
        self.assertEqual(value["session"]["guide"]["index"], 2)
        self.assertIn("本地预置回复｜非模型生成", value["response"])
        self.assertNotIn("未调用模型", value["response"])
        self.assertNotIn("simulated connection failure", value["response"])

    def test_reply_failure_after_tool_call_does_not_advance_twice(self):
        calls = 0

        def transport(_messages):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {"choices": [{"message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "guide-once", "type": "function",
                        "function": {
                            "name": "advance_bell_guide", "arguments": "{}",
                        },
                    }],
                }}]}
            raise RuntimeError("simulated follow-up failure")

        store = ExperimentStore(agent_transport=transport)
        session = store.create()
        revision = session["circuit_revision"]
        value = store.agent_turn(
            session["session_id"], session["guide"]["preset_instruction"]
        )
        self.assertEqual(calls, 2)
        self.assertEqual(value["status"], "fallback")
        self.assertEqual(value["fallback_reason"], "explanation_failed")
        self.assertTrue(value["model_attempted"])
        self.assertFalse(value["model_generated"])
        self.assertEqual(value["session"]["guide"]["index"], 2)
        self.assertEqual(value["session"]["circuit_revision"], revision + 1)

    def test_invalid_model_tool_arguments_use_preset_not_local_error(self):
        calls = 0

        def transport(_messages):
            nonlocal calls
            calls += 1
            return {"choices": [{"message": {
                "content": None,
                "tool_calls": [{
                    "id": "bad-arguments", "type": "function",
                    "function": {
                        "name": "advance_bell_guide", "arguments": "[]",
                    },
                }],
            }}]}

        store = ExperimentStore(agent_transport=transport)
        session = store.create()
        value = store.agent_turn(
            session["session_id"], session["guide"]["preset_instruction"]
        )

        self.assertEqual(calls, 1)
        self.assertEqual(value["status"], "fallback")
        self.assertEqual(value["source"], "preset")
        self.assertEqual(value["fallback_reason"], "model_response_unavailable")
        self.assertNotIn("error_kind", value)
        self.assertEqual(value["session"]["guide"]["index"], 2)

    def test_local_guide_tool_failure_is_not_retried_or_misreported(self):
        calls = 0
        run_calls = 0

        def transport(_messages):
            nonlocal calls
            calls += 1
            return {"choices": [{"message": {
                "content": None,
                "tool_calls": [{
                    "id": "guide-run", "type": "function",
                    "function": {
                        "name": "advance_bell_guide", "arguments": "{}",
                    },
                }],
            }}]}

        def failing_runner(_circuit, _shots):
            nonlocal run_calls
            run_calls += 1
            raise RuntimeError("simulated local runner failure")

        store = ExperimentStore(
            agent_transport=transport,
            backend_probes={"spinq_taurus_simulator": lambda: object()},
            backend_runners={"spinq_taurus_simulator": failing_runner},
        )
        session = store.create()
        session = store.select_backend(
            session["session_id"], "spinq_taurus_simulator"
        )
        for _ in range(6):
            session = store.advance(
                session["session_id"],
                expected_revision=session["circuit_revision"],
            )
        live = store.get(session["session_id"])
        history_before = len(live.history)
        revision_before = live.workbench_revision

        value = store.agent_turn(
            session["session_id"], session["guide"]["preset_instruction"]
        )

        self.assertEqual(calls, 1)
        self.assertEqual(run_calls, 1)
        self.assertEqual(value["status"], "error")
        self.assertEqual(value["source"], "local")
        self.assertEqual(value["error_kind"], "local_tool_error")
        self.assertNotIn("fallback_reason", value)
        self.assertEqual(value["session"]["guide"]["stage"], "run")
        self.assertEqual(len(live.history), history_before)
        self.assertEqual(live.workbench_revision, revision_before)

    def test_stale_guide_request_cannot_overwrite_new_qasm(self):
        entered = threading.Event()
        release = threading.Event()

        def transport(messages):
            if any(item.get("role") == "tool" for item in messages):
                return {"choices": [{"message": {"content": "阶段已完成。"}}]}
            entered.set()
            self.assertTrue(release.wait(5))
            return {"choices": [{"message": {
                "content": None,
                "tool_calls": [{
                    "id": "stale-guide", "type": "function",
                    "function": {
                        "name": "advance_bell_guide", "arguments": "{}",
                    },
                }],
            }}]}

        store = ExperimentStore(agent_transport=transport)
        session = store.create()
        results = []
        errors = []

        def request_guide():
            try:
                results.append(store.agent_turn(
                    session["session_id"], session["guide"]["preset_instruction"]
                ))
            except Exception as exc:  # assertion below checks the exact type
                errors.append(exc)

        worker = threading.Thread(target=request_guide)
        worker.start()
        self.assertTrue(entered.wait(5))
        changed_qasm = session["qasm"] + "x q[0];\n"
        store.update_qasm(
            session["session_id"], changed_qasm, session["circuit_revision"]
        )
        release.set()
        worker.join(5)

        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ConflictError)
        current = store.get(session["session_id"])
        self.assertEqual(current.guide_stage, 0)
        self.assertEqual(current.qasm, changed_qasm)

    def test_concurrent_same_stage_presets_advance_only_once(self):
        barrier = threading.Barrier(2)

        def transport(messages):
            if any(item.get("role") == "tool" for item in messages):
                return {"choices": [{"message": {"content": "阶段已完成。"}}]}
            barrier.wait(5)
            return {"choices": [{"message": {
                "content": None,
                "tool_calls": [{
                    "id": "concurrent-guide-%s" % threading.get_ident(),
                    "type": "function",
                    "function": {
                        "name": "advance_bell_guide", "arguments": "{}",
                    },
                }],
            }}]}

        store = ExperimentStore(agent_transport=transport)
        session = store.create()
        results = []
        errors = []

        def request_guide():
            try:
                results.append(store.agent_turn(
                    session["session_id"], session["guide"]["preset_instruction"]
                ))
            except Exception as exc:  # assertion below checks the exact type
                errors.append(exc)

        workers = [threading.Thread(target=request_guide) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(5)

        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "ready")
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ConflictError)
        current = store.get(session["session_id"])
        self.assertEqual(current.guide_stage, 1)
        self.assertEqual(current.circuit_revision, session["circuit_revision"] + 1)

    def test_fallback_is_limited_to_the_exact_current_preset(self):
        store = ExperimentStore()
        session = store.create()
        current = session["guide"]["preset_instruction"]
        future = "请继续 Bell 引导：在 q[0] 上加入 H 门建立叠加。"
        environment = {
            "LOOMQ_LLM_BASE_URL": "", "LOOMQ_LLM_API_KEY": "",
            "LOOMQ_LLM_MODEL": "",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            for prompt in (current + " 请详细解释", future, "什么是 Bell 态？"):
                value = store.agent_turn(session["session_id"], prompt)
                self.assertEqual(value["status"], "unavailable")
                self.assertEqual(store.get(session["session_id"]).guide_stage, 0)

    def test_every_guide_stage_has_one_preset_fallback_reply(self):
        self.assertEqual(set(GUIDE_FALLBACK_REPLIES), set(STAGES))
        self.assertTrue(all(GUIDE_FALLBACK_REPLIES[stage] for stage in STAGES))

    def test_web_validation_reports_real_target_semantics(self):
        valid = _validation(parse_qasm(BELL_QASM), "制备两比特 Bell 态并全部测量")
        product = _validation(
            parse_qasm(BELL_QASM.replace("cx q[0],q[1];\n", "")),
            "制备两比特 Bell 态并全部测量",
        )
        open_goal = _validation(parse_qasm(BELL_QASM), "研究自定义态")
        collision = _validation(parse_qasm(
            BELL_QASM.replace("measure q[1] -> c[1]", "measure q[1] -> c[0]")
        ), "研究自定义态")
        self.assertEqual(valid["target"]["label"], "目标一致")
        self.assertEqual(product["target"]["status"], "fail")
        self.assertTrue(product["runnable"])
        self.assertFalse(product["target_supported"])
        self.assertEqual(open_goal["target"]["label"], "当前未提供语义证明")
        self.assertEqual(collision["measurements"]["status"], "fail")
        self.assertFalse(collision["runnable"])

    def test_web_rejects_measurement_collisions_but_allows_labeled_target_exploration(self):
        store = ExperimentStore()
        collision_qasm = BELL_QASM.replace(
            "measure q[1] -> c[1]", "measure q[1] -> c[0]"
        )
        collision = store.create(
            mode="qasm", qasm=collision_qasm,
            goal="制备两比特 Bell 态并全部测量",
        )
        with self.assertRaisesRegex(ValueError, "unsafe measurement mapping"):
            store.run(collision["session_id"], shots=32)
        self.assertIsNone(store.get(collision["session_id"]).result)

        product_qasm = BELL_QASM.replace("cx q[0],q[1];\n", "")
        product = store.create(
            mode="qasm", qasm=product_qasm,
            goal="制备两比特 Bell 态并全部测量",
        )
        result = store.run(product["session_id"], shots=32)["result"]
        self.assertFalse(result["target_supported"])
        self.assertIn("本次运行不支持当前目标", result["boundary"])

    def test_agent_qasm_with_measurement_collision_is_not_applicable(self):
        collision_qasm = BELL_QASM.replace(
            "measure q[1] -> c[1]", "measure q[1] -> c[0]"
        )

        def transport(_messages):
            return {"choices": [{"message": {"content": json.dumps({
                "understanding": "修改读出", "response": "请审阅。",
                "proposal": {
                    "kind": "qasm", "qasm": collision_qasm,
                    "summary": "冲突的测量映射",
                },
            }, ensure_ascii=False)}}]}

        store = ExperimentStore(agent_transport=transport)
        session = store.create()
        original_qasm = session["qasm"]
        value = store.agent_turn(session["session_id"], "帮我修改当前 QASM")
        proposal = value["proposal"]
        self.assertFalse(proposal["safe_to_apply"])
        self.assertEqual(proposal["validation"]["measurements"]["status"], "fail")
        with self.assertRaisesRegex(ValueError, "failed structural validation"):
            store.apply_agent_proposal(session["session_id"], proposal["proposal_id"])
        self.assertEqual(store.get(session["session_id"]).qasm, original_qasm)

        # Even a corrupted cached decision cannot bypass the apply-time gate.
        store.pending_proposals[proposal["proposal_id"]]["safe_to_apply"] = True
        with self.assertRaisesRegex(ValueError, "failed structural validation"):
            store.apply_agent_proposal(session["session_id"], proposal["proposal_id"])
        self.assertEqual(store.get(session["session_id"]).qasm, original_qasm)

    def test_apply_revalidates_qasm_after_a_cached_safe_decision(self):
        def transport(_messages):
            return {"choices": [{"message": {"content": json.dumps({
                "understanding": "保留当前电路", "response": "请审阅。",
                "proposal": {
                    "kind": "qasm", "qasm": BELL_QASM,
                    "summary": "保持安全的 Bell 测量",
                },
            }, ensure_ascii=False)}}]}

        store = ExperimentStore(agent_transport=transport)
        session = store.create()
        original_qasm = session["qasm"]
        value = store.agent_turn(session["session_id"], "帮我修改当前 QASM")
        proposal = value["proposal"]
        self.assertTrue(proposal["safe_to_apply"])

        collision_qasm = BELL_QASM.replace(
            "measure q[1] -> c[1]", "measure q[1] -> c[0]"
        )
        store.pending_proposals[proposal["proposal_id"]]["qasm"] = collision_qasm
        with self.assertRaisesRegex(ValueError, "failed structural validation"):
            store.apply_agent_proposal(session["session_id"], proposal["proposal_id"])
        self.assertEqual(store.get(session["session_id"]).qasm, original_qasm)

    def test_multi_register_identity_survives_web_ir_and_description(self):
        circuit = parse_qasm("""OPENQASM 2.0;
qreg a[1]; qreg b[1]; creg x[1]; creg y[1];
h a[0]; cx a[0],b[0];
measure a[0] -> y[0]; measure b[0] -> x[0];
""")
        ir = _circuit_ir(circuit)
        self.assertEqual(ir["qubit_labels"], ["a[0]", "b[0]"])
        self.assertEqual(ir["gates"][1]["qubits"], [0, 1])
        self.assertEqual(ir["measurements"][0]["classical_label"], "y[0]")
        description = _description(circuit)
        self.assertIn("a[0]", description)
        self.assertIn("b[0]", description)
        self.assertIn("y[0]", description)

    def test_counting_method_and_backend_boundary_are_honest(self):
        built_in = ExperimentStore()
        session = built_in.create(mode="qasm", qasm=BELL_QASM)
        result = built_in.run(session["session_id"], shots=7)["result"]
        self.assertIn("确定性折算", result["counting_method"])
        self.assertIn("不是真实逐 shot 抽样", result["counting_method"])
        self.assertIn("LoomQ 本地理想参考模拟器", result["boundary"])

        backend_ids = tuple((
            "spinq_taurus_simulator", "originq_local_simulator",
            "braket_local_simulator",
        ))
        provider = ExperimentStore(
            backend_probes={item: (lambda: object()) for item in backend_ids},
            backend_runners={item: (lambda _circuit, shots: (
                {"00": shots}, "vendor-engine", "job", {}
            )) for item in backend_ids},
        )
        session = provider.create(mode="qasm", qasm=BELL_QASM)
        provider.select_backend(session["session_id"], "spinq_taurus_simulator")
        result = provider.run(session["session_id"], shots=8)["result"]
        self.assertIn("量旋 SpinQit", result["boundary"])
        self.assertIn("供应商", result["counting_method"])
        self.assertNotIn("LoomQ 本地理想参考模拟器", result["boundary"])

    def test_static_client_routes_guide_through_agent_and_has_narrow_layout(self):
        js = (STARTER / "web" / "static" / "app.js").read_text(encoding="utf-8")
        css = (STARTER / "web" / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertNotIn('const action = "advance";', js)
        self.assertIn("填入本阶段指令", js)
        self.assertIn('$("#agent-input").focus();', js)
        self.assertIn("发送后才会推进实验", js)
        self.assertNotIn("if (active) prefillGuideInstruction(true)", js)
        self.assertEqual(js.count("prefillGuideInstruction("), 2)
        self.assertNotIn("/advance", js)
        self.assertIn("counting_method", js)
        self.assertIn("@media (max-width: 1099px)", css)
        self.assertIn("body { margin: 0; min-width: 0; }", css)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", css)


if __name__ == "__main__":
    unittest.main()
