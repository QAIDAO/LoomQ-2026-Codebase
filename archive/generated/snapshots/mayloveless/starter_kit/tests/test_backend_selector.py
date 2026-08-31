"""Task 11C tests for deterministic backend selection."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import adapter
from loomq.backend_selector import (
    BackendCapabilityError,
    BackendConstraints,
    load_backends,
    load_capability_version,
    select_backends,
)


def constraints(
    *,
    min_qubits=None,
    require_qpu=None,
    require_no_queue=False,
    cost_policy="unspecified",
    allow_account_required=None,
):
    return BackendConstraints(
        min_qubits=min_qubits,
        require_qpu=require_qpu,
        require_no_queue=require_no_queue,
        cost_policy=cost_policy,
        allow_account_required=allow_account_required,
    )


def backend_ids(selected):
    return [backend.id for backend in selected]


def completion_for_backend_selection(backend_constraints, **extra):
    payload = {
        "task_type": "select_backend",
        "qasm": None,
        "backend_constraints": backend_constraints,
        "explanation": "已提取后端约束。",
    }
    payload.update(extra)
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


class BackendSelectorTests(unittest.TestCase):
    def test_fifteen_qubits_and_no_queue_returns_all_matches_in_table_order(self):
        selected = select_backends(
            constraints(min_qubits=15, require_no_queue=True)
        )
        self.assertEqual(
            backend_ids(selected),
            [
                "spinq_taurus_simulator",
                "originq_local_simulator",
                "braket_local_simulator",
            ],
        )

    def test_qpu_five_qubits_and_free_or_quota(self):
        selected = select_backends(
            constraints(
                min_qubits=5,
                require_qpu=True,
                cost_policy="free_or_quota",
            )
        )
        self.assertEqual(
            backend_ids(selected),
            ["spinq_cloud_qpu", "originq_wukong"],
        )
        self.assertTrue(all(backend.kind == "qpu" for backend in selected))

    def test_free_only_and_no_account_excludes_quota_and_account_backends(self):
        selected = select_backends(
            constraints(
                cost_policy="free_only",
                allow_account_required=False,
            )
        )
        self.assertEqual(
            backend_ids(selected),
            [
                "spinq_taurus_simulator",
                "originq_local_simulator",
                "braket_local_simulator",
            ],
        )

    def test_paid_allowed_does_not_exclude_paid_backend(self):
        selected = select_backends(
            constraints(min_qubits=30, cost_policy="paid_allowed")
        )
        self.assertEqual(
            backend_ids(selected),
            ["originq_local_simulator", "originq_wukong", "braket_cloud"],
        )

    def test_more_than_table_maximum_has_no_match(self):
        self.assertEqual(select_backends(constraints(min_qubits=73)), ())

    def test_qpu_and_no_queue_has_no_match(self):
        self.assertEqual(
            select_backends(
                constraints(require_qpu=True, require_no_queue=True)
            ),
            (),
        )

    def test_default_capability_path_does_not_depend_on_working_directory(self):
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temporary_directory:
            try:
                os.chdir(temporary_directory)
                loaded = load_backends()
            finally:
                os.chdir(original_cwd)
        self.assertEqual(loaded[0].id, "spinq_taurus_simulator")

    def test_capability_version_comes_from_the_same_json_snapshot(self):
        self.assertEqual(load_capability_version(), "2026-07")

    def test_missing_required_capability_field_fails_clearly(self):
        malformed = {
            "backends": [
                {
                    "id": "test_backend",
                    "kind": "simulator",
                    "max_qubits": 2,
                    "queue": "none",
                    "cost": "free",
                    "requires_account": False,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "capabilities.json"
            path.write_text(json.dumps(malformed), encoding="utf-8")
            with self.assertRaisesRegex(BackendCapabilityError, "missing field.*name"):
                load_backends(path)

    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_missing_model_constraint_field_fails_stably(self, chat):
        chat.return_value = completion_for_backend_selection(
            {
                "min_qubits": 15,
                "require_qpu": None,
                "require_no_queue": True,
                "cost_policy": "unspecified",
            }
        )

        with self.assertRaisesRegex(RuntimeError, "missing field.*allow_account"):
            adapter.agent_chat("需要 15 比特且零排队的后端")
        chat.assert_called_once()

    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_model_constraint_types_are_not_coerced(self, chat):
        invalid_values = (
            ("min_qubits", "20"),
            ("require_qpu", "false"),
            ("require_no_queue", 1),
            ("allow_account_required", "no"),
        )
        for field, value in invalid_values:
            with self.subTest(field=field, value=value):
                chat.reset_mock()
                raw = {
                    "min_qubits": 20,
                    "require_qpu": False,
                    "require_no_queue": True,
                    "cost_policy": "free_only",
                    "allow_account_required": False,
                }
                raw[field] = value
                chat.return_value = completion_for_backend_selection(raw)
                with self.assertRaisesRegex(RuntimeError, "invalid constraints"):
                    adapter.agent_chat("至少 20 比特、免费且零排队")
                chat.assert_called_once()

    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_agent_ignores_model_backend_id_and_calls_model_once(self, chat):
        chat.return_value = completion_for_backend_selection(
            {
                "min_qubits": 15,
                "require_qpu": False,
                "require_no_queue": True,
                "cost_policy": "unspecified",
                "allow_account_required": True,
            },
            backend_id="originq_wukong",
        )

        reply = adapter.agent_chat("需要 15 比特且零排队的后端")

        chat.assert_called_once()
        self.assertIn("spinq_taurus_simulator", reply)
        self.assertIn("originq_local_simulator", reply)
        self.assertIn("braket_local_simulator", reply)
        self.assertNotIn("originq_wukong", reply)
        system_prompt = chat.call_args.args[0][0]["content"]
        self.assertIn("不要推荐或输出 backend ID", system_prompt)

    @mock.patch("loomq.l2_agent.llm_client.chat_completion")
    def test_agent_reports_no_solution_without_inventing_backend(self, chat):
        chat.return_value = completion_for_backend_selection(
            {
                "min_qubits": 73,
                "require_qpu": True,
                "require_no_queue": True,
                "cost_policy": "free_only",
                "allow_account_required": False,
            }
        )

        reply = adapter.agent_chat("73 比特真机，零排队、完全免费且无需账号")

        chat.assert_called_once()
        self.assertIn("没有满足全部条件", reply)
        self.assertIn("比特数", reply)
        self.assertIn("真机", reply)
        for backend in load_backends():
            self.assertNotIn(backend.id, reply)


if __name__ == "__main__":
    unittest.main()
