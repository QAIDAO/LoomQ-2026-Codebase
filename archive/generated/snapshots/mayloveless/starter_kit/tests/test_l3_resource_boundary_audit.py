"""L3 release resource-boundary audit tests."""

import unittest

from scripts.audit_l3_resource_boundary import (
    ASSEMBLY_SIZE_SENTINEL_BYTES,
    CASE_SET_VERSION,
    COMPILE_TIME_SENTINEL_SECONDS,
    MIN_EXECUTION_MARGIN_STEPS,
    RESOURCE_CASES,
    build_report,
)


class L3ResourceBoundaryAuditTests(unittest.TestCase):
    def test_case_set_is_versioned_and_covers_release_stress_groups(self):
        self.assertEqual(
            CASE_SET_VERSION,
            "l3-resource-boundary-2026-08-20-v1",
        )
        self.assertEqual(len(RESOURCE_CASES), 6)
        self.assertEqual(
            {case.group for case in RESOURCE_CASES},
            {"nested_if", "classical_feedback", "sequential"},
        )
        self.assertEqual(
            {case.nesting_depth for case in RESOURCE_CASES if case.nesting_depth},
            {3, 5, 8},
        )

    def test_audit_passes_semantic_and_resource_checks(self):
        report = build_report()

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(report["summary"]["total"], len(RESOURCE_CASES))
        self.assertGreater(report["summary"]["execution_count"], len(RESOURCE_CASES))
        self.assertLessEqual(
            report["maxima"]["compile_time_seconds"],
            COMPILE_TIME_SENTINEL_SECONDS,
        )
        self.assertLessEqual(
            report["maxima"]["assembly_size_bytes"],
            ASSEMBLY_SIZE_SENTINEL_BYTES,
        )
        self.assertGreaterEqual(
            report["safety_margin"]["execution_steps"],
            MIN_EXECUTION_MARGIN_STEPS,
        )

    def test_each_case_records_compilation_execution_and_differential_evidence(self):
        report = build_report()

        for entry in report["cases"]:
            with self.subTest(case_id=entry["case_id"]):
                self.assertEqual(entry["status"], "PASS")
                self.assertGreater(entry["metrics"]["compile_time_seconds"], 0)
                self.assertGreater(entry["metrics"]["assembly_size_bytes"], 0)
                self.assertGreater(entry["metrics"]["instruction_count"], 0)
                self.assertGreater(entry["metrics"]["execution_count"], 0)
                self.assertGreater(entry["metrics"]["max_execution_steps"], 0)
                self.assertTrue(entry["expected"]["classical_outcomes"])
                self.assertTrue(entry["actual"]["classical_outcomes"])
                self.assertEqual(entry["semantic"]["quantum"], "PASS")
                self.assertEqual(entry["semantic"]["classical"], "PASS")


if __name__ == "__main__":
    unittest.main()
