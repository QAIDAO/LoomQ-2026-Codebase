"""Coverage contracts for the generated L2 hidden-family surrogate corpus."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys
import unittest


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

from tests import l2_surrogate_corpus as corpus  # noqa: E402
import loomq.l2 as l2_module  # noqa: E402


class L2SurrogateCorpusTests(unittest.TestCase):
    def test_extended_corpus_has_192_unique_balanced_cases(self) -> None:
        cases = corpus.build_extended_cases()

        self.assertEqual(len(cases), 192)
        self.assertEqual(len({case.case_id for case in cases}), 192)
        self.assertEqual(len({case.prompt for case in cases}), 192)
        self.assertEqual(
            Counter(case.category for case in cases),
            {"generate": 64, "repair": 64, "select": 64},
        )
        self.assertEqual({case.language for case in cases}, {"en", "zh", "mixed"})

    def test_quantum_family_width_and_repair_error_coverage(self) -> None:
        cases = corpus.build_extended_cases()
        quantum = [case for case in cases if case.category != "select"]

        self.assertTrue({"bell", "ghz", "uniform", "deterministic", "phase"} <= {case.family for case in quantum})
        self.assertTrue({2, 3, 4, 5, 6, 8} <= {case.qubits for case in quantum if case.family == "ghz"})
        self.assertTrue({1, 2, 3, 4} <= {case.qubits for case in quantum if case.family == "uniform"})
        repairs = [case for case in quantum if case.category == "repair"]
        self.assertTrue(
            {"missing_declarations", "case_and_punctuation", "wrong_gate", "wrong_control", "wrong_bit_order", "missing_measurement"}
            <= {case.mutation for case in repairs}
        )
        self.assertTrue(any(case.semantic_mutation for case in repairs))

    def test_oracles_are_normalized_and_reference_qasm_matches(self) -> None:
        for case in corpus.build_extended_cases():
            if case.category == "select":
                self.assertIsNone(case.expected_distribution)
                self.assertIsNotNone(case.selection_constraints)
                continue
            expected = case.expected_distribution
            self.assertIsNotNone(expected)
            self.assertAlmostEqual(sum(expected.values()), 1.0)
            observed = corpus.independent_distribution(case.reference_qasm)
            self.assertGreaterEqual(corpus.hellinger_fidelity(observed, expected), 0.999999)

    def test_every_semantic_mutation_is_valid_qasm_and_actually_wrong(self) -> None:
        semantic = [
            case for case in corpus.build_extended_cases()
            if case.category == "repair" and case.semantic_mutation
        ]
        self.assertGreaterEqual(len(semantic), 24)
        for case in semantic:
            with self.subTest(case=case.case_id):
                self.assertIsNotNone(case.broken_qasm)
                observed = corpus.independent_distribution(case.broken_qasm)
                self.assertLess(
                    corpus.hellinger_fidelity(observed, case.expected_distribution),
                    0.97,
                )
    def test_every_quantum_prompt_round_trips_through_independent_prompt_oracle(self) -> None:
        for case in corpus.build_extended_cases():
            if case.category == "select":
                continue
            with self.subTest(case=case.case_id):
                oracle = l2_module._prompt_distribution_oracle(case.prompt, case.qubits)
                self.assertIsNotNone(oracle)
                width, distribution, _name = oracle
                self.assertEqual(width, case.qubits)
                self.assertGreaterEqual(
                    corpus.hellinger_fidelity(distribution, case.expected_distribution),
                    0.999999,
                )

    def test_every_selection_prompt_expresses_every_private_constraint(self) -> None:
        for case in corpus.build_extended_cases():
            if case.category != "select":
                continue
            constraints = case.selection_constraints
            prompt = case.prompt.lower()
            with self.subTest(case=case.case_id):
                if constraints.get("required_kind"):
                    self.assertIn(str(constraints["required_kind"]).lower(), prompt)
                if constraints.get("require_real_hardware"):
                    self.assertIn("real", prompt)
                if constraints.get("require_zero_queue"):
                    self.assertIn("zero", prompt)
                if constraints.get("avoid_paid"):
                    self.assertTrue("paid" in prompt or "fee" in prompt or "免费" in prompt)
                if constraints.get("require_no_account"):
                    self.assertTrue("account" in prompt or "账号" in prompt)
                for platform in constraints.get("allowed_platforms", []):
                    self.assertIn(platform.lower(), prompt)
    def test_selection_cases_cover_capability_boundaries_and_conflicts(self) -> None:
        cases = [case for case in corpus.build_extended_cases() if case.category == "select"]
        expected_sets = [corpus.expected_backend_ids(case.selection_constraints) for case in cases]

        self.assertTrue(any(not answers for answers in expected_sets))
        self.assertTrue(any(len(answers) > 1 for answers in expected_sets))
        covered = set().union(*expected_sets)
        self.assertEqual(covered, corpus.canonical_backend_ids())
        self.assertTrue({1, 8, 9, 15, 24, 25, 26, 30, 31, 34, 35, 50, 180, 181, 200} <= {case.qubits for case in cases})

    def test_sixty_case_live_sample_is_deterministic_and_stratified(self) -> None:
        first = corpus.stratified_live_sample(size=60, seed=2026081203)
        second = corpus.stratified_live_sample(size=60, seed=2026081203)

        self.assertEqual([case.case_id for case in first], [case.case_id for case in second])
        self.assertEqual(Counter(case.category for case in first), {"generate": 20, "repair": 20, "select": 20})
        self.assertTrue({"bell", "ghz", "uniform", "deterministic", "phase"} <= {case.family for case in first})
        self.assertTrue(any(case.semantic_mutation for case in first if case.category == "repair"))
        self.assertTrue(any(not corpus.expected_backend_ids(case.selection_constraints) for case in first if case.category == "select"))


if __name__ == "__main__":
    unittest.main()
