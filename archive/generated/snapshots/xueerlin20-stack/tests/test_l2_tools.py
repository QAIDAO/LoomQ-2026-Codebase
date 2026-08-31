import unittest

from starter_kit.l2_agent import AgentContext, AgentEngine, AgentIntent, default_registry
from starter_kit.l2_agent.tools import CapabilityBackendSelector


class RealBackendSelectorTests(unittest.TestCase):
    def setUp(self):
        self.selector = CapabilityBackendSelector()

    def test_fifteen_qubits_without_queue_returns_all_local_options(self):
        selection = self.selector.select({"min_qubits": 15, "queue": "none"})

        self.assertEqual(selection.selected_id, "spinq_taurus_simulator")
        self.assertEqual(
            set([selection.selected_id] + selection.alternatives),
            {
                "spinq_taurus_simulator",
                "originq_local_simulator",
                "braket_local_simulator",
            },
        )

    def test_twelve_qubits_free_without_queue_has_three_valid_local_options(self):
        selection = self.selector.select(
            {"min_qubits": 12, "queue": "none", "cost": "free"}
        )

        self.assertEqual(selection.selected_id, "spinq_taurus_simulator")
        self.assertEqual(
            set([selection.selected_id] + selection.alternatives),
            {
                "spinq_taurus_simulator",
                "originq_local_simulator",
                "braket_local_simulator",
            },
        )

    def test_twenty_six_qubits_free_without_queue_selects_originq_local(self):
        selection = self.selector.select(
            {"min_qubits": 26, "queue": "none", "cost": "free"}
        )

        self.assertEqual(selection.selected_id, "originq_local_simulator")
        self.assertEqual(selection.alternatives, [])

    def test_real_hardware_with_no_paid_cost_returns_free_quota_qpus(self):
        selection = self.selector.select(
            {"min_qubits": 5, "kind": "qpu", "cost": "not_paid"}
        )

        self.assertEqual(selection.selected_id, "spinq_cloud_qpu")
        self.assertEqual(selection.alternatives, ["originq_wukong"])

    def test_paid_constraint_selects_braket_cloud(self):
        selection = self.selector.select({"cost": "paid"})

        self.assertEqual(selection.selected_id, "braket_cloud")

    def test_impossible_qubit_count_reports_no_match(self):
        selection = self.selector.select({"min_qubits": 73})

        self.assertIsNone(selection.selected_id)
        self.assertIn("没有满足", selection.explanation)
        self.assertTrue(selection.alternatives)

    def test_unknown_constraint_is_rejected_instead_of_ignored(self):
        with self.assertRaisesRegex(ValueError, "unsupported backend constraint"):
            self.selector.select({"fastest": True})

    def test_invalid_constraint_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            self.selector.select({"min_qubits": "20"})


class MockLLMWithRealTools:
    def __init__(self, intent):
        self.intent = intent
        self.understand_count = 0

    def understand(self, _prompt):
        self.understand_count += 1
        return self.intent

    def repair_qasm(self, **_arguments):
        raise AssertionError("valid test QASM must not trigger model repair")


class UnusedQASMValidator:
    def validate(self, _qasm, _intent):
        raise AssertionError("backend recommendation must not run a circuit")


class AgentWithRealToolsTests(unittest.TestCase):
    def test_mock_model_and_real_selector_complete_the_agent_flow(self):
        llm = MockLLMWithRealTools(
            AgentIntent(
                task_type="recommend_backend",
                user_goal="26 比特、免费、无排队",
                backend_constraints={
                    "min_qubits": 26,
                    "queue": "none",
                    "cost": "free",
                },
            )
        )
        context = AgentContext(
            llm=llm,
            backend_selector=CapabilityBackendSelector(),
            validator=UnusedQASMValidator(),
        )

        reply = AgentEngine(context, default_registry()).respond(
            "运行 26 比特电路，必须免费且不能排队"
        )

        self.assertEqual(llm.understand_count, 1)
        self.assertIn("originq_local_simulator", reply)


if __name__ == "__main__":
    unittest.main()
