import unittest
from unittest import mock

from starter_kit import adapter


class L2AgentTests(unittest.TestCase):
    def call_agent_with_fake_llm(self, prompt):
        response = {"choices": [{"message": {"role": "assistant", "content": "model called"}}]}
        with mock.patch.object(adapter.llm_client, "chat_completion", return_value=response) as mocked:
            reply = adapter.agent_chat(prompt)
        mocked.assert_called_once()
        return reply

    def test_agent_generates_ghz_qasm_after_model_call(self):
        reply = self.call_agent_with_fake_llm("生成一个 3 比特 GHZ 态并进行全测量")

        self.assertIn("model called", reply)
        self.assertIn("你想做的是", reply)
        self.assertIn("OPENQASM 2.0;", reply)
        self.assertIn("qreg q[3];", reply)
        self.assertIn("cx q[1], q[2];", reply)
        self.assertIn("measure q -> c;", reply)
        self.assertIn("我已经用本地 L1 模拟器运行了 1000 次", reply)
        self.assertIn("人话解释", reply)

    def test_agent_repairs_bell_intent_after_model_call(self):
        reply = self.call_agent_with_fake_llm("我想制备一个贝尔态，但 H q[0]; CX q[0] q[1] 报错")

        self.assertIn("只修复一次", reply)
        self.assertIn("通过 LoomQ L1 检查", reply)
        self.assertIn("OPENQASM 2.0;", reply)
        self.assertIn("qreg q[2];", reply)
        self.assertIn("h q[0];", reply)
        self.assertIn("cx q[0], q[1];", reply)
        self.assertIn("00", reply)
        self.assertIn("11", reply)

    def test_agent_explains_two_quantum_coins_in_plain_language(self):
        reply = self.call_agent_with_fake_llm("我想让两枚量子硬币最后总是一样")

        self.assertIn("两枚量子硬币保持一致", reply)
        self.assertIn("qreg q[2];", reply)
        self.assertIn("运行了 1000 次", reply)
        self.assertIn("测量结果保持一致", reply)

    def test_agent_recommends_backend_identifier_after_model_call(self):
        reply = self.call_agent_with_fake_llm("我需要运行一个 15 比特电路，且零排队等待，选哪个平台？")

        self.assertIn("spinq_taurus_simulator", reply)
        self.assertIn("originq_local_simulator", reply)
        self.assertIn("braket_local_simulator", reply)

    def test_agent_recommends_no_account_backend_identifier(self):
        reply = self.call_agent_with_fake_llm("我要运行一个 15 比特电路，不想排队、不想付费，也不想注册")

        self.assertIn("spinq_taurus_simulator", reply)
        self.assertIn("originq_local_simulator", reply)
        self.assertIn("braket_local_simulator", reply)
        self.assertNotIn("originq_wukong", reply)

    def test_agent_handles_hidden_variant_four_qubit_global_correlation(self):
        reply = self.call_agent_with_fake_llm("请准备 4 个量子位的全局关联态，然后全部测量")

        self.assertIn("qreg q[4];", reply)
        self.assertIn("creg c[4];", reply)
        self.assertIn("cx q[2], q[3];", reply)
        self.assertIn("measure q -> c;", reply)
        self.assertIn("0000", reply)
        self.assertIn("1111", reply)

    def test_agent_repairs_three_qubit_ghz_steps(self):
        reply = self.call_agent_with_fake_llm(
            "我想修复一个 3 比特 GHZ 实验：H q[0]; CX q[0] q[1]; CX q[1] q[2]"
        )

        self.assertIn("只修复一次", reply)
        self.assertIn("qreg q[3];", reply)
        self.assertIn("cx q[1], q[2];", reply)
        self.assertIn("000", reply)
        self.assertIn("111", reply)

    def test_agent_recommends_backend_for_english_constraints(self):
        reply = self.call_agent_with_fake_llm("Need 15 qubits, no queue, free, no account. Which backend id?")

        self.assertIn("spinq_taurus_simulator", reply)
        self.assertIn("originq_local_simulator", reply)
        self.assertIn("braket_local_simulator", reply)
        self.assertNotIn("originq_wukong", reply)
        self.assertNotIn("braket_cloud", reply)

    def test_agent_reports_no_backend_when_constraints_conflict(self):
        reply = self.call_agent_with_fake_llm("我需要 20 比特真实量子硬件，还要免费并且不用排队")

        self.assertIn("没有后端同时满足", reply)


if __name__ == "__main__":
    unittest.main()
