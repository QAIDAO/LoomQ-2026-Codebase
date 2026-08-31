"""Offline contract tests for the opt-in real DeepSeek L2 harness."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starter_kit.tests import live_l2_deepseek_harness as harness  # noqa: E402


class L2LiveHarnessContractTests(unittest.TestCase):
    def test_two_fixed_seeds_define_twenty_four_balanced_cases(self) -> None:
        cases = harness.build_cases()

        self.assertEqual(harness.SURROGATE_SEEDS, (2026081201, 2026081202))
        self.assertEqual(len(cases), 24)
        self.assertEqual(len({case.case_id for case in cases}), 24)
        self.assertEqual(len({case.prompt for case in cases}), 24)
        self.assertEqual(
            {category: sum(case.category == category for case in cases)
             for category in ("generate", "repair", "select")},
            {"generate": 8, "repair": 8, "select": 8},
        )
        for seed in harness.SURROGATE_SEEDS:
            seeded = [case for case in cases if case.seed == seed]
            self.assertEqual(len(seeded), 12)
            self.assertEqual(
                {category: sum(case.category == category for case in seeded)
                 for category in ("generate", "repair", "select")},
                {"generate": 4, "repair": 4, "select": 4},
            )

    def test_quantum_oracles_are_normalized_binary_distributions(self) -> None:
        for case in harness.build_cases():
            if case.category == "select":
                self.assertIsNone(case.expected_distribution)
                continue
            distribution = case.expected_distribution
            self.assertIsNotNone(distribution)
            self.assertAlmostEqual(sum(distribution.values()), 1.0)
            widths = {len(state) for state in distribution}
            self.assertEqual(len(widths), 1)
            for state, probability in distribution.items():
                self.assertFalse(set(state) - {"0", "1"})
                self.assertGreater(probability, 0.0)

    def test_backend_oracle_is_derived_from_official_capability_table(self) -> None:
        cases = [case for case in harness.build_cases() if case.category == "select"]
        observed = {
            case.oracle_name: harness.expected_backend_ids(case.selection_constraints)
            for case in cases
        }

        self.assertEqual(
            observed["15q-free-zero-queue-no-account"],
            {
                "spinq_taurus_simulator",
                "originq_local_simulator",
                "braket_local_simulator",
            },
        )
        self.assertEqual(
            observed["5q-real-hardware-no-paid"],
            {"spinq_cloud_qpu", "originq_wukong"},
        )
        self.assertEqual(
            observed["30q-free-zero-queue"],
            {"originq_local_simulator"},
        )
        self.assertEqual(observed["200q-real-free-zero-queue"], set())

    def test_report_redaction_never_serializes_configured_key(self) -> None:
        secret = "sk-live-secret-that-must-not-appear"
        report = harness.redact_report(
            {"reply": f"accidental echo {secret}", "nested": [secret]},
            secrets=[secret],
        )
        serialized = json.dumps(report)

        self.assertNotIn(secret, serialized)
        self.assertEqual(report["nested"], ["[REDACTED]"])

    def test_worker_protocol_is_ascii_safe_on_windows(self) -> None:
        serialized = harness.serialize_worker_payload({"message": "right ket: ⟩"})

        self.assertTrue(serialized.isascii())
        self.assertEqual(json.loads(serialized), {"message": "right ket: ⟩"})

    def test_campaign_extractor_rejects_summary_header_poisoning(self) -> None:
        poisoned = """OPENQASM 2.0; qreg q[1]; creg c[1]; x q[0]; measure q -> c;

```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
```
"""
        with self.assertRaisesRegex(ValueError, "exactly one"):
            harness._extract_qasm(poisoned)

    def test_extended_suite_selection_is_deterministic_and_balanced(self) -> None:
        sample = harness.build_execution_cases("extended60")
        full = harness.build_execution_cases("extended192")

        self.assertEqual(len(sample), 60)
        self.assertEqual(len(full), 192)
        self.assertEqual(
            {category: sum(case.category == category for case in sample)
             for category in ("generate", "repair", "select")},
            {"generate": 20, "repair": 20, "select": 20},
        )
        self.assertEqual(
            [case.case_id for case in sample],
            [case.case_id for case in harness.build_execution_cases("extended60")],
        )

    def test_quantum_scoring_uses_production_and_independent_oracles(self) -> None:
        source = Path(harness.__file__).read_text(encoding="utf-8")

        self.assertIn("production_fidelity", source)
        self.assertIn("independent_fidelity", source)
        self.assertIn("independent_distribution", source)
        self.assertIn("--suite", source)
        self.assertIn("extended60", source)
        self.assertIn("integrity_sha256", source)
        self.assertIn("prompt_sha256", source)
        self.assertIn("verify_campaign_report", source)
    def test_live_execution_is_opt_in_and_generated_report_is_ignored(self) -> None:
        source = Path(harness.__file__).read_text(encoding="utf-8")
        self.assertIn("--env-file", source)
        self.assertIn("LOOMQ_LLM_BASE_URL", source)
        self.assertIn("LOOMQ_LLM_API_KEY", source)
        self.assertIn("LOOMQ_LLM_MODEL", source)
        self.assertIn("--live", source)
        self.assertIn("l2-live-deepseek-report.json", source)
        self.assertNotIn("api.deepseek.com", source)
        self.assertNotRegex(source, r"sk-[A-Za-z0-9_-]{8,}")
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8-sig")
        self.assertIn("/starter_kit/.env.l2.local", ignored)
        self.assertIn("/starter_kit/tests/generated/", ignored)
