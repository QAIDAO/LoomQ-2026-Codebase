from __future__ import annotations

import http.client
import json
from pathlib import Path
import threading
import unittest
from unittest import mock

from starter_kit.loomq.compiler.parser import parse_qasm
from starter_kit.loomq.agent.verifier import verify_qasm
from starter_kit.loomq.web import server as web_server


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "starter_kit" / "loomq" / "web" / "static"
LAUNCHER = ROOT / "starter_kit" / "scripts" / "run_web.ps1"


class BellTopologyAndPedagogyTests(unittest.TestCase):
    def test_bell_contract_keeps_h_cnot_then_measurement_order_and_mapping(self):
        report = verify_qasm(web_server.BELL_QASM)
        operations = report.circuit.operations
        self.assertEqual(
            [(type(operation).__name__, getattr(operation, "name", None), getattr(operation, "qubits", None), getattr(operation, "qubit", None)) for operation in operations],
            [
                ("Gate", "h", (0,), None),
                ("Gate", "cx", (0, 1), None),
                ("Measurement", None, None, 0),
                ("Measurement", None, None, 1),
            ],
        )

    def test_result_circuit_has_grouped_measurement_and_explicit_cnot_roles(self):
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        for required in (
            "groupCircuitColumns",
            "measurement-glyph",
            "控制位 q0",
            "目标位 q1",
            "operation.qubits[0]",
            "operation.qubits[1]",
        ):
            self.assertIn(required, script)

    def test_pedagogy_interactions_expose_required_copy_and_controls(self):
        markup = (STATIC / "index.html").read_text(encoding="utf-8")
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        compact = "".join(markup.split())
        for required in (
            'id="h-lab"',
            'id="h-single-run"',
            'id="h-shots-run"',
            'id="h-bloch-details"',
            'id="cnot-rule-result"',
            'class="cnot-rule-choice"',
            'id="bell-shot-lab"',
            'id="bell-one-shot"',
            'id="bell-auto-shots"',
            "H 把 |0⟩ 变成 |+⟩。",
            "如果现在在 Z 基测量，一次只会读出 0 或 1；重复很多次，二者会各占约一半。",
            "控制位是 0：目标位不变。",
            "控制位是 1：目标位翻转。",
            "CNOT 本身不等于“纠缠”",
            "在 Z 基测量理想 Bell Φ+ 态时，只会得到 00 或 11，各约 50%。",
            "shots 是把同一份电路重新准备并测量很多次。",
            "这里先用理想模拟把规律演示出来",
        ):
            self.assertIn("".join(required.split()), compact)
        for required in (
            "initHInteraction",
            "initCnotInteraction",
            "initBellShotAccumulator",
            "requestAnimationFrame",
            "prefers-reduced-motion",
        ):
            self.assertIn(required, script)
        self.assertNotIn("这个量子比特现在同时就是 0 和 1", compact)
        self.assertNotIn("setInterval(", script)


class JudgeAlignedBeginnerUxTests(unittest.TestCase):
    def test_v722_promise_outcome_and_agent_destination_are_explicit(self):
        markup = (STATIC / "index.html").read_text(encoding="utf-8")
        compact = "".join(markup.split())
        for required in (
            'id="hero-beginner-path"',
            'id="hero-agent-path"',
            'id="outcome-first"',
            'id="agent-entry"',
            'id="circuit-inspect"',
            "先看结果，再一步步看它是怎么发生的。",
            "看懂以后，你也可以直接把自己的问题交给 LoomQ。",
            "跟着做一次完整实验",
            "已经懂基础？直接问 LoomQ →",
            "00</strong><span>≈ 50%",
            "11</strong><span>≈ 50%",
            "看看它是怎么做到的",
            "接下来，直接说出你想做什么。",
            "帮我生成一个 GHZ 态并测量",
            "这段 Bell 电路写错了，帮我修好",
            "我有一个 15 比特任务，不想排队，应该选哪个后端？",
            "同一类电路也已经交给了真实量子机器",
            "本地模拟",
            "API Key",
        ):
            self.assertIn("".join(required.split()), compact)

    def test_v722_beginner_order_keeps_agent_after_local_and_hardware_sections(self):
        markup = (STATIC / "index.html").read_text(encoding="utf-8")
        positions = {
            marker: markup.index(marker)
            for marker in (
                'id="outcome-first"',
                'id="onboarding"',
                'id="qubit"',
                'id="bell"',
                'id="experiment"',
                'id="evidence"',
                'id="agent-entry"',
                'id="tomography"',
            )
        }
        self.assertLess(positions['id="outcome-first"'], positions['id="onboarding"'])
        self.assertLess(positions['id="onboarding"'], positions['id="qubit"'])
        self.assertLess(positions['id="qubit"'], positions['id="bell"'])
        self.assertLess(positions['id="bell"'], positions['id="experiment"'])
        self.assertLess(positions['id="experiment"'], positions['id="evidence"'])
        self.assertLess(positions['id="evidence"'], positions['id="agent-entry"'])
        self.assertLess(positions['id="agent-entry"'], positions['id="tomography"'])

    def test_v722_copy_does_not_use_shortcut_misconceptions(self):
        markup = (STATIC / "index.html").read_text(encoding="utf-8")
        forbidden = (
            "旋转硬币",
            "同时既是正面又是反面",
            "同时遍历所有答案",
            "瞬间控制",
            "指数增长",
            "自动放大正确答案",
        )
        for phrase in forbidden:
            self.assertNotIn(phrase, markup)


class HumanAcceptanceUxTests(unittest.TestCase):
    def test_v725_hero_restores_golden_centered_entry_and_cta_hierarchy(self):
        markup = (STATIC / "index.html").read_text(encoding="utf-8")
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        compact = "".join(markup.split())
        for required in (
            'id="hero-see-result"',
            'class="hero-action hero-action--primary"',
            "跟着做一次完整实验 →",
            "已经懂基础？直接问 LoomQ →",
        ):
            self.assertIn("".join(required.split()), compact)
        for required in (
            "initV725GoldenRestore",
            "hero-mystery",
            "hero-preview",
            "先看见一个结果",
            "再走进量子世界",
            "为什么这份只有两个量子比特的电路，反复运行时，答案会集中在 00 和 11？",
            "不懂量子也可以。先跑一次，再看发生了什么。",
            "LoomQ 会把你的自然语言变成量子电路、检查它、选择后端并把结果翻译成人话。",
            "先看结果 ↓",
        ):
            self.assertIn(required, script)
        self.assertIn("hero-golden-line", css)
        self.assertIn("width: fit-content", css)
        self.assertNotIn("initV724Hero();", script)
        self.assertNotIn("先看 Bell 结果", script)
        self.assertNotIn("hero-result-preview", script + css)
        self.assertLess(markup.index('id="hero-see-result"'), markup.index('id="hero-beginner-path"'))
        self.assertNotIn("带我完成第一次实验", markup)
        self.assertNotIn("我有自己的问题", markup)

    def test_v723_beginner_copy_removes_implementation_caveats_and_redundant_help(self):
        markup = (STATIC / "index.html").read_text(encoding="utf-8")
        compact = "".join(markup.split())
        for required in (
            "这里先展示理想状态下的参考结果。真正运行到量子机器上时，数字通常会有一点偏差。",
            "这里先用理想模拟把规律演示出来，方便你看清 00 和 11 是怎么出现的。",
            "接下来，直接说出你想做什么。",
            "你可以像平时提问一样描述目标，LoomQ 会帮你生成电路、检查并运行。",
        ):
            self.assertIn("".join(required.split()), compact)
        for removed in (
            "这是要解释的目标分布，不是假装刚刚提交了一次硬件任务。",
            "理想 / 本地教学可视化：这里不会调用 API，也不会改变后面的真实实验。",
            "现在，把你的问题说成人话就行。",
            'id="onboarding-qubit-help"',
        ):
            self.assertNotIn(removed, markup)

    def test_v723_story_stages_are_scroll_linked_without_wheel_interception(self):
        markup = (STATIC / "index.html").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        self.assertEqual(markup.count('class="tutorial-story-stage'), 2)
        self.assertEqual(markup.count('class="tutorial-story-frame"'), 2)
        self.assertIn("min-height: clamp(180svh, 210svh, 240svh)", css)
        self.assertIn("position: sticky", css)
        self.assertIn(".tutorial-story-stage.tutorial-sticky { position: static; top: auto; }", css)
        self.assertIn("tutorialProgress", script)
        self.assertIn("prefers-reduced-motion", script)
        self.assertNotIn("addEventListener('wheel'", script)
        self.assertNotIn('addEventListener("wheel"', script)

    def test_v723_result_circuit_uses_single_svg_topology(self):
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        for required in (
            "createElementNS",
            "quantum-circuit-svg",
            "circuit-rail",
            "circuit-connector-svg",
            "data-role",
            "control q0",
            "target q1",
        ):
            self.assertIn(required, script)
        self.assertNotIn(".circuit-cell::before", css)
        self.assertNotIn("class\", \"circuit-connector\"", script)

    def test_v723_outcome_delight_is_finite_and_reduced_motion_safe(self):
        markup = (STATIC / "index.html").read_text(encoding="utf-8")
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        for required in (
            'class="outcome-first-stat outcome-first-stat--00"',
            'class="outcome-first-stat outcome-first-stat--11"',
            'class="outcome-decoration outcome-decoration--smile" aria-hidden="true"',
            'class="outcome-decoration outcome-decoration--hop" aria-hidden="true"',
            "initOutcomeDelight",
            "outcome-smile-blink",
            "outcome-hop",
            "prefers-reduced-motion: reduce",
        ):
            self.assertIn(required, markup + script + css)
        self.assertNotIn("animation-iteration-count: infinite", css)

    def test_v724_scroll_progress_ends_before_sticky_stage_releases(self):
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        self.assertIn("tutorial-story-frame", script)
        self.assertIn("stickyStart", script)
        self.assertIn("stickyEnd", script)
        self.assertIn("stageDocumentTop", script)
        self.assertIn("frameDocumentBottom", script)
        self.assertIn("tutorialProgress(section)", script)
        self.assertIn("return clamp((window.scrollY - stickyStart) / stickyTravel, 0, 1);", script)
        self.assertIn("gateProgress", script)
        self.assertIn("connectorProgress", script)
        self.assertIn("resultProgress", script)
        self.assertNotIn("if (raw < 0.12)", script)
        self.assertNotIn("return 0.32;", script)
        self.assertNotIn("return 0.72;", script)
        self.assertIn(".tutorial-story-frame", css)
        self.assertIn("sectionRect", script)
        self.assertIn("naturalTravel", script)

    def test_v725_single_qubit_copy_has_a_wide_sentence_measure(self):
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        self.assertIn("先从 |0⟩ 出发。\\n现在立刻测量，结果会是 0。", script)
        self.assertIn("接着加入 H。\\n先别急着记定义，先看它带来的变化。\\n重复测量以后，0 和 1 都会出现。", script)
        self.assertIn(".tutorial-story-stage .tutorial-copy { width: min(100%, 620px);", css)
        self.assertIn(".tutorial-body.v71-copy", css)

    def test_v725_outcome_cards_keep_the_feedback_local_and_light(self):
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".outcome-first-stat--00 .outcome-decoration--smile", css)
        self.assertIn("opacity: 0;", css)
        self.assertIn("width: 20px;", css)
        self.assertIn(".outcome-first-stat--11:hover strong", css)
        self.assertIn("animation: outcome-hop 220ms", css)
        self.assertIn(".outcome-first-stat:focus-visible", css)
        self.assertNotIn(
            ".outcome-first-stat:hover, .outcome-first-stat:focus-visible, .outcome-first-stat.is-delighted { border-color: var(--blue);",
            css,
        )

    def test_v724_beginner_copy_and_circuit_feedback_are_plain_and_targeted(self):
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        for required in (
            "先从 |0⟩ 出发。",
            "现在立刻测量，结果会是 0。",
            "接着加入 H。",
            "接着加入 H。先看它带来的变化。",
            "先别急着记定义，先看它带来的变化。",
            "第一次先用现成的 Bell 例子就行，不用配 API Key。",
            "想让 LoomQ 帮你生成、修改或解释自己的电路时，再连接模型。",
            "滚到底时会接近各一半。",
        ):
            self.assertIn(required, script)
        self.assertIn(".outcome-first-stat--00 .outcome-decoration--smile", css)
        self.assertIn(".outcome-first-stat--11:hover strong", css)
        self.assertIn("--circuit-stroke: 2px", css)


class BackendAvailabilityAndLauncherTests(unittest.TestCase):
    def setUp(self):
        self.server = web_server.create_server("127.0.0.1", 0, static_root=STATIC)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method: str, path: str, payload: object | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {} if body is None else {"Content-Type": "application/json"}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        content_type = response.getheader("Content-Type", "")
        connection.close()
        return response.status, json.loads(raw) if "application/json" in content_type else raw.decode("utf-8")

    def test_health_exposes_safe_backend_availability(self):
        status, payload = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(set(payload["backends"]), {"spinq", "originq", "braket"})
        for backend_id, details in payload["backends"].items():
            with self.subTest(backend_id=backend_id):
                self.assertIsInstance(details["available"], bool)
                self.assertNotIn("Traceback", details["status"])
                self.assertNotIn("C:\\", details["status"])

    def test_unavailable_backend_is_rejected_before_adapter_run(self):
        unavailable = {
            "spinq": {"available": False, "dependency": "spinqit==0.2.4", "status": "missing dependency"},
            "originq": {"available": True, "dependency": "pyqpanda", "status": "available"},
            "braket": {"available": True, "dependency": "amazon-braket-sdk", "status": "available"},
        }
        with mock.patch.object(web_server, "backend_availability", create=True, return_value=unavailable), mock.patch.object(
            web_server.adapter,
            "run",
            side_effect=AssertionError("adapter.run must not be called for unavailable backend"),
        ):
            status, payload = self.request(
                "POST",
                "/api/experiment",
                {"prompt": "做一次 Bell 实验", "example": "bell", "target": "spinq", "shots": 100},
            )
        self.assertEqual(status, 503)
        self.assertEqual(payload["error"]["code"], "backend_unavailable")
        self.assertIn("starter_kit", payload["error"]["message"])
        self.assertIn("setup.ps1", payload["error"]["message"])

    def test_launcher_is_precise_and_checks_pinned_spinqit(self):
        self.assertTrue(LAUNCHER.is_file())
        launcher = LAUNCHER.read_text(encoding="utf-8")
        for required in (
            "$PSScriptRoot",
            ".venv\\Scripts\\python.exe",
            "spinqit",
            "0.2.4",
            "-m starter_kit.loomq.web.server",
            "http://127.0.0.1:",
            "starter_kit\\scripts\\setup.ps1",
        ):
            self.assertIn(required, launcher)
        self.assertNotIn("SpinQit is unavailable; run starter_kit/scripts/setup", launcher)


if __name__ == "__main__":
    unittest.main()
