import math
import unittest

from starter_kit.loomq_l1.errors import ExpressionError
from starter_kit.loomq_l1.expressions import evaluate_expression


class _IndexGuardedString(str):
    def __new__(cls, value, maximum_index=None):
        instance = super().__new__(cls, value)
        instance.maximum_index = maximum_index
        return instance

    def __getitem__(self, index):
        if isinstance(index, int) and (
            self.maximum_index is None or index > self.maximum_index
        ):
            raise AssertionError("input was scanned past its allowed boundary")
        return super().__getitem__(index)


class ExpressionTests(unittest.TestCase):
    def test_evaluates_contest_parameter_grammar(self):
        cases = {
            "pi/2": math.pi / 2,
            "-(pi/4)": -math.pi / 4,
            "2*(pi/8+0.25)": 2 * (math.pi / 8 + 0.25),
            ".5": 0.5,
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertAlmostEqual(evaluate_expression(source), expected)

    def test_rejects_code_and_non_finite_arithmetic(self):
        for source in (
            "__import__('os')",
            "1/0",
            "unknown+1",
            "9" * 400,
            "1..2",
            "(1+2",
            "1+2)",
        ):
            with self.subTest(source=source):
                with self.assertRaises(ExpressionError):
                    evaluate_expression(source)

    def test_rejects_non_ascii_digits(self):
        for source in ("١+٢", "１２+３"):
            with self.subTest(source=source):
                with self.assertRaises(ExpressionError):
                    evaluate_expression(source)

    def test_accepts_ascii_whitespace_unary_plus_and_binary_minus(self):
        self.assertEqual(evaluate_expression(" \t+1\r\n"), 1.0)
        self.assertEqual(evaluate_expression(" 5\t-\r2\n"), 3.0)

    def test_rejects_non_ascii_whitespace(self):
        with self.assertRaises(ExpressionError):
            evaluate_expression("1\u00a0+2")

    def test_requires_exact_str_source_type(self):
        with self.assertRaises(ExpressionError):
            evaluate_expression(_IndexGuardedString("1"))

    def test_rejects_numeric_literals_over_resource_limit(self):
        cases = (
            "0" * 2048,
            "0." + "0" * 2046 + "1",
        )
        for source in cases:
            with self.subTest(length=len(source)):
                with self.assertRaises(ExpressionError):
                    evaluate_expression(source)

    def test_numeric_literal_length_boundary(self):
        self.assertEqual(evaluate_expression("0" * 1024), 0.0)
        with self.assertRaises(ExpressionError):
            evaluate_expression("0" * 1025)

    def test_total_source_length_boundary(self):
        accepted = "1" + " " * 65535
        self.assertEqual(len(accepted), 65536)
        self.assertEqual(evaluate_expression(accepted), 1.0)

        rejected = "1" + " " * 65536
        self.assertEqual(len(rejected), 65537)
        with self.assertRaises(ExpressionError):
            evaluate_expression(rejected)

    def test_rejects_excessive_unary_and_parenthesis_nesting(self):
        cases = (
            "+" * 2048 + "1",
            "(" * 2048 + "1" + ")" * 2048,
        )
        for source in cases:
            with self.subTest(length=len(source)):
                with self.assertRaises(ExpressionError):
                    evaluate_expression(source)

    def test_enforces_deterministic_nesting_boundary(self):
        nesting_limit = 64
        cases = (
            ("+" * nesting_limit + "1", 1.0),
            ("(" * nesting_limit + "1" + ")" * nesting_limit, 1.0),
        )
        for source, expected in cases:
            with self.subTest(length=len(source)):
                self.assertEqual(evaluate_expression(source), expected)

        over_limit_cases = (
            "+" * (nesting_limit + 1) + "1",
            "(" * (nesting_limit + 1) + "1" + ")" * (nesting_limit + 1),
        )
        for source in over_limit_cases:
            with self.subTest(length=len(source)):
                with self.assertRaises(ExpressionError):
                    evaluate_expression(source)

    def test_rejects_overlong_source_before_tokenization(self):
        source = _IndexGuardedString("1+" * 40000)
        with self.assertRaises(ExpressionError):
            evaluate_expression(source)

    def test_rejects_overlong_numeric_literal_during_scanning(self):
        source = _IndexGuardedString("0" * 2048, maximum_index=1024)
        with self.assertRaises(ExpressionError):
            evaluate_expression(source)


if __name__ == "__main__":
    unittest.main()
