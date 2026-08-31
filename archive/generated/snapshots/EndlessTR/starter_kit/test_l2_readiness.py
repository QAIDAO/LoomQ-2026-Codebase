import json
import unittest
from pathlib import Path
from unittest import mock

if __package__:
    from . import adapter
else:
    import adapter


STARTER_KIT = Path(__file__).resolve().parent


def model_response(payload):
    return {
        "choices": [
            {"message": {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)}}
        ]
    }


class L2SubmissionReadinessTests(unittest.TestCase):
    def test_manifest_enables_l2_and_its_network(self):
        manifest = (STARTER_KIT / "submission.yaml").read_text(encoding="utf-8")
        levels = manifest.split("levels:", 1)[1].split("runtime:", 1)[0]
        network = manifest.split("network:", 1)[1].split("l2_runtime:", 1)[0]
        self.assertIn("l2: true", levels)
        self.assertIn("required_for_l2: true", network)

    def test_backend_metadata_is_complete_and_loadable(self):
        adapter._load_backend_metadata.cache_clear()
        adapter.load_backends.cache_clear()
        backends = adapter.load_backends()
        self.assertEqual(len(backends), 6)
        self.assertEqual(sum(backend.is_default for backend in backends), 1)
        self.assertEqual(
            adapter.select_backend_from_request(
                adapter.BackendRequest(required_qubits=30, queue_exact="none")
            ).id,
            "originq_local_simulator",
        )

    def test_schema_repair_uses_only_remaining_case_budget(self):
        invalid = {"choices": [{"message": {"content": "not-json"}}]}
        valid = model_response(
            {
                "task": "backend_selection",
                "backend_request": {
                    "required_qubits": 15,
                    "queue_exact": "none",
                },
                "circuit_request": None,
            }
        )
        with mock.patch.object(adapter, "chat_completion", side_effect=[invalid, valid]) as completion:
            semantic = adapter.parse_l2_semantics("为 15 比特电路选择零排队后端")
        self.assertEqual(semantic.task, "backend_selection")
        self.assertEqual(completion.call_count, 2)
        first = completion.call_args_list[0].kwargs["_request_timeout_seconds"]
        second = completion.call_args_list[1].kwargs["_request_timeout_seconds"]
        self.assertGreater(first, 0)
        self.assertGreater(second, 0)
        self.assertLessEqual(second, first)
        self.assertLessEqual(first, adapter.L2_CASE_BUDGET_SECONDS)

    def test_schema_repair_is_skipped_when_case_budget_is_exhausted(self):
        invalid = {"choices": [{"message": {"content": "not-json"}}]}
        clock = [0.0, 0.1, adapter.L2_CASE_BUDGET_SECONDS - 0.1]
        with mock.patch.object(adapter.time, "monotonic", side_effect=clock), mock.patch.object(
            adapter, "chat_completion", return_value=invalid
        ) as completion:
            with self.assertRaisesRegex(adapter.L2SemanticError, "budget is exhausted"):
                adapter.parse_l2_semantics("为 15 比特电路选择零排队后端")
        self.assertEqual(completion.call_count, 1)

    def test_repeated_identical_semantics_produce_identical_qasm(self):
        response = model_response(
            {
                "task": "natural_language_generation",
                "backend_request": None,
                "circuit_request": {
                    "parse_status": "ok",
                    "intent_type": "named_operation",
                    "operation": "ghz",
                    "num_qubits": 3,
                    "measurement": "all",
                    "operations": [],
                    "ambiguities": [],
                    "grounding_evidence": ["3", "GHZ", "全测量"],
                },
            }
        )
        prompt = "生成一个 3 比特 GHZ 态并进行全测量"
        with mock.patch.object(adapter, "chat_completion", return_value=response) as completion:
            first = adapter.agent_chat(prompt)
            second = adapter.agent_chat(prompt)
        self.assertEqual(first, second)
        self.assertIn("OPENQASM 2.0;", first)
        self.assertEqual(completion.call_count, 2)


if __name__ == "__main__":
    unittest.main()
