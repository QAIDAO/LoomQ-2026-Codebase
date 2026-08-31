from html.parser import HTMLParser
from collections import Counter
from pathlib import Path
import re
import subprocess
import sys
import unittest


STATIC = Path(__file__).resolve().parents[1] / "loomq" / "web" / "static"


class MarkupAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.h1_count = 0
        self.labels = set()
        self.buttons_without_type = []
        self.live_regions = 0
        self.details_count = 0
        self.open_details = set()
        self.external_resources = []
        self.text = []
        self.visible_text = []
        self.ids = set()
        self.classes = set()
        self.hrefs = set()
        self.hidden_stack = []
        self.void_tags = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if attributes.get("href", "").startswith("#"):
            self.hrefs.add(attributes["href"][1:])
        self.classes.update(attributes.get("class", "").split())
        if tag == "h1":
            self.h1_count += 1
        if tag == "label" and attributes.get("for"):
            self.labels.add(attributes["for"])
        if tag == "button" and not attributes.get("type"):
            self.buttons_without_type.append(attributes)
        if attributes.get("aria-live"):
            self.live_regions += 1
        if tag == "details":
            self.details_count += 1
            if "open" in attributes:
                self.open_details.add(attributes.get("id", ""))
        if tag not in self.void_tags:
            inherited_hidden = any(self.hidden_stack)
            hidden = inherited_hidden or "hidden" in attributes or (tag == "details" and "open" not in attributes)
            self.hidden_stack.append(hidden)
        for name in ("src", "href"):
            value = attributes.get(name, "")
            if value.startswith(("http://", "https://", "//")):
                self.external_resources.append(value)

    def handle_data(self, data):
        self.text.append(data)
        if not any(self.hidden_stack):
            self.visible_text.append(data)

    def handle_endtag(self, tag):
        if tag in self.void_tags:
            return
        if self.hidden_stack:
            self.hidden_stack.pop()


class WebAssetContractTests(unittest.TestCase):
    def setUp(self):
        self.paths = {
            "html": STATIC / "index.html",
            "css": STATIC / "styles.css",
            "js": STATIC / "app.js",
        }
        for name, path in self.paths.items():
            self.assertTrue(path.is_file(), f"missing {name} asset: {path}")

    def test_markup_has_v7_five_act_story_and_accessible_controls(self):
        audit = MarkupAudit()
        markup = self.paths["html"].read_text(encoding="utf-8")
        audit.feed(markup)
        page_text = " ".join(audit.text)
        compact_text = "".join(page_text.split())

        self.assertEqual(audit.h1_count, 1)
        self.assertTrue({"prompt", "target", "shots"}.issubset(audit.labels))
        self.assertEqual(audit.buttons_without_type, [])
        self.assertGreaterEqual(audit.live_regions, 2)
        self.assertGreaterEqual(audit.details_count, 3)
        self.assertEqual(audit.external_resources, [])
        for required in (
            "为什么反复运行同一份电路，结果会集中在 00 和 11？",
            "先只看一个量子比特",
            "再把两个量子比特连起来",
            "CNOT",
            "00",
            "11",
            "重复次数",
            "OpenQASM",
            "换个方向，再看同一个状态",
            "已归档真机数据 · Origin Wukong 180-2",
            "量子态层析",
            "Fidelity",
            "0.952449",
            "PPT",
            "-0.4561",
            "量子电路程序 · OpenQASM",
            "If you wish to make an apple pie from scratch",
            "Carl Sagan · Cosmos · 1980",
        ):
            self.assertIn("".join(required.split()), compact_text)
        for removed_copy in (
            "CHAPTER ONE",
            "CHAPTER TWO",
            "A MORE PRECISE VIEW",
            "ARCHIVED PROVIDER EVIDENCE",
            "量子态层析会换多个测量方向收集数据",
        ):
            self.assertNotIn(removed_copy, page_text)
        self.assertIn('data-example="bell"', markup)
        self.assertIn('data-value="Czz = 0.99955"', markup)
        self.assertIn('data-value="Cxx = 0.99956"', markup)
        self.assertIn('data-value="Cyy = -0.99865"', markup)
        self.assertNotIn('class="header-nav"', markup)
        self.assertIn('data-language-label>中 / EN', markup)
        self.assertIn("This page shows saved run records.", page_text)
        self.assertTrue(
            {
                "launch-notice",
                "runtime-status",
                "runtime-status-copy",
                "experiment-form",
                "workspace",
                "qasm-code",
                "qubit-story-line",
                "bell-story-line",
                "language-toggle",
                "h-gate-help",
                "cnot-help",
                "shots-help",
                "backend-help",
                "agent-tasks",
                "judge-evidence",
                "bell-prediction",
                "prediction-feedback",
                "pauli-tabs",
                "pauli-panel",
                "tomography",
            }.issubset(audit.ids)
        )
        self.assertTrue(
            {"possibility-line", "scroll-float", "science-note", "result-boundary", "term-help", "prediction-choice", "pauli-tab"}.issubset(audit.classes)
        )
        self.assertIn("qasm-disclosure", audit.open_details)
        self.assertTrue({"top", "qubit", "bell", "flow", "experiment", "workspace", "evidence", "tomography"}.issubset(audit.ids))
        self.assertNotIn("particle-canvas", audit.ids)
        self.assertNotIn("<canvas", markup)
        self.assertIn("data-scroll-float", markup)
        self.assertIn("data-stroke-char", markup)
        self.assertIn("data-fill-char", markup)
        self.assertIn("<clipPath", markup)

    def test_v71_public_audience_launch_and_anchor_contract(self):
        audit = MarkupAudit()
        markup = self.paths["html"].read_text(encoding="utf-8")
        audit.feed(markup)
        script = self.paths["js"].read_text(encoding="utf-8")
        visible_page_text = " ".join(audit.visible_text)
        for forbidden_visible in (
            "评委证据路线",
            "可计分",
            "正式评审路径",
            "工程实现的独立验证",
            "补充科学",
            "provenance hash discrepancy",
            "回到 Agent 入口",
        ):
            self.assertNotIn(forbidden_visible, visible_page_text)
        self.assertIn('id="judge-evidence" hidden', markup)
        for required in (
            "initV71PublicExperience",
            "真实机器上的运行记录",
            "真实任务记录 · 实际 QASM · 原始返回结果",
            "想自己问一个量子问题？回到实验区 ↑",
            "technical-disclosure-v71",
            "multi-view-diagram",
            "science-boundary-disclosure",
            "scrollIntoView",
            "H 改变了状态，重复测量显出了分布。",
            "加入 CNOT：q0 控制 q1。",
            "理想 Bell 电路最后主要留下 00 和 11，各约一半。",
            "每个测量方向都只告诉我们一部分信息。",
            "PPT 纠缠检验",
        ):
            self.assertIn(required, script)
        self.assertTrue(audit.hrefs.issubset(audit.ids), sorted(audit.hrefs - audit.ids))
        user_guide = (STATIC.parents[2] / "USER_GUIDE.md").read_text(encoding="utf-8")
        self.assertIn(".\\starter_kit\\scripts\\run_web.ps1 -Port 8765", user_guide)
        self.assertNotIn("npm run dev", user_guide)

    def test_css_has_v7_tokens_responsive_motion_and_touch_guardrails(self):
        css = self.paths["css"].read_text(encoding="utf-8")
        for required in (
            "--page: #FFFFFF",
            "--surface: #FFFFFF",
            "--blue: #0071E3",
            "--text-primary:",
            "--border-default:",
            "--lh-display:",
            "--lh-heading:",
            "--lq-accent:",
            "min-height: 44px",
            "text-wrap: balance",
            ".pauli-tabs",
            ".prediction-choice",
            ".title-reveal",
            ".spotlight-card",
            ".line-sidebar",
            ".runtime-status",
            ".result-boundary",
            "prefers-reduced-motion: reduce",
            "max-width: 767px",
            "min-width: 1024px",
            "min-width: 1280px",
            "scroll-margin-top: 72px",
        ):
            self.assertIn(required, css)
        self.assertNotIn("--glow-angle", css)
        self.assertNotIn("#16191F", css)
        self.assertNotIn(".historian-note", css)
        self.assertNotIn("translateY(120%) scaleY(2.3)", css)

    def test_javascript_uses_safe_dom_rendering_same_origin_api_and_v7_interactions(self):
        script = self.paths["js"].read_text(encoding="utf-8")
        for required in (
            "fetch('/api/experiment'",
            "fetch('/api/health'",
            "window.location.protocol === 'file:'",
            "agent_unavailable",
            "invalid_request",
            "execution_failed",
            "textContent",
            "document.documentElement.lang",
            "toggleAttribute('hidden'",
            "prediction-choice",
            "prediction-feedback",
            "pauli-tab",
            "Czz = 0.99955",
            "Cxx = 0.99956",
            "Cyy = -0.99865",
            "aria-selected",
            "IntersectionObserver",
            "requestAnimationFrame",
            "stepperFinish.hidden = false",
        ):
            self.assertIn(required, script)
        for forbidden in (
            "innerHTML",
            "localStorage",
            "sessionStorage",
            "LOOMQ_LLM_API_KEY",
            "http://",
            "https://",
            "translateY(120%)",
            "scaleY(2.3)",
            "setInterval(",
            "quantumFieldLoop",
            "particleCanvas",
        ):
            self.assertNotIn(forbidden, script)
        self.assertIn("getBoundingClientRect", script)
        self.assertIn("updateStrokeViewport", script)
        self.assertNotIn("edgeDistance", script)

    def test_javascript_required_dom_selectors_exist_in_markup(self):
        audit = MarkupAudit()
        audit.feed(self.paths["html"].read_text(encoding="utf-8"))
        script = self.paths["js"].read_text(encoding="utf-8")
        selectors = re.findall(
            r"document\.querySelector(?:All)?\(['\"]([.#][A-Za-z0-9_-]+)['\"]\)",
            script,
        )
        missing = []
        for selector in selectors:
            collection = audit.ids if selector.startswith("#") else audit.classes
            if selector[1:] not in collection:
                missing.append(selector)
        self.assertEqual(missing, [], f"JavaScript references missing DOM selectors: {missing}")

    def test_v7_has_bounded_interactions_without_idle_loop(self):
        markup = self.paths["html"].read_text(encoding="utf-8")
        script = self.paths["js"].read_text(encoding="utf-8")
        for forbidden in (
            "quantumFieldLoop",
            "drawFieldConnections",
            "pauseQuantumField",
            "resumeQuantumField",
            "fieldNodes",
            "particleCanvas",
            "measurementCanvas",
            "initMeasurementCanvas",
            "drawMeasurement",
            "setInterval(",
            "document.addEventListener('pointermove'",
            'document.addEventListener("pointermove"',
        ):
            self.assertNotIn(forbidden, script)
        self.assertNotIn("particle-canvas", markup)
        self.assertIn("updateScrollTutorials", script)
        self.assertIn("scheduleScrollUpdate", script)
        self.assertIn("initStepper", script)
        self.assertIn("initSpotlightCards", script)
        self.assertIn("initLineSidebar", script)
        self.assertIn("prefers-reduced-motion", script)
        self.assertIn("#qubit-story-line", script)
        self.assertIn("#bell-story-line", script)

    def test_v71_final_micro_patch_contract(self):
        markup = self.paths["html"].read_text(encoding="utf-8")
        css = self.paths["css"].read_text(encoding="utf-8")
        script = self.paths["js"].read_text(encoding="utf-8")

        for required in (
            'class="result-card result-source-card"',
            'class="result-source-grid"',
            'class="result-source-circuit"',
            'id="qasm-disclosure" open',
            'h-narrative-copy',
            '把同一份电路重复很多次，0 和 1 会各出现大约一半。',
            '这种准备方式会得到一种均匀叠加状态。',
            '每次测量仍然只留下一个结果。',
            'id="model-disclosure"',
            '进阶功能：让 LoomQ 理解你自己的问题（可选）',
            'LOOMQ_LLM_BASE_URL',
            'LOOMQ_LLM_API_KEY',
            'LOOMQ_LLM_MODEL',
            'LOOMQ_LLM_TIMEOUT_SECONDS',
            'class="disclosure-marker"',
        ):
            self.assertIn(required, markup)
        self.assertNotIn("正式评测由服务端注入模型", markup)
        self.assertNotIn("Formal judging injects the model server-side", markup)
        self.assertIn("makeDisclosureSummary", script)
        for required in (
            ".result-source-grid",
            "grid-template-columns: repeat(2, minmax(0, 1fr))",
            "@media (max-width: 899px)",
            "details[open] > summary .disclosure-marker",
            "summary:focus-visible",
            ".h-narrative-copy .sentence-line",
        ):
            self.assertIn(required, css)

    def test_v72_zero_knowledge_onboarding_and_symbol_guide_contract(self):
        markup = self.paths["html"].read_text(encoding="utf-8")
        compact_markup = "".join(markup.split())

        self.assertIn('id="onboarding"', markup)
        for required in (
            "开始前，先认四件事",
            "你不用先学过量子力学",
            "量子计算也是在处理信息",
            "量子比特是量子计算里的基本信息单位",
            "我们只做一个最小实验",
            "先认识四个符号",
            "Quantum computing is another way of processing information.",
            "A qubit is a basic unit of quantum information.",
        ):
            self.assertIn("".join(required.split()), compact_markup)
        for symbol in ("|0⟩", "H", "CNOT", "M"):
            self.assertIn(symbol, markup)
        self.assertIn('data-zh="从 0 状态开始"', markup)
        self.assertIn('data-en="start in the 0 state"', markup)

    def test_v72_term_help_buttons_are_accessible_and_dictionary_is_bilingual(self):
        markup = self.paths["html"].read_text(encoding="utf-8")
        script = self.paths["js"].read_text(encoding="utf-8")
        trigger_matches = re.findall(r"<button\b([^>]*data-help-target=[^>]*data-term-key=[^>]*)>", markup)
        self.assertGreaterEqual(len(trigger_matches), 12)
        target_ids = []
        for attributes in trigger_matches:
            self.assertRegex(attributes, r'\btype="button"')
            self.assertRegex(attributes, r'\bclass="[^"]*term-help-trigger')
            self.assertRegex(attributes, r'\baria-label="[^"]+"')
            match = re.search(r'data-help-target="([^"]+)"', attributes)
            self.assertIsNotNone(match)
            target_ids.append(match.group(1))

        for target_id in target_ids:
            self.assertRegex(
                markup,
                rf'<(?:div|span)\b(?=[^>]*class="[^"]*term-help)(?=[^>]*id="{re.escape(target_id)}")[^>]*>',
            )

        required_keys = (
            "qubit", "ket-zero", "h-gate", "cnot", "bell-state", "measurement",
            "shots", "openqasm", "backend", "tomography", "density-matrix",
            "fidelity", "ppt", "api-key",
        )
        for key in required_keys:
            self.assertIn("'" + key + "':", script)
        self.assertIn("TERM_HELP_COPY", script)
        self.assertIn("zh:", script)
        self.assertIn("en:", script)
        self.assertIn("aria-describedby", script)
        self.assertIn("event.key !== 'Escape'", script)

        ids = re.findall(r'\bid="([A-Za-z][A-Za-z0-9_-]*)"', markup)
        duplicates = sorted(key for key, count in Counter(ids).items() if count > 1)
        self.assertEqual(duplicates, [])

    def test_v72_api_is_explicitly_optional_and_disclosures_have_affordances(self):
        markup = self.paths["html"].read_text(encoding="utf-8")
        css = self.paths["css"].read_text(encoding="utf-8")
        script = self.paths["js"].read_text(encoding="utf-8")
        compact_markup = "".join(markup.split())
        for required in (
            "第一次体验 LoomQ，不需要 API Key",
            "现成的 Bell 实验和本地模拟可以直接运行",
            "进阶功能：让 LoomQ 理解你自己的问题（可选）",
            "第一次体验这页，不需要配置这里",
            "只有当你想让 LoomQ 根据你自己的自然语言问题生成、修复或解释量子电路时",
            "You do not need an API key to run the built-in Bell experiment",
        ):
            self.assertIn("".join(required.split()), compact_markup)
        self.assertIn("initV72PublicCopy", script)
        self.assertNotIn("正式评测会注入 LOOMQ_LLM_", markup)
        summaries = re.findall(r'<summary\b([^>]*)>(.*?)</summary>', markup, flags=re.DOTALL)
        self.assertGreaterEqual(len(summaries), 5)
        self.assertGreaterEqual(sum("disclosure-marker" in content for attributes, content in summaries), 3)
        self.assertIn("experiment-settings > summary::before", css)
        self.assertIn("density-help > summary::before", css)

    def test_v72_protected_values_and_result_source_contract_remain_exact(self):
        markup = self.paths["html"].read_text(encoding="utf-8")
        script = self.paths["js"].read_text(encoding="utf-8")
        for value in (
            'data-value="Czz = 0.99955"',
            'data-value="Cxx = 0.99956"',
            'data-value="Cyy = -0.99865"',
            "0.952449",
            "-0.4561",
            "已归档真机数据 · Origin Wukong 180-2",
            "LOOMQ_LLM_BASE_URL",
            "LOOMQ_LLM_API_KEY",
            "LOOMQ_LLM_MODEL",
            "LOOMQ_LLM_TIMEOUT_SECONDS",
            'class="result-source-grid"',
            'id="qasm-disclosure"',
        ):
            self.assertIn(value, markup)
        for value in ("Czz = 0.99955", "Cxx = 0.99956", "Cyy = -0.99865"):
            self.assertIn(value, script)

    def test_v721_teaching_and_runtime_hooks_are_present(self):
        markup = self.paths["html"].read_text(encoding="utf-8")
        script = self.paths["js"].read_text(encoding="utf-8")
        css = self.paths["css"].read_text(encoding="utf-8")
        for required in (
            'id="h-lab"',
            'id="cnot-rule-result"',
            'id="bell-shot-lab"',
            'class="cnot-rule-choice"',
            'data-ideal-local="true"',
            "控制位是 0：目标位不变。",
            "控制位是 1：目标位翻转。",
            "在 Z 基测量理想 Bell Φ+ 态时，只会得到 00 或 11，各约 50%。",
        ):
            self.assertIn(required, markup)
        for required in (
            "initHInteraction",
            "initCnotInteraction",
            "initBellShotAccumulator",
            "groupCircuitColumns",
            "backend_unavailable",
        ):
            self.assertIn(required, script)
        for required in (".h-lab", ".tutorial-card > .h-lab", ".cnot-rule-choice", ".bell-shot-lab", ".measurement-glyph"):
            self.assertIn(required, css)

    def test_v722_judge_aligned_beginner_ux_hooks_are_present(self):
        markup = self.paths["html"].read_text(encoding="utf-8")
        script = self.paths["js"].read_text(encoding="utf-8")
        css = self.paths["css"].read_text(encoding="utf-8")
        for required in (
            'id="hero-beginner-path"',
            'id="hero-agent-path"',
            'id="outcome-first"',
            'id="agent-entry"',
            'id="circuit-inspect"',
            'class="agent-prompt-card"',
            "先看结果，再一步步看它是怎么发生的。",
            "接下来，直接说出你想做什么。",
            "帮我生成一个 GHZ 态并测量",
            "这段 Bell 电路写错了，帮我修好",
            "我有一个 15 比特任务，不想排队，应该选哪个后端？",
            "同一类电路也已经交给了真实量子机器",
        ):
            self.assertIn(required, markup)
        for required in (
            "initCircuitInspect",
            "initAgentPromptCards",
            "agentPromptCards",
        ):
            self.assertIn(required, script)
        for required in (".outcome-first", ".agent-entry", ".agent-prompt-card", ".circuit-inspect", ".bell-lane { position: relative; }"):
            self.assertIn(required, css)

    def test_server_module_help_starts_without_runtime_warning(self):
        repository_root = Path(__file__).resolve().parents[2]
        completed = subprocess.run(
            [sys.executable, "-m", "starter_kit.loomq.web.server", "--help"],
            cwd=repository_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("RuntimeWarning", completed.stderr)


if __name__ == "__main__":
    unittest.main()
