import unittest

try:
    from starter_kit.prompt_quality import CASES, CaseResult, QualityCase, build_report, grade_answer
except ModuleNotFoundError:
    from prompt_quality import CASES, CaseResult, QualityCase, build_report, grade_answer


class PromptQualityTests(unittest.TestCase):
    def test_corpus_covers_all_l2_categories(self):
        self.assertEqual({case.category for case in CASES}, {"generation", "repair", "backend"})
        self.assertEqual(len(CASES), 12)

    def test_backend_grading_requires_canonical_id(self):
        case = QualityCase("id", "backend", "", ("originq_local_simulator",))
        self.assertTrue(grade_answer(case, "推荐 originq_local_simulator")[0])
        self.assertFalse(grade_answer(case, "推荐本源本地模拟器")[0])

    def test_no_solution_grading_accepts_explicit_statement(self):
        case = QualityCase("id", "backend", "", expects_no_backend=True)
        self.assertTrue(grade_answer(case, "没有后端满足全部条件；可考虑拆分线路。 ")[0])

    def test_report_calculates_absolute_improvement(self):
        legacy = [CaseResult("x", "generation", False, "", "")]
        v2 = [CaseResult("x", "generation", True, "", "")]
        report = build_report({"legacy": legacy, "v2": v2})
        self.assertEqual(report["improvement"]["absolute_pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
