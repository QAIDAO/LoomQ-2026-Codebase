import unittest

from starter_kit.l2_agent import (
    AgentContext,
    AgentEngine,
    AgentIntent,
    BackendSelection,
    ValidationResult,
    default_registry,
)


VALID_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
measure q -> c;"""


class MockLLM:
    """A deterministic test double; it performs no network calls."""

    def __init__(self, intent, repaired_qasm=VALID_QASM):
        self.intent = intent
        self.repaired_qasm = repaired_qasm
        self.understand_calls = []
        self.repair_calls = []

    def understand(self, prompt):
        self.understand_calls.append(prompt)
        if isinstance(self.intent, Exception):
            raise self.intent
        return self.intent

    def repair_qasm(self, **arguments):
        self.repair_calls.append(arguments)
        return self.repaired_qasm


class MockQASMValidator:
    """Represents the single run-and-counts validation boundary."""

    def __init__(self):
        self.calls = []

    def validate(self, qasm, _intent):
        self.calls.append(qasm)
        if qasm == "BROKEN":
            return ValidationResult(
                False, "execution_failed", "mock L1 run rejected QASM", qasm
            )
        return ValidationResult(
            True,
            "verified",
            "mock L1 run and counts passed",
            qasm.strip(),
        )


class MockBackendSelector:
    def __init__(self):
        self.calls = []

    def select(self, constraints, _response_language="zh"):
        self.calls.append(constraints)
        return BackendSelection(
            selected_id="mock_backend",
            explanation="Mock 选择器确认所有约束均满足。",
            alternatives=["mock_alternative"],
        )


def build_agent(intent, repaired_qasm=VALID_QASM):
    llm = MockLLM(intent, repaired_qasm)
    validator = MockQASMValidator()
    selector = MockBackendSelector()
    context = AgentContext(
        llm=llm,
        backend_selector=selector,
        validator=validator,
    )
    return AgentEngine(context, default_registry()), llm, validator, selector


class L2AgentFrameworkTests(unittest.TestCase):
    def test_explanation_is_a_successful_agent_result(self):
        intent = AgentIntent(
            task_type="explain_current",
            user_goal="解释 Bell 测量结果",
            explanation="00 和 11 各约一半来自 Bell 态的关联测量。",
        )
        agent, _llm, validator, selector = build_agent(intent)

        result = agent.execute("为什么结果是 1:1？")

        self.assertTrue(result.ok)
        self.assertEqual(result.task_type, "explain_current")
        self.assertIn("Bell", result.explanation)
        self.assertEqual(validator.calls, [])
        self.assertEqual(selector.calls, [])

    def test_generate_flow_uses_llm_dispatches_validates_and_renders(self):
        intent = AgentIntent(
            task_type="generate_qasm",
            user_goal="创建一个单比特叠加实验",
            candidate_qasm=VALID_QASM,
            explanation="对量子比特施加 H 门并测量。",
        )
        agent, llm, validator, selector = build_agent(intent)

        reply = agent.respond("请创建一个单比特叠加实验")

        self.assertEqual(llm.understand_calls, ["请创建一个单比特叠加实验"])
        self.assertEqual(validator.calls, [VALID_QASM])
        self.assertEqual(selector.calls, [])
        self.assertEqual(llm.repair_calls, [])
        self.assertIn("OPENQASM 2.0;", reply)
        self.assertIn("```qasm", reply)

    def test_repair_flow_performs_at_most_one_model_repair(self):
        intent = AgentIntent(
            task_type="repair_qasm",
            user_goal="修复代码并保持叠加态目标",
            source_qasm="H q[0]",
            candidate_qasm="BROKEN",
        )
        agent, llm, validator, selector = build_agent(intent)

        reply = agent.respond("这段代码坏了，请保持原目标并修复")

        self.assertEqual(validator.calls, ["BROKEN", VALID_QASM])
        self.assertEqual(len(llm.repair_calls), 1)
        self.assertEqual(llm.repair_calls[0]["source_qasm"], "H q[0]")
        self.assertEqual(
            llm.repair_calls[0]["validation_error"],
            "mock L1 run rejected QASM",
        )
        self.assertEqual(selector.calls, [])
        self.assertIn("OPENQASM 2.0;", reply)

    def test_backend_flow_uses_structured_constraints_not_qasm_tools(self):
        constraints = {"min_qubits": 20, "queue": "none", "cost": "free"}
        intent = AgentIntent(
            task_type="recommend_backend",
            user_goal="选择免费无排队的 20 比特后端",
            backend_constraints=constraints,
        )
        agent, llm, validator, selector = build_agent(intent)

        reply = agent.respond("我要运行 20 比特电路，免费而且不能排队")

        self.assertEqual(len(llm.understand_calls), 1)
        self.assertEqual(selector.calls, [constraints])
        self.assertEqual(validator.calls, [])
        self.assertEqual(llm.repair_calls, [])
        self.assertIn("mock_backend", reply)
        self.assertIn("mock_alternative", reply)

    def test_empty_prompt_is_rejected_before_calling_the_model(self):
        intent = AgentIntent(
            task_type="recommend_backend",
            user_goal="占位任务",
        )
        agent, llm, _validator, _selector = build_agent(intent)

        with self.assertRaisesRegex(ValueError, "non-empty"):
            agent.respond("   ")

        self.assertEqual(llm.understand_calls, [])

    def test_unknown_task_type_is_rejected_after_model_call(self):
        intent = AgentIntent(task_type="unknown_task", user_goal="未知任务")
        agent, llm, _validator, _selector = build_agent(intent)

        with self.assertRaisesRegex(ValueError, "unsupported L2 task type"):
            agent.respond("做一个尚未支持的任务")

        self.assertEqual(len(llm.understand_calls), 1)

    def test_ambiguous_request_returns_an_honest_clarification(self):
        intent = AgentIntent(
            task_type="clarify",
            user_goal="无法可靠识别用户目标",
            explanation="我不确定你希望设计什么电路，请补充输入和目标状态。",
        )
        agent, _llm, validator, selector = build_agent(intent)

        result = agent.execute("帮我弄一下那个东西")

        self.assertFalse(result.ok)
        self.assertEqual(result.task_type, "clarify")
        self.assertIn("不确定", result.message)
        self.assertEqual(validator.calls, [])
        self.assertEqual(selector.calls, [])

    def test_unreadable_model_response_does_not_guess_an_answer(self):
        agent, _llm, validator, selector = build_agent(
            RuntimeError("LoomQ LLM returned invalid JSON")
        )

        result = agent.execute("请处理这个问题")

        self.assertFalse(result.ok)
        self.assertEqual(result.task_type, "clarify")
        self.assertIn("不会猜测或编造", result.message)
        self.assertIsNone(result.qasm)
        self.assertEqual(validator.calls, [])
        self.assertEqual(selector.calls, [])


if __name__ == "__main__":
    unittest.main()
