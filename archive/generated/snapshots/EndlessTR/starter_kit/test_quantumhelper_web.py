import http.client
import json
import threading
import unittest
from unittest import mock

from starter_kit.quantumhelper_web import server as web


BELL_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;"""

GHZ_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[0],q[2];
measure q -> c;"""

GHZ5_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[5];
creg c[5];
h q[0];
cx q[0],q[1];
cx q[0],q[2];
cx q[0],q[3];
cx q[0],q[4];
measure q -> c;"""

NO_MEASUREMENT_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];"""

NON_GHZ_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[0];
measure q -> c;"""

GHZ4_NO_MEASUREMENT_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[4];
creg c[4];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
cx q[2],q[3];"""

GHZ6_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[6];
creg c[6];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
cx q[2],q[3];
cx q[3],q[4];
cx q[4],q[5];
measure q -> c;"""

INTERLEAVED_MEASUREMENT_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
measure q[0] -> c[0];
x q[0];"""

GHZ4_SMALL_CREG_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[4];
creg c[1];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
cx q[2],q[3];"""


class QuantumHelperAgentWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = web.ThreadingHTTPServer(("127.0.0.1", 0), web.QuantumHelperHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, payload=None, extra_headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if body else {}
        headers.update(extra_headers or {})
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read()
        content_type = response.getheader("Content-Type", "")
        connection.close()
        if "application/json" in content_type:
            return response.status, json.loads(data.decode("utf-8"))
        return response.status, data.decode("utf-8")

    def test_agent_page_is_part_of_static_submission(self):
        status, html = self.request("GET", "/agent.html")
        self.assertEqual(status, 200)
        self.assertIn("adapter.agent_chat()", html)
        self.assertIn("app.js?v=20260820-1", html)

    def test_home_does_not_load_app_script_twice(self):
        status, html = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(len(web.re.findall(r'<script[^>]+src="[^"]*app\.js', html)), 1)
        self.assertRegex(html, r'src="workspace-state\.js(?:\?[^\"]+)?"')

    def test_chat_qasm_is_revalidated_for_l1(self):
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat", return_value=BELL_QASM
        ):
            status, payload = self.request("POST", "/api/chat", {"prompt": "生成 Bell 态"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "qasm")
        self.assertEqual(payload["summary"]["qubits"], 2)
        self.assertTrue(payload["summary"]["has_measurement"])
        self.assertEqual(payload["summary"]["operation_count"], 4)
        self.assertEqual(payload["kind"], "qasm")
        self.assertEqual(payload["qasm"], BELL_QASM)

    def test_case1_four_qubit_ghz_partial_measurement_is_data_driven(self):
        prompt = "生成一个 4 比特 GHZ 态，只测量前两个量子比特"
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat", return_value=GHZ4_NO_MEASUREMENT_QASM
        ) as agent_chat:
            status, payload = self.request("POST", "/api/chat", {"prompt": prompt})

        self.assertEqual(status, 200)
        self.assertNotIn("unsupported", json.dumps(payload).lower())
        agent_chat.assert_called_once_with("生成一个 4 比特 GHZ 态，且不要测量")
        self.assertEqual(payload["circuit"]["qubits"], 4)
        operations = payload["circuit"]["operations"]
        self.assertEqual([item["name"] for item in operations[:4]], ["h", "cx", "cx", "cx"])
        measurements = [item for item in operations if item["type"] == "measurement"]
        self.assertEqual([(item["qubits"][0], item["clbits"][0]) for item in measurements], [(0, 0), (1, 1)])
        self.assertIn("measure q[0] -> c[0];", payload["qasm"])
        self.assertIn("measure q[1] -> c[1];", payload["qasm"])
        self.assertNotIn("measure q[2]", payload["qasm"])
        self.assertEqual(payload["task"]["measurement"]["mode"], "partial")
        self.assertIn("q[0] → c[0]", payload["explanation_steps"][-1]["explanation"])
        self.assertIn("q[1] → c[1]", payload["explanation_steps"][-1]["explanation"])
        self.assertTrue(payload["validation"]["valid"])

    def test_case2_six_qubit_ghz_full_measurement(self):
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat", return_value=GHZ6_QASM
        ):
            status, payload = self.request(
                "POST", "/api/chat", {"prompt": "生成一个 6 比特 GHZ 态并全部测量"}
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["circuit"]["qubits"], 6)
        operations = payload["circuit"]["operations"]
        self.assertEqual([item["name"] for item in operations[:6]], ["h"] + ["cx"] * 5)
        self.assertEqual(sum(item["type"] == "measurement" for item in operations), 6)
        self.assertEqual(payload["task"]["measurement"], "all")
        self.assertEqual(len(payload["explanation_steps"][-1]["operation_ids"]), 6)
        self.assertTrue(payload["validation"]["valid"])

    def test_case3_bell_followup_changes_only_measurement_without_agent(self):
        request = {
            "prompt": "只测量第一个量子比特",
            "context": {
                "current_qasm": BELL_QASM,
                "task": {"goal": "Bell State", "qubits": 2, "measurement": "all"},
            },
        }
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "0"}), mock.patch.object(
            web.adapter, "agent_chat"
        ) as agent_chat:
            status, payload = self.request("POST", "/api/chat", request)

        self.assertEqual(status, 200)
        agent_chat.assert_not_called()
        self.assertEqual(payload["intent"], "modify_current_task")
        operations = payload["circuit"]["operations"]
        self.assertEqual([item["name"] for item in operations[:2]], ["h", "cx"])
        measurements = [item for item in operations if item["type"] == "measurement"]
        self.assertEqual([(item["qubits"][0], item["clbits"][0]) for item in measurements], [(0, 0)])
        self.assertIn("measure q[0] -> c[0];", payload["qasm"])
        self.assertNotIn("measure q[1]", payload["qasm"])
        self.assertEqual(payload["task"]["measurement"]["mode"], "partial")
        self.assertIn("q[0] → c[0]", payload["explanation_steps"][-1]["explanation"])
        self.assertTrue(payload["validation"]["valid"])

    def test_measurement_followup_rejects_interleaved_measurement_without_rewrite(self):
        request = {
            "prompt": "只测量第一个量子比特",
            "context": {"current_qasm": INTERLEAVED_MEASUREMENT_QASM},
        }
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "0"}), mock.patch.object(
            web.adapter, "agent_chat"
        ) as agent_chat:
            status, payload = self.request("POST", "/api/chat", request)

        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "INVALID_INPUT")
        self.assertIn("测量后仍包含量子门", payload["error"])
        self.assertNotIn("qasm", payload)
        agent_chat.assert_not_called()

    def test_partial_measurement_expands_small_classical_register(self):
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat", return_value=GHZ4_SMALL_CREG_QASM
        ):
            status, payload = self.request(
                "POST", "/api/chat",
                {"prompt": "生成一个 4 比特 GHZ 态，只测量前两个量子比特"},
            )

        self.assertEqual(status, 200)
        self.assertIn("creg c[2];", payload["qasm"])
        parsed = web.adapter.parse_qasm(payload["qasm"])
        self.assertEqual(parsed.c_num, 2)
        for target in web.ALLOWED_TARGETS:
            self.assertTrue(web.adapter.transpile(payload["qasm"], target))

    def test_measurement_followups_work_locally_for_none_and_all(self):
        context = {
            "current_qasm": BELL_QASM,
            "task": {"goal": "Bell State", "qubits": 2, "measurement": "all"},
        }
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "0"}), mock.patch.object(
            web.adapter, "agent_chat"
        ) as agent_chat:
            none_status, none_payload = self.request(
                "POST", "/api/chat", {"prompt": "改成不要测量", "context": context}
            )
            all_status, all_payload = self.request(
                "POST", "/api/chat", {"prompt": "改成全部测量", "context": context}
            )

        self.assertEqual(none_status, 200)
        self.assertEqual(none_payload["task"]["measurement"], "none")
        self.assertFalse(none_payload["summary"]["has_measurement"])
        self.assertEqual(all_status, 200)
        self.assertEqual(all_payload["task"]["measurement"], "all")
        self.assertEqual(all_payload["summary"]["measurement_count"], 2)
        agent_chat.assert_not_called()

    def test_unresolved_measurement_followup_returns_invalid_input_not_500(self):
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "0"}), mock.patch.object(
            web.adapter, "agent_chat"
        ) as agent_chat:
            status, payload = self.request(
                "POST", "/api/chat",
                {"prompt": "只测量奇数位", "context": {"current_qasm": BELL_QASM}},
            )

        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "INVALID_INPUT")
        self.assertIn("无法确定要测量哪些量子比特", payload["error"])
        agent_chat.assert_not_called()

    def test_malformed_partial_measurement_context_is_rejected(self):
        malformed = {
            "mode": "partial",
            "pairs": [{"qubit": 0, "classical_bit": "zero"}],
        }
        with mock.patch.object(web.adapter, "agent_chat") as agent_chat:
            status, payload = self.request(
                "POST", "/api/chat",
                {
                    "prompt": "继续",
                    "context": {
                        "current_qasm": BELL_QASM,
                        "task": {"goal": "Bell State", "qubits": 2, "measurement": malformed},
                    },
                },
            )

        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "INVALID_INPUT")
        self.assertIn("下标必须是非负整数", payload["error"])
        agent_chat.assert_not_called()

    def test_chat_qasm_echoes_workspace_metadata_and_serializes_real_ghz(self):
        request = {
            "prompt": "生成一个 3 比特 GHZ 态并进行全测量",
            "schema_version": "1.0",
            "request_id": "request-7",
            "session_id": "session-3",
            "task_id": "task-ghz",
            "base_revision": 2,
            "context": {
                "current_qasm": BELL_QASM,
                "task": {"goal": "Bell State", "qubits": 2, "measurement": "all"},
            },
        }
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat", return_value=GHZ_QASM
        ):
            status, payload = self.request("POST", "/api/chat", request)

        self.assertEqual(status, 200)
        for key in ("schema_version", "request_id", "session_id", "task_id", "base_revision"):
            self.assertEqual(payload[key], request[key])
        self.assertEqual(payload["intent"], "generate_circuit")
        self.assertEqual(payload["task"]["qubits"], 3)
        self.assertEqual(payload["summary"]["operation_count"], 6)
        self.assertTrue(payload["validation"]["valid"])
        self.assertEqual(
            payload["validation"]["source"], "adapter.parse_qasm+transpile"
        )
        self.assertEqual(set(payload["transpiled"]), web.ALLOWED_TARGETS)
        self.assertTrue(payload["transpiled"]["spinq"].startswith("OPENQASM 2.0;"))
        self.assertTrue(payload["transpiled"]["originq"].startswith("QINIT 3"))
        self.assertTrue(payload["transpiled"]["braket"].startswith("OPENQASM 3.0;"))

        operations = payload["circuit"]["operations"]
        self.assertEqual([item["id"] for item in operations], [f"op-{i}" for i in range(6)])
        self.assertEqual([item["name"] for item in operations[:3]], ["h", "cx", "cx"])
        self.assertTrue(all(item["type"] == "measurement" for item in operations[3:]))
        operation_ids = {item["id"] for item in operations}
        explained_ids = {
            operation_id
            for step in payload["explanation_steps"]
            for operation_id in step["operation_ids"]
        }
        self.assertEqual(explained_ids, operation_ids)

    def test_chat_backend_returns_official_metadata(self):
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat", return_value="braket_local_simulator"
        ):
            status, payload = self.request("POST", "/api/chat", {"prompt": "选择零排队后端"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "backend")
        self.assertEqual(payload["adapter_target"], "braket")
        self.assertEqual(payload["backend"]["queue"], "none")

    def test_chat_repair_returns_staged_proposal_with_provable_issues(self):
        prompt = "请修复这段代码：\n```qasm\nH q[0];\nCX q[0] q[1]\n```"
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat", return_value=BELL_QASM
        ):
            status, payload = self.request(
                "POST", "/api/chat", {"prompt": prompt, "intent": "repair"}
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "repair_circuit")
        self.assertEqual(payload["qasm"], BELL_QASM)
        proposal = payload["repair"]
        self.assertEqual(proposal["status"], "awaiting_apply")
        self.assertIn("CX q[0] q[1]", proposal["before"])
        self.assertEqual(proposal["proposed_qasm"], BELL_QASM)
        codes = {issue["code"] for issue in proposal["issues"]}
        self.assertIn("MISSING_HEADER", codes)
        self.assertIn("MISSING_COMMA", codes)
        self.assertIn("MISSING_SEMICOLON", codes)
        self.assertTrue(payload["validation"]["valid"])

    def test_chat_backend_explains_full_canonical_match(self):
        prompt = "我需要运行一个 15 比特电路，要求零排队并且免费"
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat", return_value="originq_local_simulator"
        ):
            status, payload = self.request("POST", "/api/chat", {"prompt": prompt})

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "backend")
        # 硬约束模型(任务书 §11)：嵌套 hard_constraints，free/zero_queue 是布尔。
        self.assertEqual(payload["backend_requirements"]["hard_constraints"]["min_qubits"], 15)
        self.assertEqual(payload["backend_requirements"]["hard_constraints"]["free"], True)
        self.assertEqual(payload["backend_requirements"]["hard_constraints"]["zero_queue"], True)
        self.assertEqual(payload["match_status"], "full")
        self.assertEqual(payload["unmet_requirements"], [])
        self.assertEqual(len(payload["matched_reasons"]), 3)
        self.assertTrue(payload["runnable_locally"])
        self.assertIn(payload["adapter_target"], web.ALLOWED_TARGETS)

    def test_chat_qpu_recommendation_is_not_locally_runnable(self):
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat", return_value="originq_wukong"
        ):
            status, payload = self.request(
                "POST", "/api/chat", {"prompt": "请选择本源悟空真机"}
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "backend")
        # 真机请求的精确匹配必须是 qpu（真机），且不可本地运行。
        self.assertEqual(payload["backend"]["kind"], "qpu")
        self.assertFalse(payload["runnable_locally"])
        self.assertIsNone(payload["adapter_target"])
        self.assertEqual(payload["match_status"], "full")

    def test_chat_backend_negated_preferences_are_not_claimed_as_full_match(self):
        prompt = "免费不是必须，零排队也可选，请推荐一个后端"
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat", return_value="originq_local_simulator"
        ):
            status, payload = self.request("POST", "/api/chat", {"prompt": prompt})

        self.assertEqual(status, 200)
        # 否定偏好是「明确不要求」，区别于「未指定」；两者都不是硬约束。
        self.assertFalse(payload["backend_requirements"]["hard_constraints"]["free"])
        self.assertFalse(payload["backend_requirements"]["hard_constraints"]["zero_queue"])
        self.assertEqual(payload["match_status"], "full")
        self.assertEqual(payload["matched_reasons"], [])

    def test_scenario_measurement_card_returns_runnable_circuit(self):
        # 任务书 §9.3/§37: 测量卡必须进入真实可运行流程，而不是解释模式或报错。
        status, payload = self.request("POST", "/api/chat", {
            "prompt": "重复运行同一条两比特线路，观察不同测量结果出现的次数和分布。",
            "scenario_id": "measurement",
        })
        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "qasm")
        self.assertEqual(payload["intent"], "generate_circuit")
        self.assertEqual(payload["scenario_id"], "measurement")
        self.assertTrue(payload["validation"]["valid"])

    def test_scenario_search_card_returns_concept_explanation_only(self):
        # 第三轮 §28/§30/§31: 查找（Grover）未实现时，查找卡进入概念解释模式，
        # 不生成演示线路、不假装支持；如实说明还缺什么信息。
        status, payload = self.request("POST", "/api/chat", {
            "prompt": "我有 8 个候选编号，其中只有一个满足条件，希望找到它。",
            "scenario_id": "search",
        })
        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "scenario")
        self.assertEqual(payload["intent"], "scenario_help")
        self.assertIs(payload["direct_generation_supported"], False)
        self.assertIn("不宣称已经实现通用 Grover", payload["answer"])

    def test_scenario_correlation_card_returns_runnable_bell(self):
        # 任务书 §9.4/§37: 关联卡必须进入 Bell 示例流程。
        status, payload = self.request("POST", "/api/chat", {
            "prompt": "生成并运行一个 Bell 实验，看看两个量子比特怎样产生关联。",
            "scenario_id": "correlation",
        })
        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "qasm")
        self.assertEqual(payload["intent"], "generate_circuit")
        self.assertIn("cx q[0],q[1]", payload["qasm"])

    def test_chat_backend_no_exact_match_lists_alternatives(self):
        # 任务书 §12/§35: 真机+免费+零排队+无需账号 必然无精确匹配，不得把模拟器
        # 标成完全满足，且必须返回带牺牲条件标注的 alternatives（HTTP 层覆盖）。
        status, payload = self.request("POST", "/api/chat", {
            "prompt": "我要真机、免费、零排队、无需账号",
        })
        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "backend")
        self.assertEqual(payload["match_status"], "no_exact_match")
        self.assertTrue(any("不是真机" in u for u in payload["unmet_requirements"]))
        self.assertTrue(payload["alternatives"])
        for alt in payload["alternatives"]:
            self.assertTrue(alt["unmet"], "每个备选都必须标注牺牲的条件")
        self.assertIn("没有", payload["conflict_explanation"])

    def test_diagnose_locate_missing_semicolon(self):
        # 第二轮 §7/§16 Test 4：定位缺分号，而不是解释 CX 门。
        issues = web._diagnose_qasm_issues("h q[0] cx q[0],q[1];")
        self.assertTrue(any(i["code"] == "MISSING_SEMICOLON" for i in issues))

    def test_diagnose_out_of_range_qubit(self):
        issues = web._diagnose_qasm_issues("qreg q[2];\ncx q[0], q[2];")
        self.assertTrue(any(i["code"] == "QUBIT_OUT_OF_RANGE" for i in issues))

    def test_diagnostics_carry_severity_and_line(self):
        # 第三轮 §24：diagnostic 必须带 severity，能定位到行就带 line。
        issues = web._diagnose_qasm_issues("qreg q[2];\ncx q[0], q[2];")
        out_of_range = next(i for i in issues if i["code"] == "QUBIT_OUT_OF_RANGE")
        self.assertEqual(out_of_range["severity"], "error")
        self.assertEqual(out_of_range["line"], 2)

    def test_repair_options_not_auto_resolved(self):
        # 第三轮 §25/§26：越界有两种合理修法，不擅自决定，给出选项让用户选。
        issues = web._diagnose_qasm_issues("qreg q[2];\ncx q[0], q[2];")
        options = web._repair_options_for_issues("qreg q[2];\ncx q[0], q[2];", issues)
        labels = [o["label"] for o in options]
        self.assertTrue(any("改成 q[1]" in label for label in labels))
        self.assertTrue(any("扩成 q[3]" in label for label in labels))

    def test_modify_response_includes_action_metadata(self):
        # 第二轮 §6/§16 Test 7：修改响应带结构化 action，前端据此高亮面板。
        request = {"prompt": "只测量第一个量子比特", "context": {"current_qasm": BELL_QASM}}
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "0"}), mock.patch.object(
            web.adapter, "agent_chat"
        ) as agent_chat:
            status, payload = self.request("POST", "/api/chat", request)

        self.assertEqual(status, 200)
        agent_chat.assert_not_called()
        self.assertIsNotNone(payload.get("action"))
        self.assertEqual(payload["action"]["type"], "update_task")
        self.assertIn("current_task", payload["action"]["updated_panels"])
        self.assertIn("circuit", payload["action"]["updated_panels"])
        self.assertIn("validation", payload["action"]["updated_panels"])

    def test_chat_is_explicitly_disabled_without_opt_in(self):
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "0"}):
            status, payload = self.request("POST", "/api/chat", {"prompt": "生成 Bell 态"})
        self.assertEqual(status, 503)
        self.assertEqual(payload["code"], "LLM_DISABLED")

    def test_check_returns_validated_summary_and_operation_count(self):
        status, payload = self.request("POST", "/api/check", {"qasm": BELL_QASM})

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"]["qubits"], 2)
        self.assertEqual(payload["summary"]["gate_count"], 2)
        self.assertEqual(payload["summary"]["measurement_count"], 2)
        self.assertEqual(payload["summary"]["operation_count"], 4)
        self.assertTrue(payload["summary"]["has_measurement"])
        self.assertEqual(set(payload["transpiled"]), web.ALLOWED_TARGETS)
        self.assertTrue(payload["transpiled"]["spinq"].startswith("OPENQASM 2.0;"))
        self.assertIn("measure q[1] -> c[1];", payload["transpiled"]["spinq"])
        self.assertIn("CNOT q[0],q[1]", payload["transpiled"]["originq"])
        self.assertIn("cnot q[0],q[1];", payload["transpiled"]["braket"])

    def test_workspace_code_panels_opt_out_of_browser_translation(self):
        html = (web.STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertRegex(
            html,
            r'<pre[^>]+class="[^"]*notranslate[^"]*"[^>]+id="qasmCode"[^>]+translate="no"',
        )
        self.assertRegex(
            html,
            r'<pre[^>]+class="[^"]*notranslate[^"]*"[^>]+id="adapterCode"[^>]+translate="no"',
        )

    def test_workspace_renderer_receives_dispatch_without_closing_over_store(self):
        script = (web.STATIC_ROOT / "app.js").read_text(encoding="utf-8")
        renderer_start = script.index("function renderWorkspace")
        renderer_end = script.index("function setupHome", renderer_start)
        renderer = script[renderer_start:renderer_end]
        self.assertIn("function renderWorkspace(state, dispatchAction, normalizeCounts)", renderer)
        self.assertIn("dispatchAction({type: 'SELECT_EXECUTION_TARGET'", renderer)
        self.assertNotIn("store.dispatch", renderer)
        self.assertNotIn("stateApi.", renderer)

    def test_workspace_explains_measurement_is_optional_but_required_for_visualization(self):
        html = (web.STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        script = (web.STATIC_ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("电路不要求必须包含测量", html)
        self.assertIn("只有加入测量操作后", html)
        self.assertIn('id="resultEmptyState"', html)
        self.assertIn("function circuitHasMeasurement(state)", script)
        self.assertIn("runButton.disabled = busy || !hasMeasurement", script)

    def test_check_accepts_no_measurement_but_run_rejects_it_without_result(self):
        check_status, checked = self.request(
            "POST", "/api/check", {"qasm": NO_MEASUREMENT_QASM}
        )
        self.assertEqual(check_status, 200)
        self.assertFalse(checked["summary"]["has_measurement"])
        self.assertEqual(checked["summary"]["operation_count"], 1)

        with mock.patch.object(web.adapter, "run") as adapter_run:
            run_status, failed = self.request(
                "POST", "/api/run",
                {"qasm": NO_MEASUREMENT_QASM, "target": "spinq", "shots": 16},
            )
        self.assertEqual(run_status, 400)
        self.assertFalse(failed["ok"])
        self.assertEqual(failed["code"], "INVALID_INPUT")
        self.assertNotIn("result", failed)
        adapter_run.assert_not_called()

    def test_run_accepts_shots_boundaries_and_returns_only_adapter_result(self):
        for shots in (1, web.MAX_SHOTS):
            adapter_result = {
                "counts": {"00": shots},
                "shots": shots,
                "backend": "spinq",
                "bit_order": "q[1]q[0]",
            }
            with self.subTest(shots=shots), mock.patch.object(
                web.adapter, "run", return_value=adapter_result
            ) as adapter_run:
                status, payload = self.request(
                    "POST", "/api/run",
                    {"qasm": BELL_QASM, "target": "spinq", "shots": shots},
                )
                self.assertEqual(status, 200)
                self.assertEqual(payload["result"], adapter_result)
                self.assertEqual(payload["summary"]["operation_count"], 4)
                adapter_run.assert_called_once_with(BELL_QASM, "spinq", shots)

    def test_run_rejects_invalid_shots_and_target_without_fake_result(self):
        invalid_requests = (
            {"qasm": BELL_QASM, "target": "spinq", "shots": 0},
            {"qasm": BELL_QASM, "target": "spinq", "shots": web.MAX_SHOTS + 1},
            {"qasm": BELL_QASM, "target": "spinq", "shots": True},
            {"qasm": BELL_QASM, "target": "unknown", "shots": 16},
        )
        with mock.patch.object(web.adapter, "run") as adapter_run:
            for request in invalid_requests:
                with self.subTest(request=request):
                    status, payload = self.request("POST", "/api/run", request)
                    self.assertEqual(status, 400)
                    self.assertFalse(payload["ok"])
                    self.assertEqual(payload["code"], "INVALID_INPUT")
                    self.assertNotIn("result", payload)
        adapter_run.assert_not_called()

    def test_chat_modifies_validated_ghz_context_with_grounded_prompt(self):
        request = {
            "prompt": "改成5比特",
            "request_id": "modify-1",
            "task_id": "ghz-task",
            "base_revision": 4,
            "context": {
                "current_qasm": GHZ_QASM,
                "task": {"type": "generate_circuit", "goal": "GHZ State", "qubits": 3, "measurement": "all"},
            },
        }
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat", return_value=GHZ5_QASM
        ) as agent_chat:
            status, payload = self.request("POST", "/api/chat", request)

        self.assertEqual(status, 200)
        agent_chat.assert_called_once_with("生成一个 5 比特 GHZ 态并进行全测量")
        self.assertEqual(payload["intent"], "modify_current_task")
        self.assertEqual(payload["task"]["qubits"], 5)
        self.assertEqual(payload["circuit"]["qubits"], 5)
        measurements = [
            item for item in payload["circuit"]["operations"]
            if item["type"] == "measurement"
        ]
        self.assertEqual(len(measurements), 5)
        self.assertTrue(payload["validation"]["valid"])
        self.assertEqual(payload["request_id"], "modify-1")
        self.assertEqual(payload["task_id"], "ghz-task")
        self.assertEqual(payload["base_revision"], 4)

    def test_chat_does_not_trust_fake_ghz_task_for_modify(self):
        request = {
            "prompt": "改成5比特",
            "context": {
                "current_qasm": NON_GHZ_QASM,
                "task": {"goal": "GHZ State", "qubits": 2, "measurement": "all"},
            },
        }
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat"
        ) as agent_chat:
            status, payload = self.request("POST", "/api/chat", request)

        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "INVALID_INPUT")
        self.assertIn("不是 canonical GHZ", payload["error"])
        agent_chat.assert_not_called()

    def test_chat_edit_current_qasm_preserves_current_task(self):
        # Regression: edit_current_qasm used to omit "task" from its response,
        # which made the frontend treat it as a fresh generation and wipe the
        # Current Task panel for a pure textual edit (原则1:
        # Task modification != QASM text editing).
        request = {
            "prompt": "把最后一行改成 measure q -> c;",
            "context": {
                "current_qasm": GHZ_QASM,
                "task": {"goal": "GHZ State", "qubits": 3, "measurement": "all"},
            },
        }

        def fake_classify(content):
            return {"choices": [{"message": {"content": (
                '{"intent":"edit_current_qasm","confidence":0.9,'
                '"requires_clarification":false,"reason":"mock"}'
            )}}]}

        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.web_agent, "classify_by_llm",
            side_effect=lambda prompt, context, completion=None: web.web_agent._route_from_llm_payload(
                fake_classify(prompt)
            ),
        ):
            status, payload = self.request("POST", "/api/chat", request)

        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "edit_current_qasm")
        self.assertEqual(payload["task"], {"goal": "GHZ State", "qubits": 3, "measurement": "all"})

    def test_chat_explains_real_h_operation_without_calling_agent(self):
        request = {
            "prompt": "为什么这里需要 H 门？",
            "request_id": "explain-1",
            "base_revision": 3,
            "context": {
                "current_qasm": GHZ_QASM,
                "task": {"goal": "GHZ State", "qubits": 3, "measurement": "all"},
            },
        }
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "0"}), mock.patch.object(
            web.adapter, "agent_chat"
        ) as agent_chat:
            status, payload = self.request("POST", "/api/chat", request)

        self.assertEqual(status, 200)
        agent_chat.assert_not_called()
        self.assertEqual(payload["kind"], "explanation")
        self.assertEqual(payload["intent"], "explain_circuit")
        self.assertIn("H 门", payload["assistant_message"])
        self.assertEqual(payload["related_operation_ids"], ["op-0"])
        self.assertNotIn("qasm", payload)
        self.assertEqual(payload["base_revision"], 3)

    def test_chat_rejects_invalid_or_oversized_context(self):
        contexts = (
            {"unexpected": "field"},
            {"current_qasm": "x" * 16_001},
            {"current_qasm": "not valid qasm"},
        )
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat"
        ) as agent_chat:
            for context in contexts:
                with self.subTest(context=list(context)):
                    status, payload = self.request(
                        "POST", "/api/chat", {"prompt": "继续", "context": context}
                    )
                    self.assertEqual(status, 400)
                    self.assertEqual(payload["code"], "INVALID_INPUT")
        agent_chat.assert_not_called()

    def test_chat_text_response_echoes_workspace_metadata(self):
        # 任务书 §27: a vague request now produces a friendly clarification
        # ("clarify") instead of a hard-to-render free-text reply.  The
        # workspace metadata echo is unchanged.
        request = {
            "prompt": "请说明还需要哪些信息",
            "schema_version": "1.0",
            "request_id": "text-request",
            "session_id": "text-session",
            "task_id": "text-task",
            "base_revision": 6,
        }
        with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "1"}), mock.patch.object(
            web.adapter, "agent_chat", return_value="请补充量子比特数量。"
        ):
            status, payload = self.request("POST", "/api/chat", request)

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "clarify")
        self.assertEqual(payload["intent"], "unknown")
        for key in ("schema_version", "request_id", "session_id", "task_id", "base_revision"):
            self.assertEqual(payload[key], request[key])

    def test_runtime_config_save_drives_real_adapter_call_without_env_mutation(self):
        cfg = web.runtime_config.get_runtime_config()
        cfg.clear()
        seen = {}

        def fake_agent_chat(_prompt):
            from starter_kit import llm_client  # noqa: PLC0415

            base, key, model, _timeout, _max_output = llm_client._configuration()
            seen.update(base=base, key=key, model=model)
            return BELL_QASM

        try:
            with mock.patch.dict(web.os.environ, {"QUANTUMHELPER_ENABLE_LLM": "0"}), \
                    mock.patch.object(web.adapter, "agent_chat", side_effect=fake_agent_chat):
                status, saved = self.request("POST", "/api/config", {
                    "base_url": "https://runtime.example.com/v1/",
                    "api_key": "runtime-secret",
                    "model": "runtime-model",
                })
                self.assertEqual(status, 200)
                self.assertNotIn("runtime-secret", repr(saved))

                status, config_status = self.request("GET", "/api/config/status")
                self.assertEqual(status, 200)
                self.assertTrue(config_status["config"]["available"])

                status, payload = self.request(
                    "POST", "/api/chat", {"prompt": "生成一个 Bell 态并全部测量"}
                )
        finally:
            cfg.clear()

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "qasm")
        self.assertEqual(seen, {
            "base": "https://runtime.example.com/v1",
            "key": "runtime-secret",
            "model": "runtime-model",
        })

    def test_runtime_config_supports_positional_classifier_completion(self):
        cfg = web.runtime_config.get_runtime_config()
        cfg.clear()
        cfg.set("https://runtime.example.com/v1", "runtime-secret", "runtime-model")
        classifier_payload = {
            "choices": [{"message": {"content": json.dumps({
                "intent": "unknown",
                "confidence": 0.4,
                "requires_clarification": True,
                "reason": "信息不足",
            })}}]
        }
        try:
            with mock.patch.object(
                web.web_agent, "_chat_completion", return_value=mock.Mock(return_value=classifier_payload)
            ):
                status, payload = self.request(
                    "POST", "/api/chat", {"prompt": "请帮我看看这个"}
                )
        finally:
            cfg.clear()

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "clarify")

    def test_model_configuration_management_is_loopback_only(self):
        self.assertTrue(web._local_config_client("127.0.0.1"))
        self.assertTrue(web._local_config_client("::1"))
        self.assertFalse(web._local_config_client("192.168.1.10"))
        self.assertFalse(web._local_config_client("not-an-address"))

        self.assertTrue(web._local_config_host("localhost:8000"))
        self.assertTrue(web._local_config_host("127.0.0.1:8000"))
        self.assertTrue(web._local_config_host("[::1]:8000"))
        self.assertFalse(web._local_config_host("attacker.example:8000"))
        self.assertFalse(web._local_config_host("attacker@localhost:8000"))
        self.assertFalse(web._local_config_host("localhost/path"))
        self.assertFalse(web._local_config_host("localhost:99999"))
        self.assertFalse(web._local_config_host(""))
        self.assertTrue(web._local_config_request("127.0.0.1", "localhost:8000"))
        self.assertFalse(
            web._local_config_request("127.0.0.1", "attacker.example:8000")
        )
        self.assertFalse(
            web._local_config_request("192.168.1.10", "localhost:8000")
        )

        status, payload = self.request(
            "GET",
            "/api/config/status",
            extra_headers={"Host": "attacker.example:8000"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(payload["code"], "LOCAL_ONLY")

    def test_unrelated_qa_sequence_is_not_hijacked_by_current_h_gate(self):
        cfg = web.runtime_config.get_runtime_config()
        cfg.clear()
        cfg.set("https://runtime.example.com/v1", "runtime-secret", "runtime-model")
        context = {
            "current_qasm": BELL_QASM,
            "task": {"goal": "Bell 态", "qubits": 2, "measurement": "all"},
        }

        def completion(messages):
            request = json.loads(messages[-1]["content"])
            question_type = request["question_type"]
            answers = {
                "result_pattern": "Bell 态的两个比特相互关联，因此主要得到 00 和 11。",
                "shots_explanation": "shots 是重复执行次数；单次只有一个结果，多次才能估计概率。",
                "backend_explanation": "模拟器计算理想结果，真机会包含真实硬件噪声。",
            }
            return {"choices": [{"message": {"content": answers[question_type]}}]}

        prompts = (
            ("为什么 Bell 态通常会看到 00 和 11？", "result_pattern", "Bell"),
            ("shots 是什么意思？", "shots_explanation", "shots"),
            ("模拟器和真机有什么区别？", "backend_explanation", "模拟器"),
        )
        responses = []
        try:
            with mock.patch.object(web.runtime_config, "_chat_completion", return_value=completion):
                for prompt, expected_type, keyword in prompts:
                    status, payload = self.request(
                        "POST", "/api/chat?debug=1", {"prompt": prompt, "context": context}
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(payload["question_type"], expected_type)
                    self.assertIn(keyword, payload["answer"])
                    self.assertFalse(payload["qa_debug"]["used_glossary"])
                    self.assertTrue(payload["qa_debug"]["used_llm"])
                    self.assertIsNone(payload["qa_debug"]["current_gate"])
                    responses.append(payload["answer"])
        finally:
            cfg.clear()

        self.assertEqual(len(set(responses)), 3)
        self.assertTrue(all("H 门让量子比特进入叠加状态" not in text for text in responses))


if __name__ == "__main__":
    unittest.main()
