import unittest

try:
    from starter_kit.loomq_agent.backend_selector import format_selection, select_backends
except ModuleNotFoundError:
    from loomq_agent.backend_selector import format_selection, select_backends


class BackendSelectorTests(unittest.TestCase):
    def test_zero_queue_filters_all_matching_local_simulators(self):
        selection = select_backends("15 比特电路必须零排队，推荐后端")
        self.assertEqual(
            {item["id"] for item in selection.candidates},
            {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"},
        )

    def test_free_quota_satisfies_non_paid_qpu_requirement(self):
        selection = select_backends("5 比特必须上真实量子硬件而且不能付费")
        self.assertEqual(
            {item["id"] for item in selection.candidates},
            {"spinq_cloud_qpu", "originq_wukong"},
        )

    def test_local_no_account_constraint(self):
        selection = select_backends("本地运行 28 比特，不注册账号，选哪个平台")
        self.assertEqual(
            [item["id"] for item in selection.candidates],
            ["originq_local_simulator"],
        )

    def test_no_solution_has_relaxed_alternative(self):
        selection = select_backends("40 比特且零排队，是否有后端？")
        answer = format_selection("40 比特且零排队，是否有后端？", selection)
        self.assertFalse(selection.candidates)
        self.assertIn("没有后端满足", answer)
        self.assertIn("originq_wukong", answer)


if __name__ == "__main__":
    unittest.main()
