"""Private-evaluator-shaped L2 paraphrase and recovery stress tests."""

import unittest
from unittest import mock

from starter_kit import agent_engine


def completion(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def ghz_qasm(width):
    lines = [
        "OPENQASM 2.0;", 'include "qelib1.inc";',
        f"qreg q[{width}];", f"creg c[{width}];", "h q[0];",
    ]
    lines.extend(f"cx q[{index - 1}], q[{index}];" for index in range(1, width))
    lines.append("measure q -> c;")
    return "\n".join(lines)


class BackendParaphraseStressTests(unittest.TestCase):
    CASES = (
        ("Run 15 qubits without any waiting",
         {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
        ("Which service can run 25 qubits locally at no charge without signup?",
         {"originq_local_simulator", "braket_local_simulator"}),
        ("I don't need real hardware; use a free 30-qubit simulator",
         {"originq_local_simulator"}),
        ("Avoid local execution; use an AWS managed cloud backend for 30 qubits",
         {"braket_cloud"}),
        ("Use a cloud simulator for 30 qubits", {"braket_cloud"}),
        ("30 比特云端模拟器，付费和注册都可以", {"braket_cloud"}),
        ("不要真机，30 个量子比特，用模拟方式执行", {"originq_local_simulator"}),
        ("不要本地，30 比特，选一个 AWS 云服务", {"braket_cloud"}),
        ("我不要求免费，30 比特云服务即可", {"braket_cloud"}),
        ("15 qubits; free is not required; zero queue",
         {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
        ("Which device should handle a 73-qubit circuit?", set()),
        ("Where should I execute 5 qubits on physical quantum hardware at no charge?",
         {"spinq_cloud_qpu", "originq_wukong"}),
        ("推荐一个无需登录且马上能跑 25 量子位线路的执行环境",
         {"originq_local_simulator", "braket_local_simulator"}),
        ("24 量子位，可以等，但必须是模拟环境",
         {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
        ("需要至少 30 qubits of capacity on Origin Quantum with no waiting",
         {"originq_local_simulator"}),
        ("I need a 25-qubit emulation service, no registration and zero latency",
         {"originq_local_simulator", "braket_local_simulator"}),
        ("I don't want a simulator; run five qubits on hardware for free",
         {"spinq_cloud_qpu", "originq_wukong"}),
        ("Avoid AWS; use a 24-qubit local simulator",
         {"spinq_taurus_simulator", "originq_local_simulator"}),
        ("不要使用量旋，25 量子位、本地、免费",
         {"originq_local_simulator", "braket_local_simulator"}),
        ("50 qubits，选择一个后端", {"originq_wukong"}),
        ("AWS LocalSimulator for twenty five qubits without an account",
         {"braket_local_simulator"}),
        ("AWS cloud, capacity=34", {"braket_cloud"}),
        ("AWS cloud, capacity=35", set()),
        ("8 比特真机，但不可以注册", set()),
        ("30 qubits in the cloud with no user account", set()),
        ("不可以等，不可以付费，5 比特真机",
         set()),
        ("Where can I run eight quantum bits on a physical quantum processor without paying?",
         {"spinq_cloud_qpu", "originq_wukong"}),
        ("Select a hosted option for thirty-four qubits; paid is acceptable and I can register.",
         {"braket_cloud"}),
        ("三十量子比特，排除云端和量旋，选择本地仿真。",
         {"originq_local_simulator"}),
    )

    def test_constraint_matrix(self):
        for prompt, expected in self.CASES:
            with self.subTest(prompt=prompt):
                self.assertTrue(agent_engine._is_backend_task(prompt))
                self.assertEqual(set(agent_engine.compatible_backends(prompt)), expected)

    def test_paraphrased_selection_is_sanitized_after_two_bad_model_answers(self):
        responses = [completion("I am unsure."), completion("Still unsure.")]
        with mock.patch.object(agent_engine, "chat_completion", side_effect=responses) as call:
            answer = agent_engine.agent_chat(
                "Which service can run twenty five qubits locally at no charge without signup?"
            )
        self.assertEqual(call.call_count, 2)
        self.assertIn("braket_local_simulator", answer)


class GenerationRepairStressTests(unittest.TestCase):
    def test_qubit_count_paraphrases(self):
        cases = {
            "生成四比特 GHZ 态": 4,
            "二十五量子位线路": 25,
            "a thirty-qubit circuit": 30,
            "twenty five qubits": 25,
            "capacity=34": 34,
        }
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                self.assertEqual(agent_engine._requested_qubits(prompt), expected)

    def test_named_state_aliases_drive_semantic_validation(self):
        wrong_four = ghz_qasm(4).replace("h q[0];", "x q[0];")
        cases = (
            ("Prepare an EPR pair and measure both qubits", ghz_qasm(2), None),
            ("Create a four-qubit cat state with measurements", wrong_four, "fidelity"),
            ("生成四比特最大纠缠态并进行全测量", wrong_four, "fidelity"),
            ("start in |000>, then prepare a three-qubit GHZ state and measure", ghz_qasm(3), None),
        )
        for prompt, qasm, expected_issue in cases:
            with self.subTest(prompt=prompt):
                issue = agent_engine.validate_qasm(prompt, qasm)
                if expected_issue is None:
                    self.assertIsNone(issue)
                else:
                    self.assertIn(expected_issue, issue)

    def test_missing_measurement_is_rejected(self):
        qasm = ghz_qasm(3).replace("measure q -> c;", "")
        issue = agent_engine.validate_qasm("Generate a 3-qubit GHZ state and measure all outputs", qasm)
        self.assertIn("no measure instruction", issue)

    def test_validated_fallback_recovers_when_model_fails_twice(self):
        responses = [completion("I cannot produce QASM."), completion("Still no circuit.")]
        prompt = "请生成四比特 GHZ 态并进行全测量"
        with mock.patch.object(agent_engine, "chat_completion", side_effect=responses) as call:
            answer = agent_engine.agent_chat(prompt)
        self.assertEqual(call.call_count, 2)
        qasm = agent_engine.extract_qasm(answer)
        self.assertIsNotNone(qasm)
        self.assertIsNone(agent_engine.validate_qasm(prompt, qasm))

    def test_model_qasm_is_normalized_for_strict_downstream_extractors(self):
        mixed_case = """```qasm
OpenQASM 2.0;
QREG q[2];
CREG c[2];
H q[0];
CX q[0], q[1];
MEASURE q -> c;
```"""
        with mock.patch.object(agent_engine, "chat_completion", return_value=completion(mixed_case)):
            answer = agent_engine.agent_chat("Prepare and measure a Bell pair")
        self.assertIn("OPENQASM 2.0;", answer)
        self.assertIn("h q[0];", answer)
        self.assertNotIn("QREG", answer)

    def test_hardware_word_does_not_turn_generation_into_backend_selection(self):
        prompts = (
            "Generate and measure a Bell circuit for a quantum hardware tutorial",
            "Choose suitable gates to prepare a Bell pair",
            "请选择合适的量子门生成 GHZ 态",
            "Select a repair strategy for this broken QASM",
        )
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertFalse(agent_engine._is_backend_task(prompt))

    def test_extreme_uniform_request_does_not_materialize_exponential_expected_map(self):
        self.assertIsNone(agent_engine._target_distribution(
            "Generate a uniform superposition across 20 qubits and measure it"
        ))


if __name__ == "__main__":
    unittest.main()
