"""Backend capability snapshot release preflight tests."""

import unittest
from unittest import mock

from scripts import audit_backend_capability_snapshot as preflight
from scripts.audit_backend_capability_snapshot import (
    CASE_SET_VERSION,
    PINNED_BACKEND_IDS,
    PINNED_CAPABILITY_SHA256,
    PINNED_CAPABILITY_VERSION,
    REGRESSION_CASES,
    build_report,
)


class BackendCapabilityPreflightTests(unittest.TestCase):
    def test_release_baseline_is_explicit_and_versioned(self):
        self.assertEqual(
            CASE_SET_VERSION,
            "backend-capability-preflight-2026-08-20-v1",
        )
        self.assertEqual(PINNED_CAPABILITY_VERSION, "2026-07")
        self.assertEqual(
            PINNED_CAPABILITY_SHA256,
            "1d1c2511e01c58c951f0ba9a1a59d8465b37007ae8259280c008caeac1f5cd7b",
        )
        self.assertEqual(len(PINNED_BACKEND_IDS), 6)
        self.assertEqual(len(REGRESSION_CASES), 8)

    def test_portable_snapshot_contract_passes_without_git_metadata(self):
        with mock.patch.object(preflight, "_git_output", return_value=None):
            report = build_report()

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["capability"]["version"], "2026-07")
        self.assertEqual(report["capability"]["backend_count"], 6)
        self.assertEqual(
            report["capability"]["content_sha256"],
            PINNED_CAPABILITY_SHA256,
        )
        self.assertEqual(report["contract_summary"]["failed"], 0)
        self.assertTrue(all(check["passed"] for check in report["contract_checks"]))
        self.assertEqual(report["git_drift"]["availability"], "unavailable")
        self.assertEqual(report["git_drift"]["status"], "SKIP")
        self.assertIsNone(report["git_drift"]["upstream_available"])
        self.assertEqual(report["repository_drift_summary"]["status"], "SKIP")
        self.assertEqual(report["repository_drift_summary"]["skipped"], 4)
        self.assertTrue(
            all(
                check["status"] == "SKIP" and check["passed"] is None
                for check in report["repository_drift_checks"]
            )
        )

    def test_git_drift_checks_pass_when_repository_metadata_is_available(self):
        report = build_report()

        if not report["git_drift"]["repository_metadata_available"]:
            self.skipTest("Git repository metadata unavailable")
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["git_drift"]["status"], "PASS")
        self.assertTrue(report["git_drift"]["working_tree_matches_head"])
        self.assertTrue(report["git_drift"]["working_tree_matches_upstream"])
        self.assertTrue(report["git_drift"]["head_matches_upstream"])
        self.assertEqual(report["repository_drift_summary"]["status"], "PASS")
        self.assertTrue(
            all(check["passed"] for check in report["repository_drift_checks"])
        )

    def test_git_drift_mismatch_remains_a_failure(self):
        def mismatched_git_output(arguments):
            if arguments == ("rev-parse", "--is-inside-work-tree"):
                return "true"
            if arguments == ("status", "--porcelain"):
                return ""
            if arguments == ("rev-parse", "HEAD"):
                return "head-commit"
            if arguments[0] == "hash-object":
                return "working-blob"
            if arguments == ("rev-parse", "upstream/main"):
                return "upstream-commit"
            if arguments[0] == "rev-parse" and arguments[1].startswith("HEAD:"):
                return "head-blob"
            if (
                arguments[0] == "rev-parse"
                and arguments[1].startswith("upstream/main:")
            ):
                return "upstream-blob"
            raise AssertionError("unexpected Git command: %r" % (arguments,))

        with mock.patch.object(
            preflight,
            "_git_output",
            side_effect=mismatched_git_output,
        ):
            report = build_report()

        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(report["git_drift"]["upstream_available"])
        self.assertEqual(report["git_drift"]["status"], "FAIL")
        self.assertGreater(report["repository_drift_summary"]["failed"], 0)
        self.assertIn(
            "head_matches_local_upstream_blob",
            report["repository_drift_summary"]["failed_checks"],
        )

    def test_selector_regressions_are_exact_ordered_and_never_invent_ids(self):
        report = build_report()

        self.assertEqual(report["regression_summary"]["failed"], 0)
        self.assertEqual(report["regression_summary"]["total"], 8)
        known_ids = set(PINNED_BACKEND_IDS)
        for entry in report["selector_regressions"]:
            with self.subTest(case_id=entry["case_id"]):
                self.assertEqual(entry["status"], "PASS")
                self.assertEqual(entry["selector_result"], entry["expected_result"])
                self.assertEqual(entry["invented_backend_ids"], [])
                self.assertTrue(set(entry["selector_result"]).issubset(known_ids))
                self.assertEqual(entry["no_match"], not bool(entry["selector_result"]))


if __name__ == "__main__":
    unittest.main()
