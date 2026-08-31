import http.client
import json
import sys
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT
if str(STARTER) not in sys.path:
    sys.path.insert(0, str(STARTER))

import web.app as web_app
from web.app import BELL_QASM, ConflictError, ExperimentStore, archived_hardware_evidence
from web.server import LoomQHandler, ThreadingHTTPServer


class GuidedExperimentServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = ExperimentStore()
        self.session = self.store.create()
        self.session_id = self.session["session_id"]

    def test_bell_eight_stage_golden_path(self):
        self.assertEqual(self.session["goal"], "")
        self.assertEqual(self.session["goal_revision"], 0)
        seen = [self.session["guide"]["stage"]]
        actions = 0
        current = self.session
        while current["guide"]["stage"] != "explore":
            current = self.store.advance(
                self.session_id,
                prediction="00 与 11 大致各半",
                expected_revision=current["circuit_revision"],
            )
            actions += 1
            seen.append(current["guide"]["stage"])
        self.assertEqual(
            seen,
            ["goal", "h", "cx", "measurement", "prediction", "validation", "run", "explore"],
        )
        self.assertLessEqual(actions, 20)
        self.assertEqual(current["state"], "completed")
        self.assertEqual(set(current["result"]["counts"]), {"00", "11"})
        self.assertEqual(sum(current["result"]["counts"].values()), 1024)
        self.assertIn("本地理想参考模拟器", current["result"]["boundary"])
        self.assertIn("真机计数", current["result"]["boundary"])
        self.assertIn("H 门", current["circuit_description"])
        self.assertIn("CX 门", current["circuit_description"])
        self.assertIn("Bell 态", current["goal"])

    def test_bell_guide_uses_eight_agent_presets_and_one_forced_tool_each(self):
        calls = 0
        captured = []

        def transport(messages):
            nonlocal calls
            captured.append(messages)
            calls += 1
            if calls % 2:
                return {"choices": [{"message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "guide-%d" % calls, "type": "function",
                        "function": {"name": "advance_bell_guide", "arguments": "{}"},
                    }],
                }}]}
            return {"choices": [{"message": {"content": "本阶段已完成；请点击填入下一阶段指令。"}}]}

        store = ExperimentStore(agent_transport=transport)
        session = store.create()
        presets = []
        for _ in range(8):
            preset = session["guide"]["preset_instruction"]
            presets.append(preset)
            value = store.agent_turn(session["session_id"], preset)
            self.assertEqual(value["tools_used"], ["advance_bell_guide"])
            self.assertIsNone(value["proposal"])
            session = value["session"]

        self.assertEqual(len(set(presets)), 8)
        self.assertTrue(session["guide"]["complete"])
        self.assertNotIn("cx q[0],q[1]", session["qasm"])
        self.assertEqual(calls, 16)
        guide_systems = [messages[0]["content"] for messages in captured[::2]]
        self.assertTrue(all("advance_bell_guide" in prompt for prompt in guide_systems))

    def test_bell_preset_is_rejected_when_it_is_not_the_current_stage(self):
        store = ExperimentStore(agent_transport=lambda _messages: {
            "choices": [{"message": {"content": json.dumps({
                "understanding": "请求修改电路", "response": "需要用户确认。", "proposal": None,
            }, ensure_ascii=False)}}]
        })
        session = store.create()
        future_preset = "请继续 Bell 引导：在 q[0] 上加入 H 门建立叠加。"
        value = store.agent_turn(session["session_id"], future_preset)
        self.assertEqual(value["tools_used"], [])
        self.assertEqual(store.get(session["session_id"]).guide_stage, 0)

    def test_invalid_qasm_preserves_last_valid_circuit_and_can_repair(self):
        current = self.store.advance(self.session_id, expected_revision=self.session["circuit_revision"])
        current = self.store.advance(self.session_id, expected_revision=current["circuit_revision"])
        last_ir = current["circuit_ir"]
        broken = 'OPENQASM 2.0\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nh q[0]\nmeasure q -> c;\n'
        invalid = self.store.update_qasm(self.session_id, broken, current["circuit_revision"])
        self.assertEqual(invalid["state"], "invalid")
        self.assertEqual(invalid["circuit_ir"], last_ir)
        proposal = self.store.repair(self.session_id)
        self.assertTrue(proposal["safe"])
        self.assertIn("+OPENQASM 2.0;", proposal["diff"])
        repaired = self.store.repair(self.session_id, apply=True)["session"]
        self.assertNotEqual(repaired["state"], "invalid")
        undone = self.store.undo(self.session_id)
        self.assertEqual(undone["qasm"], broken)

    def test_repair_of_valid_qasm_is_a_non_action(self):
        proposal = self.store.repair(self.session_id)
        self.assertFalse(proposal["safe"])
        self.assertEqual(proposal["qasm"], self.session["qasm"])

    def test_agent_recognizes_all_project_action_kinds(self):
        self.assertEqual(self.store._requested_proposal_kind("帮我修复当前 QASM"), "qasm")
        self.assertIsNone(self.store._requested_proposal_kind("把目标改成 GHZ"))
        self.assertEqual(self.store._requested_proposal_kind("帮我选择后端"), "backend")
        self.assertIsNone(self.store._requested_proposal_kind("解释当前电路"))
        self.assertEqual(self.store._allowed_agent_tool_names("解释运行结果"), set())
        self.assertEqual(self.store._allowed_agent_tool_names("请帮我运行 32 shots"), {"run_experiment"})
        self.assertEqual(self.store._allowed_agent_tool_names("把目标改成 GHZ"), {"set_goal"})

    def test_stale_revision_cannot_overwrite_newer_edit(self):
        revision = self.session["circuit_revision"]
        current = self.store.advance(self.session_id, expected_revision=revision)
        with self.assertRaises(ConflictError):
            self.store.update_qasm(self.session_id, BELL_QASM, revision)
        self.assertEqual(self.store.get(self.session_id).circuit_revision, current["circuit_revision"])

    def test_backend_failure_is_non_blocking(self):
        def unavailable():
            raise RuntimeError("SDK missing")

        store = ExperimentStore(backend_probes={
            "spinq_taurus_simulator": unavailable,
            "originq_local_simulator": unavailable,
            "braket_local_simulator": unavailable,
        })
        session_id = store.create()["session_id"]
        value = store.recommendations(session_id)
        local = [item for item in value["items"] if item["available"]]
        remote = [item for item in value["items"] if not item["available"]]
        self.assertEqual([item["id"] for item in local], ["loomq_reference_simulator"])
        self.assertTrue(remote)
        self.assertTrue(any(item["recommended"] for item in local))
        self.assertTrue(all(item["reason"] for item in remote))
        selected = store.select_backend(session_id, "loomq_reference_simulator")
        self.assertEqual(selected["backend_selection"], "loomq_reference_simulator")
        with self.assertRaises(ValueError):
            store.select_backend(session_id, "braket_cloud")

    def test_each_connected_local_backend_is_selectable_and_executes(self):
        calls = []

        def probe():
            return object()

        def runner_for(backend_id):
            def execute(circuit, shots):
                calls.append((backend_id, circuit.qubit_count, shots))
                return {"00": shots}, backend_id + "-engine", backend_id + "-job", {"engine": backend_id}
            return execute

        backend_ids = (
            "spinq_taurus_simulator",
            "originq_local_simulator",
            "braket_local_simulator",
        )
        store = ExperimentStore(
            backend_probes={backend_id: probe for backend_id in backend_ids},
            backend_runners={backend_id: runner_for(backend_id) for backend_id in backend_ids},
        )
        session = store.create(mode="qasm", qasm=BELL_QASM + "measure q -> c;\n")
        recommendations = store.recommendations(session["session_id"])
        selectable = {item["id"] for item in recommendations["items"] if item["selectable"]}
        self.assertTrue(set(backend_ids).issubset(selectable))

        for backend_id in backend_ids:
            store.select_backend(session["session_id"], backend_id)
            result = store.run(session["session_id"], shots=16)["result"]
            self.assertEqual(result["backend_id"], backend_id)
            self.assertEqual(result["backend"], backend_id + "-engine")
            self.assertEqual(result["job_id"], backend_id + "-job")
            self.assertEqual(result["counts"], {"00": 16})
        self.assertEqual([item[0] for item in calls], list(backend_ids))

    def test_run_snapshot_is_immutable_after_edit(self):
        current = self.session
        for _ in range(7):
            current = self.store.advance(self.session_id, expected_revision=current["circuit_revision"])
        run_id = current["result"]["run_id"]
        original = json.loads(json.dumps(self.store.runs[run_id]))
        self.store.update_goal(self.session_id, "另一个目标")
        self.assertEqual(self.store.runs[run_id], original)

    def test_archived_hardware_replay_is_read_only_and_normalized(self):
        value = archived_hardware_evidence()
        self.assertTrue(value["archived"])
        self.assertTrue(value["complete"])
        self.assertFalse(value["live_submission"])
        self.assertEqual({item["id"] for item in value["circuits"]}, {"bell", "ghz3"})
        for circuit in value["circuits"]:
            self.assertEqual(circuit["series"][0]["provider"], "Ideal")
            for series in circuit["series"]:
                self.assertEqual(sum(series["counts"].values()), series["shots"])

    def test_natural_language_ghz_uses_local_validation(self):
        value = self.store.create("natural", goal="生成一个 3 比特 GHZ 态并全部测量")
        self.assertEqual(value["circuit_ir"]["qubits"], 3)
        self.assertEqual(value["state"], "runnable")
        self.assertIn("measure q -> c", value["qasm"])
        self.assertNotIn("goal", value["validation"])
        self.assertEqual(value["validation"]["measurements"]["status"], "pass")

    def test_unconfigured_agent_is_explicit_and_does_not_fake_a_reply(self):
        with mock.patch.dict("os.environ", {"LOOMQ_LLM_BASE_URL": "", "LOOMQ_LLM_API_KEY": "", "LOOMQ_LLM_MODEL": ""}):
            value = self.store.agent_turn(self.session_id, "解释当前电路")
        self.assertEqual(value["status"], "unavailable")
        self.assertEqual(value["source"], "none")
        self.assertIsNone(value["proposal"])
        self.assertIn("Agent 尚未配置", value["response"])

    def test_agent_qasm_proposal_is_validated_and_requires_confirmation(self):
        proposed = BELL_QASM + "h q[0];\ncx q[0],q[1];\nmeasure q -> c;\n"

        def transport(_messages):
            content = json.dumps({
                "understanding": "生成 Bell 电路",
                "response": "我准备了经过本地验证的电路，确认后才会应用。",
                "proposal": {"kind": "qasm", "qasm": proposed, "summary": "加入 H、CX 和测量"},
            }, ensure_ascii=False)
            return {"choices": [{"message": {"content": content}}]}

        store = ExperimentStore(agent_transport=transport)
        session = store.create()
        value = store.agent_turn(session["session_id"], "帮我生成 Bell 电路")
        self.assertEqual(value["status"], "ready")
        self.assertEqual(store.get(session["session_id"]).qasm, BELL_QASM)
        self.assertEqual(value["proposal"]["kind"], "qasm")
        self.assertTrue(value["proposal"]["safe_to_apply"])
        self.assertIn("+h q[0];", value["proposal"]["diff"])
        applied = store.apply_agent_proposal(session["session_id"], value["proposal"]["proposal_id"])
        self.assertEqual(applied["qasm"], proposed)
        self.assertTrue(applied["validation"]["runnable"])

    def test_agent_three_qubit_proposal_applies_as_dynamic_circuit(self):
        proposed = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[0],q[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
"""

        def transport(_messages):
            content = json.dumps({
                "understanding": "生成 GHZ 电路", "response": "请确认三比特电路。",
                "proposal": {"kind": "qasm", "qasm": proposed, "summary": "生成三比特 GHZ"},
            }, ensure_ascii=False)
            return {"choices": [{"message": {"content": content}}]}

        store = ExperimentStore(agent_transport=transport)
        session = store.create()
        value = store.agent_turn(session["session_id"], "生成三比特 GHZ 电路")
        applied = store.apply_agent_proposal(session["session_id"], value["proposal"]["proposal_id"])
        self.assertEqual(applied["circuit_ir"]["qubits"], 3)
        self.assertEqual(len(applied["circuit_ir"]["measurements"]), 3)

    def test_general_agent_answer_is_free_text_with_latest_workspace_snapshot(self):
        captured = []

        def transport(messages):
            captured.extend(messages)
            return {"choices": [{"message": {"content": "当前电路已有 H 和 CX；这是自由文本回答。"}}]}

        store = ExperimentStore(agent_transport=transport)
        session = store.create()
        session = store.advance(session["session_id"], expected_revision=session["circuit_revision"])
        session = store.advance(session["session_id"], expected_revision=session["circuit_revision"])
        session = store.advance(session["session_id"], expected_revision=session["circuit_revision"])
        value = store.agent_turn(session["session_id"], "解释当前电路")
        snapshot = captured[-2]["content"]
        self.assertIn("h q[0];", snapshot)
        self.assertIn("cx q[0],q[1];", snapshot)
        self.assertIn("通用自由文本问答", snapshot)
        self.assertIn("所选后端：loomq_reference_simulator", snapshot)
        self.assertIn("执行状态：", snapshot)
        self.assertIsNone(value["proposal"])
        self.assertEqual(value["response"], "当前电路已有 H 和 CX；这是自由文本回答。")
        self.assertIn("不要输出 JSON 包装", captured[0]["content"])

    def test_general_questions_share_one_path_and_receive_five_qubit_and_result_context(self):
        captured = []
        replies = iter(["这是五比特链式电路。", "Bell 电路通常由 H 和 CX 构成。"])

        def transport(messages):
            captured.append(messages)
            return {"choices": [{"message": {"content": next(replies)}}]}

        qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[5];
creg c[5];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
cx q[2],q[3];
cx q[3],q[4];
measure q -> c;
"""
        store = ExperimentStore(agent_transport=transport)
        session = store.create("qasm", qasm=qasm)
        store.run(session["session_id"], 32)
        explanation = store.agent_turn(session["session_id"], "解释运行结果")
        concept = store.agent_turn(session["session_id"], "Bell 电路是什么？")
        self.assertEqual(explanation["response"], "这是五比特链式电路。")
        self.assertEqual(concept["response"], "Bell 电路通常由 H 和 CX 构成。")
        for messages in captured:
            snapshot = messages[-2]["content"]
            self.assertIn("qreg q[5]", snapshot)
            self.assertIn("最近运行结果", snapshot)
            self.assertIn("backend_id", snapshot)
            self.assertIn("通用自由文本问答", snapshot)

    def test_agent_backend_request_receives_capabilities_and_can_propose(self):
        captured = []

        def transport(messages):
            captured.extend(messages)
            content = json.dumps({
                "understanding": "选择无需账号的本地后端", "response": "建议本地模拟器，请确认。",
                "proposal": {"kind": "backend", "backend_id": "loomq_reference_simulator", "summary": "Web 工作台实际连接的本地执行器"},
            }, ensure_ascii=False)
            return {"choices": [{"message": {"content": content}}]}

        store = ExperimentStore(agent_transport=transport)
        session = store.create()
        value = store.agent_turn(session["session_id"], "帮我选择一个无需账号的后端")
        self.assertIn("loomq_reference_simulator", captured[-2]["content"])
        self.assertEqual(value["proposal"]["kind"], "backend")
        applied = store.apply_agent_proposal(session["session_id"], value["proposal"]["proposal_id"])
        self.assertEqual(applied["backend_selection"], "loomq_reference_simulator")

    def test_agent_proposal_cannot_overwrite_newer_work(self):
        proposed = BELL_QASM + "h q[0];\ncx q[0],q[1];\nmeasure q -> c;\n"

        def transport(_messages):
            content = json.dumps({
                "understanding": "生成电路", "response": "请确认电路。",
                "proposal": {"kind": "qasm", "qasm": proposed, "summary": "生成 Bell 电路"},
            }, ensure_ascii=False)
            return {"choices": [{"message": {"content": content}}]}

        store = ExperimentStore(agent_transport=transport)
        session = store.create()
        value = store.agent_turn(session["session_id"], "生成 Bell 电路")
        store.update_qasm(session["session_id"], BELL_QASM + "x q[0];\n", session["circuit_revision"])
        with self.assertRaises(ConflictError):
            store.apply_agent_proposal(session["session_id"], value["proposal"]["proposal_id"])
        self.assertIn("x q[0]", store.get(session["session_id"]).qasm)

    def test_general_agent_can_run_with_a_model_tool_call(self):
        responses = iter([
            {"choices": [{"message": {"content": None, "tool_calls": [{"id": "call-run", "type": "function", "function": {"name": "run_experiment", "arguments": '{"shots":32}'}}]}}]},
            {"choices": [{"message": {"content": "已运行 32 shots，并将结果同步到工作台。"}}]},
        ])
        store = ExperimentStore(agent_transport=lambda _messages: next(responses))
        session = store.create("natural", goal="生成一个 3 比特 GHZ 态并全部测量")
        value = store.agent_turn(session["session_id"], "请帮我运行 32 shots")
        self.assertEqual(value["tools_used"], ["run_experiment"])
        self.assertEqual(value["session"]["result"]["shots"], 32)
        self.assertEqual(value["response"], "已运行 32 shots，并将结果同步到工作台。")

    def test_general_agent_can_set_goal_with_a_model_tool_call(self):
        responses = iter([
            {"choices": [{"message": {"content": None, "tool_calls": [{"id": "call-goal", "type": "function", "function": {"name": "set_goal", "arguments": '{"goal":"研究五比特链式纠缠"}'}}]}}]},
            {"choices": [{"message": {"content": "目标已更新。"}}]},
        ])
        store = ExperimentStore(agent_transport=lambda _messages: next(responses))
        session = store.create()
        value = store.agent_turn(session["session_id"], "把目标改成研究五比特链式纠缠")
        self.assertIsNone(value["proposal"])
        self.assertEqual(value["tools_used"], ["set_goal"])
        self.assertEqual(value["session"]["goal"], "研究五比特链式纠缠")


class ArchivedHardwareEvidenceSafetyTests(unittest.TestCase):
    @staticmethod
    def _payload(identity):
        support = ("00", "11") if identity["width"] == 2 else ("000", "111")
        payload = {
            "backend": identity["backend"],
            "job_id": identity["job_id"],
            "shots": identity["shots"],
            "counts": {
                support[0]: identity["shots"] // 2,
                support[1]: identity["shots"] - identity["shots"] // 2,
            },
            "bit_order": "little",
            "timestamp": "2026-08-15T00:00:00+00:00",
            "circuit": identity["circuit"],
            "meta": dict(identity["meta_identity"]),
        }
        if "mode" in identity:
            payload["mode"] = identity["mode"]
        return payload

    def _write_allowlisted(self, root, mutations=None):
        mutations = {} if mutations is None else mutations
        for key, identity in web_app.ARCHIVED_HARDWARE_SUMMARIES.items():
            payload = self._payload(identity)
            payload.update(mutations.get(key, {}))
            path = Path(root, key[0], identity["filename"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def _actual_series(value):
        return [
            item
            for circuit in value["circuits"]
            for item in circuit["series"]
            if item["kind"] == "archived_hardware"
        ]

    def test_only_the_four_allowlisted_formal_summaries_are_returned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_allowlisted(root)
            with mock.patch.object(web_app, "HARDWARE_EVIDENCE_ROOT", root):
                value = archived_hardware_evidence()

        actual = self._actual_series(value)
        self.assertEqual(4, len(actual))
        self.assertEqual({"SpinQ", "OriginQ"}, {item["provider"] for item in actual})
        self.assertEqual(
            {identity["job_id"] for identity in web_app.ARCHIVED_HARDWARE_SUMMARIES.values()},
            {item["job_id"] for item in actual},
        )
        self.assertEqual([], value["missing"])
        self.assertEqual([], value["rejected"])

    def test_larger_smoke_summary_is_never_scanned_or_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_allowlisted(root)
            fake = self._payload(web_app.ARCHIVED_HARDWARE_SUMMARIES[("spinq", "bell")])
            fake.update(
                {
                    "job_id": "forged-smoke-job",
                    "mode": "smoke",
                    "shots": 100000,
                    "counts": {"00": 50000, "11": 50000},
                }
            )
            fake_path = root / "spinq" / "spinq-smoke-bell-forged-summary.json"
            fake_path.write_text(json.dumps(fake), encoding="utf-8")
            with mock.patch.object(web_app, "HARDWARE_EVIDENCE_ROOT", root):
                value = archived_hardware_evidence()

        actual = self._actual_series(value)
        self.assertNotIn("forged-smoke-job", {item["job_id"] for item in actual})
        self.assertIn(
            "S-260811-0004", {item["job_id"] for item in actual}
        )

    def test_garbage_and_mixed_width_counts_are_rejected(self):
        invalid_counts = (
            {"00": 8191, "garbage": 1},
            {"00": 8191, "0": 1},
        )
        identity = web_app.ARCHIVED_HARDWARE_SUMMARIES[("spinq", "bell")]
        for counts in invalid_counts:
            with self.subTest(counts=counts), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._write_allowlisted(
                    root, {("spinq", "bell"): {"counts": counts}}
                )
                with mock.patch.object(web_app, "HARDWARE_EVIDENCE_ROOT", root):
                    value = archived_hardware_evidence()
            self.assertIn("spinq/bell", value["missing"])
            self.assertIn(identity["filename"], value["rejected"])
            self.assertFalse(value["complete"])
            self.assertNotIn(
                identity["job_id"],
                {item["job_id"] for item in self._actual_series(value)},
            )

    def test_allowlisted_path_still_rejects_smoke_or_forged_identity(self):
        cases = (
            (("spinq", "bell"), {"mode": "smoke"}),
            (("spinq", "bell"), {"job_id": "forged-job"}),
            (("originq", "bell"), {"mode": "smoke"}),
        )
        for key, mutation in cases:
            identity = web_app.ARCHIVED_HARDWARE_SUMMARIES[key]
            with self.subTest(key=key, mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._write_allowlisted(root, {key: mutation})
                with mock.patch.object(web_app, "HARDWARE_EVIDENCE_ROOT", root):
                    value = archived_hardware_evidence()
            self.assertIn("%s/%s" % key, value["missing"])
            self.assertIn(identity["filename"], value["rejected"])


class StaticExperienceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        static = STARTER / "web" / "static"
        cls.html = (static / "index.html").read_text(encoding="utf-8")
        cls.css = (static / "styles.css").read_text(encoding="utf-8")
        cls.js = (static / "app.js").read_text(encoding="utf-8")

    def test_accessible_landmarks_and_equivalents_are_present(self):
        for token in ('href="#main"', 'aria-live="polite"', 'role="img"', "测量结果数据表", 'role="tablist"', 'role="tabpanel"', "键盘帮助"):
            self.assertIn(token, self.html)
        self.assertIn(":focus-visible", self.css)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn("forced-colors", self.css)

    def test_scientific_boundary_and_local_identity_are_fixed_copy(self):
        self.assertIn("LoomQ 内置状态向量参考模拟器", self.html)
        app = (STARTER / "web" / "app.py").read_text(encoding="utf-8")
        self.assertIn("不是普通随机数", app)
        self.assertIn("不反映真机噪声", app)
        self.assertNotIn("Bell 态可写为", self.html)
        self.assertNotIn("goal_match", self.js)

    def test_single_route_and_revision_guard(self):
        self.assertNotIn("location.href", self.js)
        self.assertIn("circuit_revision", self.js)
        self.assertIn("sessionStorage", self.js)

    def test_focus_layout_is_one_screen_and_secondary_views_are_exclusive(self):
        self.assertIn("height: calc(100dvh - 48px)", self.css)
        self.assertIn("html, body { width: 100%; min-height: 100%; }", self.css)
        self.assertIn("body { margin: 0; min-width: 0; }", self.css)
        self.assertIn("@media (max-width: 1099px)", self.css)
        self.assertIn("grid-template-columns: 1fr 1fr", self.css)
        self.assertIn("selectEvidence", self.js)
        self.assertIn('id="dialog-dock"', self.html)
        self.assertNotIn("三级解释", self.html)
        self.assertNotIn("OpenQASM 2.0 ·", self.html)

    def test_reduced_motion_switch_has_visible_state_and_animation_target(self):
        self.assertIn('class="quiet motion-toggle preference-toggle"', self.html)
        self.assertIn('aria-pressed="false">减少动态：已关闭', self.html)
        self.assertIn('class="live-dot"', self.html)
        self.assertIn("@keyframes live-pulse", self.css)
        self.assertIn('.preference-toggle[aria-pressed="true"]', self.css)
        self.assertIn("body.reduce-motion .live-dot", self.css)
        self.assertIn("body.reduce-motion *, body.reduce-motion *::before, body.reduce-motion *::after { animation: none !important", self.css)
        self.assertNotIn("animation-duration: .01ms", self.css)
        self.assertIn('window.localStorage.setItem("loomq-reduce-motion"', self.js)
        self.assertIn('button.textContent = active ? "减少动态：已开启"', self.js)

    def test_default_and_color_accessible_themes_are_explicit_and_persistent(self):
        self.assertIn("--blue: #b9daf5", self.css)
        self.assertIn("--pink: #efbfd2", self.css)
        self.assertIn("body.color-accessible", self.css)
        self.assertIn("--blue: #0072b2", self.css)
        self.assertIn("--pink: #e69f00", self.css)
        self.assertIn('id="color-button"', self.html)
        self.assertIn('aria-pressed="false">色觉辅助：已关闭', self.html)
        self.assertIn('window.localStorage.setItem("loomq-color-accessible"', self.js)
        self.assertIn('document.body.classList.toggle("color-accessible", active)', self.js)

    def test_workbench_functions_are_not_locked_behind_tutorial_navigation(self):
        self.assertNotIn('class="path-tabs"', self.html)
        self.assertIn('id="stage-track" class="stage-track" aria-label="Bell 引导八个阶段" hidden', self.html)
        self.assertIn('id="tutorial-toggle"', self.html)
        self.assertIn('>填入本阶段指令</button>', self.html)
        self.assertIn('发送后才会推进实验', self.html)
        self.assertNotIn('执行本阶段操作', self.html + self.js)
        self.assertNotIn('/advance`,', self.js)
        self.assertIn('session.guide.preset_instruction', self.js)
        self.assertNotIn('prefillGuideInstruction();', self.js)
        self.assertIn("选择或比较后端", self.html)
        self.assertIn('id="validate-button"', self.html)
        self.assertIn('id="run-button"', self.html)
        self.assertIn('id="shots-input"', self.html)
        self.assertIn("setTutorial", self.js)

    def test_agent_is_always_available_as_a_visible_conversation_surface(self):
        self.assertIn('id="agent-form"', self.html)
        self.assertIn('id="agent-input"', self.html)
        self.assertIn('id="agent-conversation"', self.html)
        self.assertIn('id="agent-proposal"', self.html)
        self.assertIn('id="agent-proposal-safety"', self.html)
        self.assertIn("apply-agent-proposal", self.js)
        self.assertIn('$("#agent-apply").disabled = !safeToApply;', self.js)
        self.assertIn('$("#repair-diff").hidden = !state.repair.safe;', self.js)
        self.assertIn("Array.from({ length: qubitCount }", self.js)
        self.assertLess(self.js.index("renderAgentProposal(null);", self.js.index("apply-agent-proposal")), self.js.index("render(session);", self.js.index("apply-agent-proposal")))
        self.assertIn("思考中", self.js)
        self.assertNotIn('setAgentStatus("理解中")', self.js)
        self.assertIn("renderMarkdown(message.content)", self.js)
        self.assertIn("diff-${kind}", self.js)
        self.assertIn(".diff-add", self.css)
        self.assertIn("measurementLeft = 115 + ir.gates.length * 95 + 25", self.js)
        self.assertIn("minmax(0, 1fr) 284px", self.css)
        self.assertIn("progress-dots", self.css)
        self.assertIn('id="evidence-tab-hardware"', self.html)
        self.assertIn('id="hardware-evidence-circuits"', self.html)
        self.assertIn('fetch("/api/hardware-evidence")', self.js)
        self.assertIn("series.support_probability", self.js)


class HTTPContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), LoomQHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        encoded = None if body is None else json.dumps(body).encode("utf-8")
        headers = {} if encoded is None else {"Content-Type": "application/json", "Content-Length": str(len(encoded))}
        connection.request(method, path, body=encoded, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        content_type = response.getheader("Content-Type")
        connection.close()
        return response.status, content_type, payload

    def test_health_static_and_session_restore(self):
        status, content_type, payload = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        health = json.loads(payload)
        self.assertFalse(health["network_required"])
        self.assertEqual(set(health["l1_backends"]), {
            "spinq_taurus_simulator",
            "originq_local_simulator",
            "braket_local_simulator",
        })
        self.assertTrue(all("connected" in item for item in health["l1_backends"].values()))
        status, content_type, payload = self.request("GET", "/api/hardware-evidence")
        self.assertEqual(status, 200)
        evidence = json.loads(payload)
        self.assertTrue(evidence["archived"])
        self.assertFalse(evidence["live_submission"])
        status, content_type, payload = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("LoomQ".encode("utf-8"), payload)
        self.assertIn("Bell 实验".encode("utf-8"), payload)
        status, _, payload = self.request("POST", "/api/experiments", {"mode": "bell"})
        session = json.loads(payload)
        status, _, payload = self.request("GET", "/api/experiments/" + session["session_id"])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload)["session_id"], session["session_id"])

    def test_stale_http_update_returns_recovery_conflict(self):
        _, _, payload = self.request("POST", "/api/experiments", {"mode": "bell"})
        session = json.loads(payload)
        path = "/api/experiments/%s/advance" % session["session_id"]
        status, _, _ = self.request("POST", path, {"circuit_revision": session["circuit_revision"]})
        self.assertEqual(status, 200)
        status, _, payload = self.request("POST", path, {"circuit_revision": session["circuit_revision"]})
        self.assertEqual(status, 409)
        self.assertIn("recovery", json.loads(payload))

    def test_agent_http_fallback_is_not_reported_as_a_connected_model(self):
        _, _, payload = self.request("POST", "/api/experiments", {"mode": "bell"})
        session = json.loads(payload)
        path = "/api/experiments/%s/agent" % session["session_id"]
        environment = {
            "LOOMQ_LLM_BASE_URL": "", "LOOMQ_LLM_API_KEY": "",
            "LOOMQ_LLM_MODEL": "",
        }
        with mock.patch.dict("os.environ", environment, clear=True):
            status, _, payload = self.request("POST", path, {
                "prompt": session["guide"]["preset_instruction"],
            })
        value = json.loads(payload)
        self.assertEqual(status, 200)
        self.assertEqual(value["status"], "fallback")
        self.assertEqual(value["source"], "preset")
        self.assertIsNone(value["model"])
        self.assertIn("未调用模型", value["response"])


if __name__ == "__main__":
    unittest.main()
