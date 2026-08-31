import unittest

from starter_kit.l2_agent import (
    AgentContext,
    AgentEngine,
    AgentIntent,
    default_registry,
)
from starter_kit.l2_agent.tools import (
    CapabilityBackendSelector,
    QASMValidator,
)


GHZ_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[0],q[2];
measure q -> c;"""

WRONG_GHZ_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
measure q -> c;"""


class FakeL1Executor:
    def __init__(self, counts=None, error=None):
        self.counts = counts or {"000": 2048, "111": 2048}
        self.error = error
        self.calls = []

    def __call__(self, qasm, target, shots):
        self.calls.append((qasm, target, shots))
        if self.error:
            raise self.error
        return {
            "backend": target,
            "job_id": "local-test-job",
            "shots": shots,
            "counts": self.counts,
            "bit_order": "little",
        }


class QASMValidatorTests(unittest.TestCase):
    def intent(self, target="ghz", qubits=3, measure_all=True):
        return AgentIntent(
            task_type="generate_qasm",
            user_goal="生成目标电路",
            circuit={
                "target_state": target,
                "qubits": qubits,
                "measure_all": measure_all,
            },
        )

    def test_ghz_is_really_submitted_to_the_configured_l1_runner(self):
        executor = FakeL1Executor()
        validator = QASMValidator(
            target="spinq", shots=4096, executor=executor
        )

        result = validator.validate(GHZ_QASM, self.intent())

        self.assertTrue(result.ok, result.explanation)
        self.assertEqual(executor.calls, [(GHZ_QASM, "spinq", 4096)])
        self.assertEqual(result.status, "verified")
        self.assertAlmostEqual(result.fidelity, 1.0)
        self.assertEqual(result.details["job_id"], "local-test-job")
        self.assertEqual(result.details["counts"], {"000": 2048, "111": 2048})

    def test_wrong_distribution_fails_fidelity(self):
        executor = FakeL1Executor(counts={"000": 2048, "001": 2048})
        validator = QASMValidator(executor=executor)

        result = validator.validate(WRONG_GHZ_QASM, self.intent())

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "fidelity_failed")
        self.assertLess(result.fidelity, 0.97)

    def test_unknown_random_target_is_executed_without_false_correctness_claim(self):
        executor = FakeL1Executor(counts={"000": 1024, "101": 3072})
        validator = QASMValidator(executor=executor)

        result = validator.validate(GHZ_QASM, self.intent(target="random"))

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "executed_unverified")
        self.assertIn("实际执行", result.explanation)
        self.assertIn("不能自动证明", result.explanation)

    def test_english_intent_produces_english_validation_text(self):
        executor = FakeL1Executor()
        validator = QASMValidator(executor=executor)
        intent = AgentIntent(
            task_type="generate_qasm",
            user_goal="Generate a three-qubit GHZ state",
            response_language="en",
            circuit={"target_state": "ghz", "qubits": 3, "measure_all": True},
        )

        result = validator.validate(GHZ_QASM, intent)

        self.assertTrue(result.ok)
        self.assertIn("Executed 4096 shots", result.explanation)
        self.assertIn("fidelity is 1.000000", result.explanation)
        self.assertNotIn("实际执行", result.explanation)

    def test_measure_all_requires_all_qubits_before_execution(self):
        executor = FakeL1Executor()
        validator = QASMValidator(executor=executor)
        partial = GHZ_QASM.replace("measure q -> c;", "measure q[0] -> c[0];")

        result = validator.validate(partial, self.intent())

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "intent_mismatch")
        self.assertEqual(len(executor.calls), 1)

    def test_runner_dependency_failure_is_not_sent_back_as_a_qasm_repair(self):
        executor = FakeL1Executor(error=ModuleNotFoundError("No module named spinqit"))
        validator = QASMValidator(executor=executor)

        result = validator.validate(GHZ_QASM, self.intent())

        self.assertFalse(result.ok)
        self.assertFalse(result.repairable)
        self.assertIn("spinqit", result.explanation)


class RepairingMockLLM:
    def __init__(self):
        self.repair_calls = []

    def understand(self, _prompt):
        return AgentIntent(
            task_type="generate_qasm",
            user_goal="生成三比特 GHZ 态",
            candidate_qasm=WRONG_GHZ_QASM,
            circuit={"target_state": "ghz", "qubits": 3, "measure_all": True},
        )

    def repair_qasm(self, **arguments):
        self.repair_calls.append(arguments)
        return GHZ_QASM


class SequencedExecutor:
    def __init__(self):
        self.calls = 0

    def __call__(self, _qasm, target, shots):
        self.calls += 1
        counts = (
            {"000": shots // 2, "001": shots - shots // 2}
            if self.calls == 1
            else {"000": shots // 2, "111": shots - shots // 2}
        )
        return {
            "backend": target,
            "job_id": "local-job-%d" % self.calls,
            "shots": shots,
            "counts": counts,
            "bit_order": "little",
        }


class L1ExecutionRepairFlowTests(unittest.TestCase):
    def test_bad_real_counts_trigger_one_repair_then_a_second_execution(self):
        llm = RepairingMockLLM()
        executor = SequencedExecutor()
        context = AgentContext(
            llm=llm,
            backend_selector=CapabilityBackendSelector(),
            validator=QASMValidator(executor=executor),
        )

        reply = AgentEngine(context, default_registry()).respond("生成三比特 GHZ 态")

        self.assertEqual(executor.calls, 2)
        self.assertEqual(len(llm.repair_calls), 1)
        self.assertIn("Fidelity 为 0.292893", llm.repair_calls[0]["validation_error"])
        self.assertIn("L1 spinq 本地模拟器实际执行", reply)
        self.assertIn("Fidelity 为 1.000000", reply)


if __name__ == "__main__":
    unittest.main()
