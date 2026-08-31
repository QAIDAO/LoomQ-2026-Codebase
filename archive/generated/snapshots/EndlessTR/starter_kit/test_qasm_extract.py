#!/usr/bin/env python3
"""Unit tests for qasm_extract - 任务书 §15/§16/§17/§36.

Covers the QASM extraction priorities (fenced block -> OPENQASM header ->
statement-level) and goal separation, with a hard guarantee that natural
language ("帮我修好" / "报错") never leaks into the extracted code.
"""

from __future__ import annotations

import unittest

from starter_kit.quantumhelper_web import qasm_extract


REPAIR_PROMPT = "我想制备一个贝尔态，但这段代码报错了，帮我修好： H q[0]; CX q[0] q[1]"


class QasmStatementExtractionTests(unittest.TestCase):
    def test_mixed_prose_and_code_yields_clean_qasm(self):
        self.assertEqual(
            qasm_extract.extract_qasm_from_prompt(REPAIR_PROMPT),
            "H q[0]; CX q[0] q[1]",
        )

    def test_build_repair_input_separates_goal_from_source(self):
        result = qasm_extract.build_repair_input(REPAIR_PROMPT)
        self.assertEqual(result["goal"], "bell")
        self.assertEqual(result["source_qasm"], "H q[0]; CX q[0] q[1]")

    def test_fenced_qasm_block_wins(self):
        prompt = "代码：\n```qasm\nOPENQASM 2.0;\ninclude \"qelib1.inc\";\n```"
        extracted = qasm_extract.extract_qasm_from_prompt(prompt)
        self.assertIn("OPENQASM 2.0;", extracted)
        self.assertIn('include "qelib1.inc";', extracted)

    def test_openqasm_header_starts_extraction_from_header(self):
        prompt = "这是我的一段程序，帮我看看：OPENQASM 2.0; include \"qelib1.inc\"; qreg q[2]; h q[0];"
        extracted = qasm_extract.extract_qasm_from_prompt(prompt)
        self.assertTrue(extracted.startswith("OPENQASM 2.0;"))
        self.assertNotIn("帮我看看", extracted)

    def test_statement_level_extraction_without_header(self):
        self.assertEqual(
            qasm_extract.extract_qasm_from_prompt("H q[0]; CX q[0] q[1]"),
            "H q[0]; CX q[0] q[1]",
        )

    def test_trailing_prose_after_last_statement_is_dropped(self):
        prompt = "帮我修好： H q[0]; CX q[0] q[1]。谢谢了"
        extracted = qasm_extract.extract_qasm_from_prompt(prompt)
        self.assertEqual(extracted, "H q[0]; CX q[0] q[1]")

    def test_full_width_separators_are_normalized(self):
        self.assertEqual(
            qasm_extract.extract_qasm_from_prompt("H q[0]； CX q[0] q[1]"),
            "H q[0]; CX q[0] q[1]",
        )


class LooksLikeQasmTests(unittest.TestCase):
    def test_gate_statement_detected(self):
        self.assertTrue(qasm_extract.looks_like_qasm("h q[0]; cx q[0],q[1];"))

    def test_structure_detected(self):
        self.assertTrue(qasm_extract.looks_like_qasm("OPENQASM 2.0; qreg q[2];"))

    def test_measure_detected(self):
        self.assertTrue(qasm_extract.looks_like_qasm("measure q[0] -> c[0];"))

    def test_pure_prose_not_detected(self):
        self.assertFalse(qasm_extract.looks_like_qasm("今天天气怎么样"))
        self.assertFalse(qasm_extract.looks_like_qasm("帮我做一个贝尔态"))


class GoalExtractionTests(unittest.TestCase):
    def test_bell_goal(self):
        self.assertEqual(qasm_extract.extract_goal("我要 Bell 态"), "bell")
        self.assertEqual(qasm_extract.extract_goal("制备一个贝尔态"), "bell")
        self.assertEqual(qasm_extract.extract_goal("量子纠缠"), "bell")
        self.assertEqual(qasm_extract.extract_goal("entangle two qubits"), "bell")

    def test_ghz_goal(self):
        self.assertEqual(qasm_extract.extract_goal("3 比特 GHZ"), "ghz")

    def test_qft_goal(self):
        self.assertEqual(qasm_extract.extract_goal("量子傅里叶变换"), "qft")
        self.assertEqual(qasm_extract.extract_goal("QFT 电路"), "qft")

    def test_superposition_goal(self):
        self.assertEqual(qasm_extract.extract_goal("叠加态"), "superposition")
        self.assertEqual(qasm_extract.extract_goal("superposition state"), "superposition")

    def test_unknown_goal_is_none(self):
        self.assertIsNone(qasm_extract.extract_goal("随便来条线路"))


class NoProseLeakTests(unittest.TestCase):
    def test_extraction_never_contains_repair_words(self):
        cases = (
            REPAIR_PROMPT,
            "这段代码报错了，帮我修好： H q[0]; CX q[0] q[1]",
            "H q[0]; CX q[0] q[1] 报错了，帮我修一下",
        )
        for prompt in cases:
            with self.subTest(prompt=prompt):
                extracted = qasm_extract.extract_qasm_from_prompt(prompt) or ""
                self.assertNotIn("帮我修好", extracted)
                self.assertNotIn("报错", extracted)

    def test_pure_natural_language_extracts_nothing(self):
        self.assertIsNone(qasm_extract.extract_qasm_from_prompt("今天天气怎么样"))
        self.assertIsNone(qasm_extract.extract_qasm_from_prompt("帮我做一个贝尔态"))


if __name__ == "__main__":
    unittest.main()
