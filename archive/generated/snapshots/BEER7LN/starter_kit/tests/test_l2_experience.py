"""Tests for the zero-background L2 web experience."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

import l2_app  # noqa: E402


class L2ExperienceTests(unittest.TestCase):
    def test_chat_payload_exposes_qasm_and_simulation_without_extra_model_call(self) -> None:
        qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
measure q[0] -> c[0];
"""
        payload = l2_app.build_chat_payload(
            "create a superposition",
            agent=lambda _prompt: f"Ready.\n```qasm\n{qasm}```",
        )

        self.assertEqual(payload["qasm"], qasm.strip())
        self.assertEqual(payload["answer"], "Ready.")
        self.assertNotIn("OPENQASM", payload["answer"])
        self.assertEqual(sum(payload["simulation"]["counts"].values()), 1024)
        self.assertEqual(payload["simulation"]["bit_order"], "little")

    def test_selection_payload_remains_text_only(self) -> None:
        payload = l2_app.build_chat_payload(
            "choose a backend",
            agent=lambda _prompt: "推荐后端：`spinq_taurus_simulator`",
        )
        self.assertIsNone(payload["qasm"])
        self.assertIsNone(payload["simulation"])

    def test_selected_local_environment_executes_current_qasm(self) -> None:
        qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
x q[0];
measure q[0] -> c[0];
"""
        payload = l2_app.run_environment_payload("local_reference", qasm, 128)

        self.assertEqual(payload["environment"]["kind"], "simulator")
        self.assertEqual(payload["engine"], "loomq.l1.statevector")
        self.assertEqual(payload["result"]["counts"], {"1": 128})
        with self.assertRaisesRegex(ValueError, "does not support web execution"):
            l2_app.run_environment_payload("originq_wukong", qasm, 128)

    def test_existing_qasm_is_validated_without_an_agent_call(self) -> None:
        qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
x q[0];
measure q[0] -> c[0];
"""
        payload = l2_app.validate_qasm_payload(qasm)
        self.assertEqual(payload["qasm"], qasm.strip())
        self.assertEqual(payload["validation"]["qubits"], 1)
        self.assertEqual(payload["validation"]["measurements"], 1)
        self.assertEqual(payload["engine"], "loomq.l1.qasm")
        with self.assertRaisesRegex(ValueError, "measurement"):
            l2_app.validate_qasm_payload(qasm.replace("measure q[0] -> c[0];", ""))

    def test_static_experience_is_accessible_and_responsive(self) -> None:
        html = (STARTER_KIT / "web" / "index.html").read_text(encoding="utf-8")
        css = (STARTER_KIT / "web" / "styles.css").read_text(encoding="utf-8")
        script = (STARTER_KIT / "web" / "app.js").read_text(encoding="utf-8")
        motion_css = (STARTER_KIT / "web" / "motion" / "loomq-motion.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("<main", html)
        self.assertIn("aria-live=\"polite\"", html)
        self.assertIn("aria-label=\"LoomQ Studio 场景导航\"", html)
        self.assertIn('data-studio-nav="learn"', html)
        self.assertIn("id=\"quantumStoryCanvas\"", html)
        self.assertIn("quantum-story.iife.js", html)
        self.assertEqual(html.count("data-story-scene="), 5)
        self.assertIn("id=\"courseList\"", html)
        self.assertIn("id=\"courseMap\"", html)
        self.assertIn("data-screen=\"course\"", html)
        self.assertIn("id=\"courseExperiment\"", html)
        self.assertIn("id=\"courseExperimentCards\"", html)
        self.assertIn("class=\"mini-circuit\"", script)
        self.assertNotIn("id=\"courseShots\"", html)
        self.assertNotIn("id=\"courseRun\"", html)
        self.assertIn("id=\"courseBackToTop\"", html)
        self.assertNotIn("id=\"courseEngine\"", html)
        self.assertNotIn("id=\"courseJob\"", html)
        self.assertIn("id=\"courseResult\"", html)
        self.assertIn("id=\"courseAnimationStage\"", html)
        self.assertNotIn("id=\"courseConclusionBoundary\"", html)
        self.assertNotIn("这次结果能说明什么，也不能说明什么", html)
        self.assertNotIn("经典 bit<br>", html)
        self.assertNotIn("路径相遇时，<br>", html)
        self.assertNotIn("运行信息与 counts 明细", html)
        self.assertIn("id=\"courseSidebarList\"", html)
        self.assertIn("id=\"courseAnimate\"", html)
        self.assertIn("id=\"courseStepBack\"", html)
        self.assertIn("id=\"courseStepNext\"", html)
        self.assertIn("id=\"courseStepCount\"", html)
        self.assertIn("id=\"courseStepTitle\"", html)
        self.assertIn("id=\"courseStepExplanation\"", html)
        self.assertIn("id=\"courseStepDots\"", html)
        self.assertIn("实验步骤图解", html)
        self.assertNotIn("先看动画，再看术语", html)
        self.assertIn("motion/loomq-motion.css", html)
        self.assertIn("motion/loomq-motion.iife.js", html)
        for legacy_screen in (
            "foundations",
            "hypothesis",
            "circuit",
            "simulation",
            "hardware",
            "record",
        ):
            self.assertNotIn(f'data-screen="{legacy_screen}"', html)
        self.assertIn("id=\"playgroundForm\"", html)
        self.assertIn(
            'id="environmentChooser" aria-labelledby="environmentChooserTitle" hidden',
            html,
        )
        self.assertIn("environmentChooser.hidden = !(payload.qasm && payload.simulation)", script)
        self.assertIn(".environment-chooser[hidden] { display: none; }", css)
        self.assertIn("id=\"environmentList\"", html)
        self.assertIn("id=\"agentProposalSummary\"", html)
        self.assertIn("id=\"agentAdopt\"", html)
        self.assertIn("id=\"themeToggle\"", html)
        self.assertNotIn("色觉辅助", html)
        self.assertNotIn('value="select"', html)
        self.assertIn("@media (max-width:", css)
        self.assertIn("flex-direction: column", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn(".remotion-shell", css)
        self.assertIn(".mini-circuit", css)
        self.assertIn('html[data-theme="light"]', css)
        self.assertNotIn(":root{--paper:", motion_css)
        self.assertIn("/api/chat", script)
        self.assertIn("/api/lessons", script)
        self.assertIn("/api/environments", script)
        self.assertIn("/api/evidence/hardware/bell", script)
        self.assertIn("/api/simulate", script)
        self.assertIn("renderCourseAnimation", script)
        self.assertIn("runCourseSimulation", script)
        self.assertIn("renderExperimentCards", script)
        self.assertNotIn("切换情景时，结果会自动更新", html)
        self.assertNotIn("点一个情景，步骤图和结果会一起更新", html)
        self.assertNotIn("你的预测（可选）", html)
        self.assertNotIn("coursePrediction", script)
        self.assertIn("miniCircuitMarkup", script)
        self.assertNotIn("renderCourseResultEvidence", script)
        self.assertIn("openCourseCatalog", script)
        self.assertIn("setTheme", script)
        self.assertIn("loomq-theme", script)
        self.assertIn('id="environmentRun"', html)
        self.assertIn('id="environmentResult"', html)
        self.assertIn('id="hardwareConfig"', html)
        self.assertIn('id="hardwareConfirm"', html)
        self.assertIn('id="hardwareLabel"', html)
        self.assertIn('id="hardwareProfileList"', html)
        self.assertIn('value="custom"', html)
        self.assertIn('value="execute"', html)
        self.assertIn("执行已有代码", html)
        self.assertIn("/api/validate-qasm", script)
        self.assertIn("runExistingQasm", script)
        self.assertIn("验证代码并选择运行环境", script)
        self.assertIn("/api/run-environment", script)
        self.assertIn("/api/hardware/profiles", script)
        self.assertIn("/api/hardware/jobs", script)
        self.assertIn('id="hardwareCurrent"', html)
        self.assertIn('id="hardwareHistoryList"', html)
        self.assertIn('data-screen="history"', html)
        self.assertIn('data-studio-nav="history"', html)
        self.assertGreater(
            html.index('id="hardwareHistoryList"'),
            html.index('data-screen="history"'),
        )
        self.assertIn("loadHardwareHistory", script)
        self.assertIn("renderActiveHardwareJob", script)
        self.assertIn("renderHardwareResult", script)
        self.assertIn("hardware-result-chart", script)
        self.assertIn("provider_job_id", script)
        self.assertIn("profile_id:", script)
        self.assertIn("ORIGINQ_WUKONG_180_REAL_QPU", script)
        self.assertIn("SPINQ_REAL_QPU", script)
        self.assertNotIn("这里的选择只用于查看建议", html)
        self.assertNotIn("真机执行尚未接入", script)
        self.assertNotIn("1024-shot L1 模拟", html)
        self.assertNotIn('class="local-validation"', html)
        self.assertNotIn("editHardwareProfile", script)
        self.assertNotIn('["edit", "修改"]', script)
        self.assertIn("qasmQubitWidth", script)
        self.assertIn("gemini_vp 真机最多支持 2 qubit", script)
        self.assertIn('html[data-theme="light"] .concept-chips span', css)
        self.assertIn("--course-sidebar-width: clamp(", css)
        self.assertIn(".course-terms {", css)
        self.assertIn("padding: clamp(14px", css)
        self.assertNotIn("没有 GHZ 真机 result.json", script)
        story_source = (STARTER_KIT / "webgl" / "src" / "quantum-story.js").read_text(encoding="utf-8")
        story_bundle = STARTER_KIT / "web" / "quantum-story.iife.js"
        self.assertTrue(story_bundle.is_file())
        self.assertIn("ShaderMaterial", story_source)
        self.assertIn("prefers-reduced-motion", story_source)
        self.assertNotIn("Math.random", story_source)
        self.assertIn("adoptAgentProposal", script)
        self.assertNotIn(">重新运行</button>", html)
        self.assertIn("CONCEPT_EXPLANATIONS", script)
        self.assertLess(html.index('id="courseSidebar"'), html.index('<main id="mainContent"'))
        self.assertNotIn("查看本次结果的数据与证据", html)
        self.assertNotIn("选择要比较的情景</label>", html)
        self.assertNotIn("courseResult.hidden = true", script)
        self.assertIn("LoomQMotion.mount", script)
        self.assertIn("LoomQMotion?.setStep", script)
        self.assertIn("COURSE_STEPS", script)
        self.assertIn("renderCourseStep", script)
        self.assertIn("courseStepBack", script)
        self.assertIn("courseStepNext", script)
        self.assertNotIn("从头重播动画", script)
        self.assertIn('showScreen("course"', script)
        self.assertIn("response.ok", script)
        self.assertNotIn("Math.random", script)
        self.assertIn("模型服务尚未连接", script)

    def test_remotion_bundle_and_source_cover_every_experiment_condition(self) -> None:
        bundle = STARTER_KIT / "web" / "motion" / "loomq-motion.iife.js"
        stylesheet = STARTER_KIT / "web" / "motion" / "loomq-motion.css"
        source = (STARTER_KIT / "motion" / "remotion" / "src" / "LoomQMotion.jsx").read_text(
            encoding="utf-8"
        )
        self.assertTrue(bundle.is_file())
        self.assertTrue(stylesheet.is_file())
        experiment_ids = {
            experiment["id"]
            for lesson in l2_app.learning.load_curriculum()["lessons"]
            for experiment in lesson["experiments"]
        }
        self.assertEqual(len(experiment_ids), 13)
        for experiment_id in experiment_ids:
            self.assertIn(experiment_id, source)
        self.assertNotIn("Math.random", source)
        self.assertNotIn("useCurrentFrame", source)
        noise_source = source[source.index("function Noise"):source.index("export function LoomQMotion")]
        self.assertIn("step >= 2 && step < 4", noise_source)
        player_source = (STARTER_KIT / "motion" / "remotion" / "src" / "index.jsx").read_text(
            encoding="utf-8"
        )
        self.assertIn("controls={false}", player_source)
        self.assertIn("autoPlay={false}", player_source)
        self.assertIn("clickToPlay={false}", player_source)
        self.assertIn("function setStep", player_source)

    def test_environment_catalog_only_exposes_locally_usable_choices(self) -> None:
        environment = {
            "LOOMQ_ORIGINQ_API_TOKEN": "secret-origin-token",
            "LOOMQ_ORIGINQ_BACKEND": "WK_C180_2",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            payload = l2_app.available_environments(
                module_available=lambda name: name == "pyqpanda3"
            )

        ids = [item["id"] for item in payload["environments"]]
        self.assertEqual(ids, ["local_reference", "originq_wukong"])
        self.assertNotIn("braket_cloud", ids)
        self.assertNotIn("secret-origin-token", json.dumps(payload))

    def test_unconfigured_hardware_is_not_offered_as_selectable(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            payload = l2_app.available_environments(module_available=lambda _name: True)

        self.assertEqual(
            [item["id"] for item in payload["environments"]],
            ["local_reference"],
        )
        self.assertEqual(
            {item["id"] for item in payload["unavailable"]},
            {"originq_wukong", "spinq_cloud_qpu"},
        )

    def test_health_payload_is_machine_readable(self) -> None:
        payload = l2_app.health_payload()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["level"], "l2")
        self.assertEqual(payload["ui_revision"], "remotion-hyperframes-1")
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
