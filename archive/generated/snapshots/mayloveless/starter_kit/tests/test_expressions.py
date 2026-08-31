"""OpenQASM 安全角度表达式测试。"""

import math
import unittest

from loomq.expressions import ParameterExpressionError, parse_angle_expression


class AngleExpressionTests(unittest.TestCase):
    def test_decimal_negative_and_scientific_numbers(self) -> None:
        cases = {
            "0": 0.0,
            "1.25": 1.25,
            "-2.5": -2.5,
            "+1e-3": 0.001,
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertAlmostEqual(expected, parse_angle_expression(expression))

    def test_pi_arithmetic(self) -> None:
        cases = {
            "pi": math.pi,
            "pi/2": math.pi / 2,
            "-pi/4": -math.pi / 4,
            "3*pi/8": 3 * math.pi / 8,
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertAlmostEqual(expected, parse_angle_expression(expression))

    def test_nested_parentheses_and_spaces(self) -> None:
        value = parse_angle_expression(" (pi + pi/2) / (1 + 2) ")

        self.assertAlmostEqual(math.pi / 2, value)

    def test_division_by_zero_is_rejected(self) -> None:
        with self.assertRaisesRegex(ParameterExpressionError, "invalid arithmetic"):
            parse_angle_expression("pi / (2 - 2)")

    def test_unknown_names_are_rejected(self) -> None:
        for expression in ("theta", "PI", "nan", "inf"):
            with self.subTest(expression=expression):
                with self.assertRaises(ParameterExpressionError):
                    parse_angle_expression(expression)

    def test_calls_attributes_and_power_are_rejected(self) -> None:
        for expression in ("sin(pi)", "pi.real", "pi ** 2", "pi % 2", "pi[0]"):
            with self.subTest(expression=expression):
                with self.assertRaises(ParameterExpressionError):
                    parse_angle_expression(expression)

    def test_non_decimal_python_literals_are_rejected(self) -> None:
        for expression in ("0x10", "0b10", "1_000"):
            with self.subTest(expression=expression):
                with self.assertRaisesRegex(ParameterExpressionError, "decimal"):
                    parse_angle_expression(expression)

    def test_non_finite_result_is_rejected(self) -> None:
        for expression in ("1e309", "1e308 * 1e308"):
            with self.subTest(expression=expression):
                with self.assertRaisesRegex(ParameterExpressionError, "finite"):
                    parse_angle_expression(expression)


if __name__ == "__main__":
    unittest.main()
