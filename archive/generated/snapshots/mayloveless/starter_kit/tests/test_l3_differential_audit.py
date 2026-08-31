"""Task 15C tests for the versioned L3 differential audit."""

import unittest

from scripts.audit_l3_differential import (
    CASE_SET_VERSION,
    DETERMINISTIC_CASES,
    RANDOM_CASES,
    build_report,
)


class L3DifferentialAuditTests(unittest.TestCase):
    def test_case_set_is_versioned_and_covers_required_groups(self):
        self.assertEqual(CASE_SET_VERSION, "l3-hidden-like-2026-08-20-v1")
        self.assertGreaterEqual(len(DETERMINISTIC_CASES), 16)
        groups = {case.group for case in DETERMINISTIC_CASES}
        self.assertEqual(
            groups,
            {"basic", "logic", "expression", "hybrid", "boundary"},
        )
        self.assertEqual(
            len({case.case_id for case in DETERMINISTIC_CASES}),
            len(DETERMINISTIC_CASES),
        )

    def test_random_cases_are_small_bounded_and_reproducible(self):
        self.assertEqual(len(RANDOM_CASES), 24)
        self.assertEqual(
            [case.seed for case in RANDOM_CASES],
            [15000 + index for index in range(24)],
        )
        for case in RANDOM_CASES:
            with self.subTest(seed=case.seed):
                self.assertGreaterEqual(case.qubit_count, 1)
                self.assertLessEqual(case.qubit_count, 5)
                self.assertGreaterEqual(case.classical_bit_count, 1)
                self.assertLessEqual(case.classical_bit_count, 3)
                self.assertGreaterEqual(case.quantum_depth, 1)
                self.assertLessEqual(case.quantum_depth, 8)
                self.assertTrue(case.expected_quantum_ops)
                self.assertTrue(case.measurement_inputs)

    def test_full_audit_passes_and_records_semantic_outputs(self):
        report = build_report()

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(
            report["summary"]["total"],
            len(DETERMINISTIC_CASES) + len(RANDOM_CASES),
        )
        self.assertGreater(report["measurement_executions"], len(RANDOM_CASES))
        random_entries = [
            entry for entry in report["cases"] if entry["kind"] == "random"
        ]
        self.assertEqual(len(random_entries), 24)
        for entry in random_entries:
            with self.subTest(seed=entry["seed"]):
                self.assertIn("source", entry)
                self.assertIn("expected", entry)
                self.assertIn("compiled_ir", entry)
                self.assertEqual(entry["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
