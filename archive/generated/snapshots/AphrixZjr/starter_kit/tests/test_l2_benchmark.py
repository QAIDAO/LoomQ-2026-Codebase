import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


STARTER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STARTER))

import loomq_l2
from experiments import l2_live_benchmark, l2_raw_prompt_stress


class L2BenchmarkTests(unittest.TestCase):
    def test_case_sets_match_the_published_three_round_plan(self):
        stress = (
            l2_raw_prompt_stress.qasm_cases()
            + l2_raw_prompt_stress.repair_cases()
            + l2_raw_prompt_stress.backend_cases()
        )
        self.assertEqual(len(l2_raw_prompt_stress.fixed_cases()), 12)
        self.assertEqual(len(stress), 72)
        self.assertEqual(len(l2_raw_prompt_stress.adversarial_backend_cases()), 20)
        self.assertEqual(l2_raw_prompt_stress._parser().parse_args([]).rounds, 3)

    def test_all_adversarial_backend_expectations_match_local_oracle(self):
        empty = {"hard_constraints": {}, "soft_preferences": {}, "forbidden": {}}
        prompts = set()
        for case_id, task, category, prompt, expected in (
            l2_raw_prompt_stress.adversarial_backend_cases()
        ):
            with self.subTest(case_id=case_id):
                self.assertEqual(task, "backend")
                self.assertEqual(category, "backend_adversarial")
                self.assertIn(loomq_l2._select_backend(empty, prompt), expected)
                prompts.add(prompt)
        for required in (
            "Use AWS without an account for 20 qubits.",
            "Use AWS but no paid services for 20 qubits.",
            "I don't want AWS; choose a 25-qubit simulator.",
            "Choose any 25-qubit simulator except AWS.",
            "Run 20 qubits without using AWS.",
            "Use a real machine for 8 qubits.",
            "Use a physical quantum computer for 9 qubits.",
        ):
            self.assertIn(required, prompts)

    def test_live_case_result_carries_agent_budget_metrics(self):
        def fake_agent(_prompt, *, metrics):
            metrics.update({
                "attempts": 1, "repair_attempts": 0, "http_retries": 0,
                "canonical_recoveries": 0, "input_tokens": 42, "output_tokens": 1000,
            })
            return "braket_local_simulator"

        with mock.patch.object(
            l2_live_benchmark, "measured_agent_chat", side_effect=fake_agent
        ):
            result = l2_live_benchmark.run_backend(
                "case", "Use AWS without an account for 20 qubits.",
                {"braket_local_simulator"},
            )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["agent_metrics"]["input_tokens"], 42)
        self.assertEqual(result["agent_metrics"]["output_tokens"], 1000)

    def test_artifacts_bind_raw_stdout_with_sha256(self):
        results = [{
            "case_id": "case", "round": 1, "category": "fixed",
            "status": "PASS", "seconds": 0.1, "agent_metrics": {},
        }]
        summary = {"passed": 1, "failed": 0, "total": 1}
        lines = ["[PASS] case", json.dumps(summary)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_out = root / "report.json"
            stdout_out = root / "raw.stdout.txt"
            l2_raw_prompt_stress._write_artifacts(
                json_out, stdout_out, results, summary, lines
            )
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            raw = stdout_out.read_bytes()
        self.assertEqual(payload["stdout"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(payload["stdout"]["bytes"], len(raw))
        self.assertEqual(payload["results"], results)


if __name__ == "__main__":
    unittest.main()
