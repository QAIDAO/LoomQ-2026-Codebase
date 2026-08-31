import unittest

from starter_kit.loomq.agent.service import handle_prompt


class LoomQLabServiceTests(unittest.TestCase):
    def test_random_lesson_runs_one_qubit_experiment(self):
        result = handle_prompt("电脑能不能像掷硬币一样，随机给出 0 或 1？")

        self.assertEqual(result["mode"], "experiment")
        self.assertEqual(result["kind"], "random")
        self.assertIn("随机", result["title"])
        self.assertIn("OPENQASM 2.0;", result["qasm"])
        self.assertEqual(result["backend"], "spinq_local_simulator")
        self.assertEqual(sum(row["count"] for row in result["counts"]), 1000)
        self.assertEqual({row["state"] for row in result["counts"]}, {"0", "1"})
        self.assertIn("概率", result["explanation"])

    def test_association_lesson_runs_bell_experiment(self):
        result = handle_prompt("两个量子结果能不能产生特别的联系？")

        self.assertEqual(result["mode"], "experiment")
        self.assertEqual(result["kind"], "bell")
        self.assertIn("联系", result["title"])
        self.assertEqual(sum(row["count"] for row in result["counts"]), 1000)
        self.assertEqual({row["state"] for row in result["counts"]}, {"00", "11"})
        self.assertIn("成对出现", result["explanation"])
        self.assertIn("Bell 态", result["explanation_blocks"][0]["body"])

    def test_beginner_entanglement_prompt_runs_bell_experiment(self):
        result = handle_prompt("我完全不懂量子，带我完成一个最简单的纠缠实验。")

        self.assertEqual(result["mode"], "experiment")
        self.assertEqual(result["kind"], "bell")
        self.assertEqual({row["state"] for row in result["counts"]}, {"00", "11"})
        self.assertEqual(len(result["platforms"]), 3)

    def test_search_lesson_is_marked_as_preview_only(self):
        result = handle_prompt("量子方法能不能帮助我们搜索隐藏答案？")

        self.assertEqual(result["mode"], "preview")
        self.assertIn("搜索", result["title"])
        self.assertNotIn("qasm", result)
        self.assertIn("不假装", result["observation"])

    def test_backend_prompt_returns_program_selected_backends(self):
        result = handle_prompt("我有一个 15 比特实验，希望免费并且零排队，推荐运行平台")

        backend_ids = {backend["id"] for backend in result["backends"]}
        self.assertEqual(result["mode"], "backend")
        self.assertIn("spinq_taurus_simulator", backend_ids)
        self.assertIn("originq_local_simulator", backend_ids)
        self.assertIn("braket_local_simulator", backend_ids)

    def test_backend_prompt_understands_no_queue_plain_language(self):
        result = handle_prompt("我有一个 15 个位置的实验，希望免费、不要排队，应该去哪里试？")

        backend_ids = {backend["id"] for backend in result["backends"]}
        self.assertIn("spinq_taurus_simulator", backend_ids)
        self.assertIn("originq_local_simulator", backend_ids)
        self.assertIn("braket_local_simulator", backend_ids)
        self.assertNotIn("originq_wukong", backend_ids)

    def test_steps_prompt_returns_repaired_runnable_qasm(self):
        result = handle_prompt("帮我看懂并改好这段步骤：H q[0]; CX q[0] q[1]")

        self.assertEqual(result["mode"], "repair")
        self.assertIn("qreg q[2];", result["qasm"])
        self.assertEqual(sum(row["count"] for row in result["counts"]), 1000)


if __name__ == "__main__":
    unittest.main()
