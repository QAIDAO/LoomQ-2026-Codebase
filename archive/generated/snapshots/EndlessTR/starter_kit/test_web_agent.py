#!/usr/bin/env python3
"""Router unit tests - 任务书 §34 / §35 / §36 / §40.2 + 第二轮/第三轮路由。

结构信号（QASM/后端/生成/测量/多轮）走确定性规则、allow_llm=False 测；
语义细分（诊断/校验/编辑/question_type/scope）走 LLM，用 mock completion 测。
"""

from __future__ import annotations

import json
import unittest

from starter_kit.quantumhelper_web import web_agent


def _route(prompt: str, context: dict | None = None):
    return web_agent.route(prompt, context, allow_llm=False)


def _route_with_llm(prompt: str, intent: str, context=None, **extra):
    """用 mock completion 模拟 LLM 结构化分类，返回最终 Route。"""
    content = json.dumps({
        "intent": intent,
        "confidence": 0.9,
        "requires_clarification": False,
        "reason": "mock",
        **extra,
    }, ensure_ascii=False)

    def completion(_messages):
        return {"choices": [{"message": {"content": content}}]}

    return web_agent.route(prompt, context, completion=completion, allow_llm=True)


class IntentRouterTests(unittest.TestCase):
    def test_qa(self):
        r = _route("H 门到底干嘛的，别给我公式")
        self.assertEqual(r.intent, "quantum_qa")
        self.assertTrue(r.slots["no_formula"])

    def test_beginner_generation(self):
        r = _route("给我弄个新手能看懂的量子线路")
        self.assertEqual(r.intent, "generate_circuit")
        self.assertEqual(r.slots["goal"], "superposition")
        self.assertEqual(r.slots["qubits"], 1)
        self.assertTrue(r.assumptions)

    def test_simple_entanglement(self):
        r = _route("给我一个最简单的量子纠缠例子，不要太复杂")
        self.assertEqual(r.intent, "generate_circuit")
        self.assertEqual(r.slots["goal"], "bell")
        self.assertEqual(r.slots["qubits"], 2)

    def test_repair(self):
        r = _route("我想制备一个贝尔态，但这段代码报错了：H q[0]; CX q[0] q[1]")
        self.assertEqual(r.intent, "repair_circuit")

    def test_verify_only(self):
        # 第三轮 §五：「这段代码对吗」是 validate_circuit（语义判断走 LLM）。
        r = _route_with_llm("我要 Bell 态，这段代码对吗？h q[0]; x q[1];", "validate_circuit")
        self.assertEqual(r.intent, "validate_circuit")

    def test_backend(self):
        r = _route("我要真机、免费、零排队、无需账号")
        self.assertEqual(r.intent, "select_backend")

    def test_optimization_clarifies(self):
        r = _route("给我弄个量子优化线路")
        self.assertEqual(r.intent, "generate_circuit")
        self.assertTrue(r.requires_clarification)

    def test_unknown_never_becomes_generate(self):
        r = _route("今天天气怎么样")
        self.assertEqual(r.intent, "unknown")
        self.assertNotEqual(r.intent, "generate_circuit")


class MultiTurnRoutingTests(unittest.TestCase):
    CTX = {"current_qasm": "OPENQASM 2.0;"}

    def test_modify_qubits(self):
        r = _route("改成 5 比特", self.CTX)
        self.assertEqual(r.intent, "modify_current_task")
        self.assertEqual(r.slots["qubits"], 5)

    def test_measurement_only_followup(self):
        r = _route("只测量第一个量子比特", self.CTX)
        self.assertEqual(r.intent, "modify_current_task")
        self.assertTrue(r.slots["measurement_only"])

    def test_contextual_qa(self):
        r = _route("H 门到底干嘛的，别给我公式", self.CTX)
        self.assertEqual(r.intent, "quantum_qa")
        self.assertEqual(r.question_type, "gate_definition")


class ScenarioDetectionTests(unittest.TestCase):
    def test_search_card(self):
        r = _route("我有 8 个候选编号，其中只有一个满足条件，希望找到它。")
        self.assertEqual(r.intent, "scenario_help")
        self.assertEqual(r.scenario_id, "search")

    def test_optimization_card(self):
        r = _route("我有几种排程方案，希望从中选一个冲突更少、更合适的方案。")
        self.assertEqual(r.intent, "scenario_help")
        self.assertEqual(r.scenario_id, "optimization")

    def test_measurement_card(self):
        r = _route("重复运行同一条两比特线路，观察不同测量结果出现的次数和分布。")
        self.assertEqual(r.intent, "scenario_help")
        self.assertEqual(r.scenario_id, "measurement")


class QasmExtractionTests(unittest.TestCase):
    def test_extract_clean_qasm(self):
        prompt = "我想制备一个贝尔态，但这段代码报错了，帮我修好： H q[0]; CX q[0] q[1]"
        self.assertEqual(
            web_agent.extract_qasm_from_prompt(prompt),
            "H q[0]; CX q[0] q[1]",
        )

    def test_extract_fenced(self):
        prompt = "代码：\n```qasm\nOPENQASM 2.0;\ninclude \"qelib1.inc\";\n```"
        self.assertIn("OPENQASM 2.0;", web_agent.extract_qasm_from_prompt(prompt))

    def test_goal_extraction(self):
        self.assertEqual(web_agent.extract_goal("我要 Bell 态"), "bell")
        self.assertEqual(web_agent.extract_goal("3 比特 GHZ"), "ghz")
        self.assertIsNone(web_agent.extract_goal("随便来条线路"))


class ThirdRoundRoutingTests(unittest.TestCase):
    """第三轮 §43：语义细分（诊断/校验/编辑/question_type/scope）由 LLM 分类，用 mock 测。"""

    def test_edit_qasm_textual(self):
        # Test 3: 文本编辑 ≠ 任务修改，绝不能重新生成任务。语义判断走 LLM。
        r = _route_with_llm("把最后一行改成 cx q[0],q[2];", "edit_current_qasm", {"current_qasm": "OPENQASM 2.0;"})
        self.assertEqual(r.intent, "edit_current_qasm")

    def test_delete_semicolon_edit(self):
        # Test 4: 删分号也是 edit_current_qasm（LLM 分类）。
        r = _route_with_llm("删掉 h q[0]; 后面的分号", "edit_current_qasm", {"current_qasm": "OPENQASM 2.0;"})
        self.assertEqual(r.intent, "edit_current_qasm")

    def test_validate_circuit(self):
        r = _route_with_llm("这段代码能运行吗？OPENQASM 2.0;\nqreg q[2];\nh q[0];", "validate_circuit")
        self.assertEqual(r.intent, "validate_circuit")

    def test_question_type_parsed_from_llm(self):
        # Test 6/7: question_type 由 LLM 结构化输出，路由层只负责透传校验。
        r = web_agent._route_from_llm_payload(
            {"choices": [{"message": {"content": '{"intent":"quantum_qa","confidence":0.9,"question_type":"gate_definition"}'}}]}
        )
        self.assertEqual(r.question_type, "gate_definition")

    def test_diagnose_out_of_range(self):
        # Test 8: 诊断（LLM 分类）+ inspect_external_code scope。
        r = _route_with_llm(
            "帮我看看这段代码哪里错了：\nOPENQASM 2.0;\nqreg q[2];\nh q[0];\ncx q[0],q[2];",
            "diagnose_circuit", conversation_scope="inspect_external_code",
        )
        self.assertEqual(r.intent, "diagnose_circuit")
        self.assertEqual(r.conversation_scope, "inspect_external_code")


class SecondRoundRoutingTests(unittest.TestCase):
    """第二轮 §16：结构信号走规则（allow_llm=False）。"""

    def test_new_task_scope_for_beginner_example(self):
        r = _route("我第一次玩，给我一个最简单能看懂的例子")
        self.assertEqual(r.intent, "generate_circuit")
        self.assertEqual(r.conversation_scope, "new_task")

    def test_continue_scope_for_modify(self):
        r = _route("改成 5 比特", {"current_qasm": "OPENQASM 2.0;"})
        self.assertEqual(r.intent, "modify_current_task")
        self.assertEqual(r.conversation_scope, "continue_current_task")


class LLMSchemaValidationTests(unittest.TestCase):
    """任务书 §31: malformed JSON / unknown intent / 非布尔 confidence 不得进 adapter。"""

    def test_unknown_intent_becomes_unknown(self):
        r = web_agent._route_from_llm_payload(
            {"choices": [{"message": {"content": '{"intent":"hack","confidence":0.9}'}}]}
        )
        self.assertEqual(r.intent, "unknown")

    def test_malformed_json_becomes_unknown(self):
        r = web_agent._route_from_llm_payload(
            {"choices": [{"message": {"content": "不是 JSON"}}]}
        )
        self.assertEqual(r.intent, "unknown")

    def test_bool_confidence_rejected(self):
        r = web_agent._route_from_llm_payload(
            {"choices": [{"message": {"content": '{"intent":"quantum_qa","confidence":true}'}}]}
        )
        self.assertEqual(r.intent, "quantum_qa")
        self.assertEqual(r.confidence, 0.5)  # bool 不是合法数值，回落到默认

    def test_fenced_json_stripped(self):
        r = web_agent._route_from_llm_payload(
            {"choices": [{"message": {"content": '```json\n{"intent":"quantum_qa","confidence":0.8}\n```'}}]}
        )
        self.assertEqual(r.intent, "quantum_qa")
        self.assertEqual(r.confidence, 0.8)


class CuratedQATests(unittest.TestCase):
    def test_h_gate_answer_no_formula(self):
        hit = web_agent.curated_answer("H 门到底干嘛的，别给我公式")
        self.assertIsNotNone(hit)
        topic, answer = hit
        self.assertEqual(topic, "h_gate")
        self.assertNotIn("矩阵", answer)
        self.assertNotIn("H =", answer)


class QuestionTypeGatingTests(unittest.TestCase):
    """§10/§32, Test 7: "为什么这里用 X" 必须结合当前线路，不能被词典抢答。"""

    def _mock_llm_answer(self, text: str):
        def completion(_messages):
            return {"choices": [{"message": {"content": text}}]}
        return completion

    def test_gate_definition_still_uses_glossary(self):
        answer = web_agent.answer_quantum_qa(
            "H 门是什么？", question_type="gate_definition",
        )
        self.assertEqual(answer.source, "curated")
        self.assertEqual(answer.topic, "h_gate")

    def test_missing_question_type_is_inferred_from_user_text(self):
        # Missing classifier metadata is re-inferred from the question itself;
        # it is not a blanket permission to enter the glossary.
        answer = web_agent.answer_quantum_qa("H 门是什么？", question_type=None)
        self.assertEqual(answer.source, "curated")

    def test_contextual_question_bypasses_glossary_even_with_keyword_hit(self):
        # "为什么这里要用H门" contains the same keyword as the curated H-gate
        # entry, but question_type says this needs the actual circuit - the
        # dictionary must not answer it.
        completion = self._mock_llm_answer("结合你当前的线路来看，这里用 H 门是因为……")
        answer = web_agent.answer_quantum_qa(
            "为什么这里要用H门？",
            question_type="gate_role_in_current_circuit",
            completion=completion,
        )
        self.assertEqual(answer.source, "llm")
        self.assertIn("结合你当前的线路", answer.text)

    def test_result_pattern_question_bypasses_glossary(self):
        completion = self._mock_llm_answer("因为纠缠，两个比特的结果绑定在一起……")
        answer = web_agent.answer_quantum_qa(
            "为什么 Bell 态通常会看到 00 和 11？",
            question_type="result_pattern",
            completion=completion,
        )
        self.assertEqual(answer.source, "llm")


class QARoutingRegressionTests(unittest.TestCase):
    """Regression: current H circuit must never become the default QA subject."""

    CIRCUIT = {"current_qasm": "OPENQASM 2.0; h q[0]; cx q[0],q[1];"}
    RESULT = {
        **CIRCUIT,
        "result": {"counts": {"00": 510, "11": 514}, "shots": 1024},
    }

    @staticmethod
    def completion(text):
        return lambda _messages: {"choices": [{"message": {"content": text}}]}

    def test_1_h_definition_uses_explicit_gate_glossary(self):
        route = _route("H 门是什么？", self.CIRCUIT)
        self.assertEqual((route.intent, route.question_type), ("quantum_qa", "gate_definition"))
        self.assertEqual(route.slots["explicit_subject"], "h_gate")
        answer = web_agent.answer_quantum_qa(
            "H 门是什么？",
            self.CIRCUIT,
            question_type=route.question_type,
            explicit_subject=route.slots["explicit_subject"],
        )
        self.assertTrue(answer.used_glossary)
        self.assertEqual(answer.topic, "h_gate")

    def test_2_explicit_current_h_role_uses_circuit_handler(self):
        route = _route("为什么这里用了 H？", self.CIRCUIT)
        self.assertEqual(route.intent, "explain_current_circuit")
        self.assertEqual(route.question_type, "gate_role_in_current_circuit")
        self.assertEqual(route.slots["explicit_subject"], "h_gate")
        self.assertEqual(route.slots["gate"], "h")

    def test_3_bell_result_pattern_is_not_h_definition(self):
        route = _route("为什么 Bell 态通常会看到 00 和 11？", self.CIRCUIT)
        self.assertEqual((route.intent, route.question_type), ("quantum_qa", "result_pattern"))
        self.assertEqual(route.slots["explicit_subject"], "bell_state")
        answer = web_agent.answer_quantum_qa(
            "为什么 Bell 态通常会看到 00 和 11？",
            self.CIRCUIT,
            question_type=route.question_type,
            explicit_subject=route.slots["explicit_subject"],
            completion=self.completion("Bell 态的两个比特相关，因此主要得到 00 或 11；H 建立叠加，CX 建立关联。"),
        )
        self.assertFalse(answer.used_glossary)
        self.assertIn("00 或 11", answer.text)
        self.assertNotEqual(answer.topic, "h_gate")

    def test_4_shots_has_own_type_and_subject(self):
        route = _route("shots 是什么意思？为什么不是跑一次就行？", self.CIRCUIT)
        self.assertEqual((route.intent, route.question_type), ("quantum_qa", "shots_explanation"))
        self.assertEqual(route.slots["explicit_subject"], "shots")
        answer = web_agent.answer_quantum_qa(
            "shots 是什么意思？为什么不是跑一次就行？",
            self.CIRCUIT,
            question_type=route.question_type,
            explicit_subject="shots",
            completion=self.completion("shots 是同一线路重复测量的次数；单次只有一个结果，多次才能估计概率分布。"),
        )
        self.assertFalse(answer.used_glossary)
        self.assertIn("概率分布", answer.text)
        self.assertNotIn("H 门（Hadamard）", answer.text)

    def test_5_backend_question_does_not_depend_on_current_gate(self):
        route = _route("模拟器和真机有什么区别？", self.CIRCUIT)
        self.assertEqual((route.intent, route.question_type), ("quantum_qa", "backend_explanation"))
        self.assertEqual(route.slots["explicit_subject"], "backend")

    def test_6_current_result_uses_result_handler(self):
        route = _route("这个结果为什么不是刚好 50/50？", self.RESULT)
        self.assertEqual((route.intent, route.question_type), ("explain_result", "current_result_explanation"))
        self.assertEqual(route.slots["explicit_subject"], "current_result")

    def test_8_x_definition_does_not_require_x_in_circuit(self):
        route = _route("X 门是什么？", self.CIRCUIT)
        self.assertEqual(route.question_type, "gate_definition")
        answer = web_agent.answer_quantum_qa(
            "X 门是什么？",
            self.CIRCUIT,
            question_type=route.question_type,
            explicit_subject=route.slots["explicit_subject"],
        )
        self.assertEqual(answer.topic, "x_gate")
        self.assertTrue(answer.used_glossary)

    def test_9_unfamiliar_reasonable_question_uses_general_llm_qa(self):
        prompt = "为什么量子测量不能直接告诉我叠加态里的所有信息？"
        route = _route(prompt, self.CIRCUIT)
        self.assertEqual((route.intent, route.question_type), ("quantum_qa", "measurement_explanation"))
        answer = web_agent.answer_quantum_qa(
            prompt,
            self.CIRCUIT,
            question_type=route.question_type,
            completion=self.completion("一次测量只给出一个经典结果，无法同时读出叠加态的全部振幅信息。"),
        )
        self.assertTrue(answer.used_llm)
        self.assertFalse(answer.used_glossary)


if __name__ == "__main__":
    unittest.main()
