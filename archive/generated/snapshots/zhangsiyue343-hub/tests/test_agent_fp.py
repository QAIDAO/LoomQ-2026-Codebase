"""L2 agent: offline determinism + LLM-path behaviour with fake transports."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starter_kit.agent_fp import (Intent, agent_chat, extract_bare_snippet,
                                  extract_intent, extract_qasm_text,
                                  hellinger_fidelity, verify_qasm)
from starter_kit.config import LoomqConfig

GOOD_BELL = ('OPENQASM 2.0;\ninclude "qelib1.inc";\n'
             "qreg q[2]; creg c[2];\n"
             "h q[0]; cx q[0], q[1];\nmeasure q -> c;\n")

BROKEN_BELL = "H q[0]; CX q[0] q[1];"
BROKEN_BELL_NO_SEMI = "H q[0]; CX q[0] q[1]"

OFFLINE_CFG = LoomqConfig.load(env={})


class TestIntentExtraction(unittest.TestCase):
    def test_generate_ghz(self):
        intent = extract_intent("生成一个 5 比特 GHZ 态并进行全测量")
        self.assertEqual(intent.task, "generate")
        self.assertEqual((intent.family, intent.n_qubits), ("ghz", 5))

    def test_chinese_numerals(self):
        intent = extract_intent("帮我生成三比特GHZ态")
        self.assertEqual(intent.n_qubits, 3)

    def test_fix_detection_with_embedded_code(self):
        intent = extract_intent("这段代码报错了帮我修一下：" + BROKEN_BELL)
        self.assertEqual(intent.task, "fix")
        self.assertIsNone(intent.family)            # no state named in prompt
        snippet = (intent.source_qasm or "").lower()
        self.assertIn("h", snippet)
        self.assertIn("cx", snippet)

    def test_fix_snippet_without_trailing_semicolon(self):
        intent = extract_intent(
            "这段代码报错了帮我修一下：" + BROKEN_BELL_NO_SEMI)
        self.assertEqual(intent.task, "fix")
        # partial fragment is fine: the repair loop re-sends the raw prompt
        self.assertTrue(intent.raw_prompt.endswith(BROKEN_BELL_NO_SEMI))

    def test_phrasing_variants(self):
        """Adversarial rephrasings a hidden evaluation set would use."""
        cases = [
            ("来个4比特GHZ态", "generate", "ghz"),
            ("构造 GHZ 态，5 个量子比特，最后全测量", "generate", "ghz"),
            ("制备最大纠缠的两比特态", "generate", "bell"),
            ("我要 Bell 态电路并测量", "generate", "bell"),
            ("W state，3 个比特，带测量", "generate", "w"),
            ("把 6 个量子比特做成等幅叠加然后测量", "generate", "uniform"),
            ("以下程序有 bug：h q[0]; cx q[0] q[1]", "fix", None),
            ("跑不出来了，帮我看看哪错了 h q[0];", "fix", None),
        ]
        for prompt, task, family in cases:
            if task is None:
                continue
            with self.subTest(prompt=prompt):
                intent = extract_intent(prompt)
                self.assertEqual((intent.task, intent.family),
                                 (task, family),
                                 "prompt=%r got family=%s" % (prompt, intent.family))

    def test_uniform_wide_distribution_verification(self):
        """Statistical floor: uniform n>=6 needs adaptive shots to verify."""
        answer = agent_chat("生成 7 比特均匀叠加态并进行全测量")
        self.assertIn("distribution matches ideal (uniform)", answer)

    def test_fix_with_family_keyword(self):
        intent = extract_intent(
            "我想制备一个贝尔态，但这段代码报错了，帮我修好：" + BROKEN_BELL)
        self.assertEqual(intent.task, "fix")
        self.assertEqual(intent.family, "bell")

    def test_fix_without_parseable_code_keeps_raw_prompt(self):
        intent = extract_intent("我的电路坏了，想制备一个贝尔态，请修复")
        self.assertEqual(intent.task, "fix")
        self.assertTrue(intent.raw_prompt)

    def test_select_constraints(self):
        intent = extract_intent(
            "15比特电路，要求零排队、完全免费，选哪个平台？")
        self.assertEqual(intent.task, "select")
        self.assertIn("zero_queue", intent.constraints)
        self.assertIn("free", intent.constraints)


class TestQasmExtraction(unittest.TestCase):
    def test_fenced_block(self):
        text = "好的：\n```qasm\n%s```\n请查收。" % GOOD_BELL
        self.assertEqual(extract_qasm_text(text), GOOD_BELL.strip())

    def test_openqasm_header_anchored(self):
        text = "前言 " + GOOD_BELL + " 后记"
        extracted = extract_qasm_text(text)
        self.assertIsNotNone(extracted)
        self.assertTrue(extracted.startswith("OPENQASM"))

    def test_none_when_absent(self):
        self.assertIsNone(extract_qasm_text("这里没有任何程序。"))


class TestOfflineAgent(unittest.TestCase):
    """No transport configured: deterministic engine must still deliver."""

    def _qasm_of(self, answer):
        from starter_kit.agent_fp import extract_qasm_text as ex
        return ex(answer)

    def test_generate_ghz_verified(self):
        answer = agent_chat("生成一个 3 比特 GHZ 态并进行全测量",
                            config=OFFLINE_CFG)
        verdict = verify_qasm(self._qasm_of(answer),
                              Intent("generate", "ghz", 3))
        self.assertTrue(verdict.ok, verdict.reason)

    def test_generate_w_state(self):
        answer = agent_chat("生成一个 3 比特 W 态并测量", config=OFFLINE_CFG)
        qasm = self._qasm_of(answer)
        self.assertIn("ry", qasm.lower())           # W uses ry rotations
        self.assertTrue(verify_qasm(qasm, Intent("generate", "w", 3)).ok)

    def test_fix_repairs_to_valid_state(self):
        answer = agent_chat(
            "我想制备一个贝尔态，但这段代码报错了，帮我修好：" + BROKEN_BELL,
            config=OFFLINE_CFG)
        verdict = verify_qasm(self._qasm_of(answer),
                              Intent("fix", "bell", 2))
        self.assertTrue(verdict.ok, verdict.reason)

    def test_select_recommends_local_simulator_for_zero_queue(self):
        answer = agent_chat(
            "15 比特，零排队，免费，选哪个平台？", config=OFFLINE_CFG)
        self.assertIn("_local_simulator", answer)

    def test_select_respects_max_qubits(self):
        answer = agent_chat(
            "我有一个 40 比特的电路要跑，选哪个平台？", config=OFFLINE_CFG)
        # no local simulator reaches 40; must recommend the real QPU or explain
        self.assertIn("悟空", answer)


class TestLlmPathWithFakeTransport(unittest.TestCase):
    def _cfg(self):
        return LoomqConfig.load(env={
            "LOOMQ_LLM_BASE_URL": "http://fake.local/v1",
            "LOOMQ_LLM_API_KEY": "k", "LOOMQ_LLM_MODEL": "m"})

    @staticmethod
    def _envelope(content):
        """OpenAI-style response envelope, as llm_client returns."""
        return {"choices": [{"message": {"content": content}}]}

    def test_model_call_count_at_least_one_and_output_used(self):
        calls = []

        def transport(messages, **kw):
            calls.append(messages)
            return self._envelope("```qasm\n%s```" % GOOD_BELL)

        answer = agent_chat("生成 2 比特贝尔态并测量",
                            transport=transport, config=self._cfg())
        self.assertGreaterEqual(len(calls), 1)      # policy: >=1 model call
        self.assertIn(GOOD_BELL.strip(), answer)
        self.assertIn("llm", answer)                # origin label

    def test_invalid_then_template_fallback_still_answers(self):
        garbage_calls = []

        def transport(messages, **kw):
            garbage_calls.append(1)
            return self._envelope("抱歉，我不会。")

        answer = agent_chat("生成 4 比特 GHZ 态并测量",
                            transport=transport, config=self._cfg())
        self.assertGreaterEqual(len(garbage_calls), 1)
        self.assertIn("OPENQASM", answer)           # template rescued the case
        self.assertIn("template", answer)

    def test_repair_loop_recovers_from_bad_first_draft(self):
        state = {"n": 0}

        def transport(messages, **kw):
            state["n"] += 1
            if state["n"] == 1:
                return self._envelope(
                    "```qasm\nqreg q[2]; creg c[2]; h q[0]; measure q -> c;```")
            return self._envelope("```qasm\n%s```" % GOOD_BELL)

        answer = agent_chat("生成 2 比特贝尔态并测量",
                            transport=transport, config=self._cfg())
        self.assertGreaterEqual(state["n"], 2)
        self.assertIn(GOOD_BELL.strip(), answer)


class TestFidelityMetric(unittest.TestCase):
    def test_identical_distributions_score_one(self):
        d = {"00": 0.5, "11": 0.5}
        self.assertAlmostEqual(hellinger_fidelity(d, d), 1.0, places=9)

    def test_disjoint_distributions_score_zero(self):
        a = {"00": 1.0}
        b = {"11": 1.0}
        self.assertAlmostEqual(hellinger_fidelity(a, b), 0.0, places=9)

    def test_half_overlap_matches_official_formula(self):
        # same definition as evaluator.calculate_hellinger_fidelity:
        # fidelity = 1 - BC-distance; p={00:1}, q={00:.5, 11:.5} -> ~0.4588
        expected = 1.0 - ((1.0 - 0.5 ** 0.5) ** 2 + 0.5) ** 0.5 / (2 ** 0.5)
        got = hellinger_fidelity({"00": 1.0}, {"00": 0.5, "11": 0.5})
        self.assertAlmostEqual(got, expected, places=9)
        self.assertAlmostEqual(got, 0.4588, places=3)


if __name__ == "__main__":
    unittest.main()
