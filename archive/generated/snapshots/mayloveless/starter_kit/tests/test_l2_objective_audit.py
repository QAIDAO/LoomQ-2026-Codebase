"""Task 15B case-set and unavailable benchmark tests."""

from collections import Counter
import json
import os
import unittest
from unittest import mock

import llm_client
from loomq.backend_selector import select_backends
from loomq.semantic_verifier import (
    SemanticVerificationResult,
    parse_target_specification,
)
import scripts.audit_l2_objective as audit_module
from scripts.audit_l2_objective import (
    AUDIT_CASES,
    CASE_SET_VERSION,
    build_report,
)


class L2ObjectiveCaseSetTests(unittest.TestCase):
    def test_versioned_case_set_has_exactly_four_cases_per_task(self):
        self.assertEqual(CASE_SET_VERSION, "l2-hidden-like-2026-08-20-v1")
        self.assertEqual(len(AUDIT_CASES), 12)
        self.assertEqual(
            Counter(case.task_type for case in AUDIT_CASES),
            {
                "generate_qasm": 4,
                "repair_qasm": 4,
                "select_backend": 4,
            },
        )
        self.assertEqual(len({case.case_id for case in AUDIT_CASES}), 12)

    def test_all_qasm_expectations_are_independent_normalized_pure_states(self):
        qasm_cases = [
            case for case in AUDIT_CASES if case.task_type != "select_backend"
        ]
        self.assertEqual(len(qasm_cases), 8)
        for case in qasm_cases:
            with self.subTest(case_id=case.case_id):
                target = parse_target_specification(case.expected_target_payload)
                self.assertEqual(target.verification_mode, "statevector")
                self.assertTrue(target.pure_state_requested)

    def test_measurement_expectations_cover_required_and_forbidden(self):
        policies = Counter(
            case.measurement_policy
            for case in AUDIT_CASES
            if case.task_type != "select_backend"
        )
        self.assertGreaterEqual(policies["required"], 3)
        self.assertGreaterEqual(policies["forbidden"], 2)

    def test_backend_expected_ids_come_from_local_capability_table(self):
        cases = {
            case.case_id: case
            for case in AUDIT_CASES
            if case.task_type == "select_backend"
        }
        actual = {
            case_id: [
                backend.id
                for backend in select_backends(case.expected_backend_constraints)
            ]
            for case_id, case in cases.items()
        }
        self.assertEqual(
            actual,
            {
                "backend_negative_constraints": [
                    "spinq_taurus_simulator",
                    "originq_local_simulator",
                    "braket_local_simulator",
                ],
                "backend_qpu_free_quota": [
                    "spinq_cloud_qpu",
                    "originq_wukong",
                ],
                "backend_25q_no_account_no_queue": [
                    "originq_local_simulator",
                    "braket_local_simulator",
                ],
                "backend_qpu_no_queue_no_match": [],
            },
        )

    def test_missing_real_model_environment_is_explicitly_pending(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            report = build_report()

        self.assertEqual(report["status"], "SKIP")
        self.assertEqual(report["availability"], "unavailable")
        self.assertEqual(report["summary"]["pending"], 12)
        self.assertEqual(len(report["cases"]), 12)
        self.assertTrue(all(case["status"] == "SKIP" for case in report["cases"]))
        self.assertTrue(all(case["llm_calls"] == 0 for case in report["cases"]))
        rendered = json.dumps(report)
        self.assertNotIn("LOOMQ_LLM_API_KEY", rendered)
        self.assertNotIn("Authorization", rendered)

    def test_all_twelve_cases_run_through_deterministic_fake_transport(self):
        bell = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];"""
        bell_measured = bell.replace(
            "qreg q[2];",
            "qreg q[2];\ncreg c[2];",
        ) + "\nmeasure q -> c;"
        bell_minus = bell + "\ns q[0];\ns q[0];"
        ghz_measured = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
measure q -> c;"""
        basis_01 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
x q[1];"""
        basis_10_measured = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[0];
measure q -> c;"""
        qasm_by_case = {
            "generate_epr_correlated_measurement": bell_measured,
            "generate_bell_minus_phase_offset": bell_minus,
            "generate_ghz_three_readout": ghz_measured,
            "generate_explicit_basis_ket": basis_01,
            "repair_syntax_preserve_epr": bell_measured,
            "repair_semantic_wrong_cx_direction": bell,
            "repair_relative_phase_sign": bell_minus,
            "repair_missing_required_measurement": basis_10_measured,
        }
        repository = {"source_commit": "fake-source-sha", "dirty": False}

        for case in AUDIT_CASES:
            with self.subTest(case_id=case.case_id):
                if case.task_type == "select_backend":
                    constraints = case.expected_backend_constraints
                    payload = {
                        "task_type": "select_backend",
                        "qasm": None,
                        "backend_constraints": {
                            "min_qubits": constraints.min_qubits,
                            "require_qpu": constraints.require_qpu,
                            "require_no_queue": constraints.require_no_queue,
                            "cost_policy": constraints.cost_policy,
                            "allow_account_required": (
                                constraints.allow_account_required
                            ),
                        },
                        "explanation": "fake constraints",
                    }
                    responses = [
                        {
                            "choices": [
                                {"message": {"content": json.dumps(payload)}}
                            ]
                        }
                    ]
                    expected_calls = 1
                else:
                    candidate_payload = {
                        "task_type": case.task_type,
                        "qasm": qasm_by_case[case.case_id],
                        "explanation": "fake candidate",
                    }
                    candidate_content = json.dumps(candidate_payload)
                    if case.case_id == "generate_bell_minus_phase_offset":
                        candidate_content = "```json\n%s\n```" % candidate_content
                    responses = [
                        {"choices": [{"message": {"content": candidate_content}}]},
                        {
                            "choices": [
                                {
                                    "message": {
                                        "content": json.dumps(
                                            case.expected_target_payload
                                        )
                                    }
                                }
                            ]
                        },
                    ]
                    expected_calls = 2

                with mock.patch.object(
                    llm_client,
                    "chat_completion",
                    side_effect=responses,
                ) as fake_transport, mock.patch(
                    "loomq.l2_agent.verify_semantics",
                    return_value=SemanticVerificationResult(
                        1.0, True, "statevector"
                    ),
                ), mock.patch.object(
                    audit_module,
                    "verify_semantics",
                    return_value=SemanticVerificationResult(
                        1.0, True, "statevector"
                    ),
                ):
                    result = audit_module._run_real_case(
                        case,
                        repository,
                        "fake-model",
                    )

                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["llm_calls"], expected_calls)
                self.assertLessEqual(fake_transport.call_count, 3)


if __name__ == "__main__":
    unittest.main()
