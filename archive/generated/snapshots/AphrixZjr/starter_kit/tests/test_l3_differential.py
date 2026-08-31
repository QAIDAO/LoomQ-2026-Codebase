"""Deterministic differential and boundary coverage for Hybrid-QASM L3."""

from __future__ import annotations

import itertools
import os
import random
import sys
import unittest
from dataclasses import dataclass
from typing import Sequence, Tuple, Union


STARTER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if STARTER not in sys.path:
    sys.path.insert(0, STARTER)

from loomq_l3 import compile_hybrid
from riscv_emulator import TinyRISCVEmulator


@dataclass(frozen=True)
class RefAtom:
    kind: str
    value: int


@dataclass(frozen=True)
class RefBinary:
    op: str
    left: "RefExpr"
    right: "RefExpr"


RefExpr = Union[RefAtom, RefBinary]


@dataclass(frozen=True)
class RefAssign:
    register: int
    expression: RefExpr


@dataclass(frozen=True)
class RefIfElse:
    op: str
    left: RefExpr
    right: RefExpr
    then_body: Tuple["RefStatement", ...]
    else_body: Tuple["RefStatement", ...]


RefStatement = Union[RefAssign, RefIfElse]


def _constant(value: int) -> RefAtom:
    return RefAtom("constant", value)


def _register(index: int) -> RefAtom:
    return RefAtom("register", index)


def _measurement(index: int) -> RefAtom:
    return RefAtom("measurement", index)


def _binary(op: str, left: RefExpr, right: RefExpr) -> RefBinary:
    return RefBinary(op, left, right)


def _sum_repeated(expression: RefExpr, repetitions: int) -> RefExpr:
    result = expression
    for _ in range(repetitions - 1):
        result = _binary("+", result, expression)
    return result


def _sequential_if_statements(
    count: int, measurement_indices: Sequence[int]
) -> Tuple[RefStatement, ...]:
    indices = tuple(measurement_indices)
    statements = []
    for index in range(count):
        target = index % 5 + 1
        condition_register = (index + 1) % 5 + 1
        measured = indices[index % len(indices)]
        statements.append(
            RefIfElse(
                "==" if index % 2 else "!=",
                _binary(
                    "+", _register(condition_register), _measurement(measured)
                ),
                _binary("-", _register(target), _constant(-(index % 4))),
                (
                    RefAssign(
                        target,
                        _binary(
                            "-",
                            _binary(
                                "+",
                                _register(target),
                                _measurement(indices[(index + 3) % len(indices)]),
                            ),
                            _constant(index - 6),
                        ),
                    ),
                ),
                (
                    RefAssign(
                        target,
                        _binary(
                            "+",
                            _binary(
                                "-",
                                _register(target),
                                _measurement(indices[(index + 5) % len(indices)]),
                            ),
                            _constant(-index - 1),
                        ),
                    ),
                ),
            )
        )
    return tuple(statements)


def _nested_statements(
    depth: int, path: int, measurement_indices: Sequence[int]
) -> Tuple[RefStatement, ...]:
    indices = tuple(measurement_indices)
    target = path % 5 + 1
    position = (path + depth) % len(indices)
    measured = indices[position]
    if depth == 0:
        return (
            RefAssign(
                target,
                _binary("-", _register(target), _constant(-(path % 7))),
            ),
        )
    return (
        RefIfElse(
            "==" if path % 2 else "!=",
            _binary("+", _register(target), _measurement(measured)),
            _binary(
                "-",
                _measurement(indices[(position + 1) % len(indices)]),
                _constant(-depth),
            ),
            (
                RefAssign(
                    target,
                    _binary("+", _register(target), _measurement(measured)),
                ),
            )
            + _nested_statements(depth - 1, path * 2 + 1, indices),
            (
                RefAssign(
                    target,
                    _binary("-", _register(target), _measurement(measured)),
                ),
            )
            + _nested_statements(depth - 1, path * 2 + 2, indices),
        ),
    )


def _render_expression(expression: RefExpr) -> str:
    if isinstance(expression, RefAtom):
        if expression.kind == "constant":
            return str(expression.value)
        if expression.kind == "register":
            return "r%d" % expression.value
        return "c[%d]" % expression.value
    return "(%s %s %s)" % (
        _render_expression(expression.left),
        expression.op,
        _render_expression(expression.right),
    )


def _render_statement(statement: RefStatement) -> str:
    if isinstance(statement, RefAssign):
        return "r%d = %s;" % (
            statement.register,
            _render_expression(statement.expression),
        )
    then_body = " ".join(_render_statement(item) for item in statement.then_body)
    else_body = " ".join(_render_statement(item) for item in statement.else_body)
    return "if (%s %s %s) { %s } else { %s }" % (
        _render_expression(statement.left),
        statement.op,
        _render_expression(statement.right),
        then_body,
        else_body,
    )


def _hybrid_source(width: int, statements: Tuple[RefStatement, ...]) -> str:
    measurements = "\n".join(
        "measure q[%d] -> c[%d];" % (index, index) for index in range(width)
    )
    body = "\n".join(_render_statement(statement) for statement in statements)
    return """OPENQASM 2.0;
include "qelib1.inc";
qreg q[{width}];
creg c[{width}];
{measurements}
classical {{
{body}
}}
""".format(width=width, measurements=measurements, body=body)


def _evaluate_expression(
    expression: RefExpr, registers: dict[int, int], measurements: Tuple[int, ...]
) -> int:
    if isinstance(expression, RefAtom):
        if expression.kind == "constant":
            return expression.value
        if expression.kind == "register":
            return registers[expression.value]
        return measurements[expression.value]
    left = _evaluate_expression(expression.left, registers, measurements)
    right = _evaluate_expression(expression.right, registers, measurements)
    return left + right if expression.op == "+" else left - right


def _interpret(
    statements: Tuple[RefStatement, ...], measurements: Tuple[int, ...]
) -> dict[int, int]:
    registers = {index: 0 for index in range(1, 10)}

    def execute(body: Tuple[RefStatement, ...]) -> None:
        for statement in body:
            if isinstance(statement, RefAssign):
                registers[statement.register] = _evaluate_expression(
                    statement.expression, registers, measurements
                )
                continue
            left = _evaluate_expression(statement.left, registers, measurements)
            right = _evaluate_expression(statement.right, registers, measurements)
            equal = left == right
            execute(
                statement.then_body
                if equal == (statement.op == "==")
                else statement.else_body
            )

    execute(statements)
    return registers


class _ProgramGenerator:
    def __init__(self, seed: int, width: int = 3):
        self.random = random.Random(seed)
        self.width = width

    def expression(self, depth: int) -> RefExpr:
        if depth <= 0 or self.random.random() < 0.42:
            atom = self.random.randrange(3)
            if atom == 0:
                return _constant(self.random.randint(-6, 6))
            if atom == 1:
                return _register(self.random.randint(1, 5))
            return _measurement(self.random.randrange(self.width))
        return _binary(
            self.random.choice(("+", "-")),
            self.expression(depth - 1),
            self.expression(depth - 1),
        )

    def assignment(self) -> RefAssign:
        target = self.random.randint(1, 5)
        if self.random.random() < 0.35:
            # Deliberately create legal, non-power-of-two target coefficients.
            repetitions = self.random.choice((3, 5))
            expression = _sum_repeated(_register(target), repetitions)
            expression = _binary(
                self.random.choice(("+", "-")), expression, self.expression(1)
            )
        else:
            expression = self.expression(2)
        return RefAssign(target, expression)

    def statements(self, depth: int, count: int) -> Tuple[RefStatement, ...]:
        result = []
        for _ in range(count):
            if depth > 0 and self.random.random() < 0.38:
                result.append(
                    RefIfElse(
                        self.random.choice(("==", "!=")),
                        self.expression(2),
                        self.expression(2),
                        self.statements(depth - 1, self.random.randint(1, 2)),
                        self.statements(depth - 1, self.random.randint(1, 2)),
                    )
                )
            else:
                result.append(self.assignment())
        return tuple(result)


class L3DifferentialTests(unittest.TestCase):
    ALLOWED_OPS = frozenset(("li", "add", "sub", "addi", "beq", "bne", "j"))

    def _assert_program(
        self,
        width: int,
        statements: Tuple[RefStatement, ...],
        *,
        max_steps: int = 1000,
        max_lines: int | None = None,
        max_bytes: int | None = None,
        measurement_indices: Sequence[int] | None = None,
    ) -> str:
        _, assembly = compile_hybrid(_hybrid_source(width, statements))
        lines = assembly.splitlines()
        if max_lines is not None:
            self.assertLessEqual(len(lines), max_lines)
        if max_bytes is not None:
            self.assertLessEqual(len(assembly.encode("utf-8")), max_bytes)
        opcodes = {
            line.split()[0]
            for line in lines
            if line.strip() and not line.rstrip().endswith(":")
        }
        self.assertLessEqual(opcodes, self.ALLOWED_OPS)
        labels = [line[:-1] for line in lines if line.endswith(":")]
        self.assertEqual(len(labels), len(set(labels)))
        varied = (
            tuple(range(width))
            if measurement_indices is None
            else tuple(measurement_indices)
        )
        self.assertEqual(len(varied), len(set(varied)))
        self.assertTrue(all(0 <= index < width for index in varied))
        for varied_values in itertools.product((0, 1), repeat=len(varied)):
            values = [0] * width
            for index, value in zip(varied, varied_values):
                values[index] = value
            measurements = tuple(values)
            emulator = TinyRISCVEmulator()
            emulator.max_steps = max_steps
            emulator.load_program(assembly)
            for index, value in enumerate(measurements):
                emulator.set_register("x%d" % (10 + index), value)
            emulator.execute()
            expected = _interpret(statements, measurements)
            actual = {
                index: emulator.get_register("x%d" % index)
                for index in range(1, 10)
            }
            self.assertEqual(actual, expected, measurements)
            self.assertEqual(
                tuple(
                    emulator.get_register("x%d" % (10 + index))
                    for index in range(width)
                ),
                measurements,
            )
        return assembly

    def test_arbitrary_repeated_target_coefficients(self):
        r1, r2, r3, r4 = (_register(index) for index in range(1, 5))
        statements = (
            RefAssign(1, _binary("+", _measurement(0), _constant(2))),
            RefAssign(1, _sum_repeated(r1, 3)),
            RefAssign(2, _binary("-", _measurement(1), _constant(3))),
            RefAssign(
                2,
                _binary(
                    "-",
                    _binary("-", _binary("-", _constant(0), r2), r2),
                    r2,
                ),
            ),
            RefAssign(3, _binary("-", _measurement(0), _measurement(1))),
            RefAssign(3, _sum_repeated(r3, 5)),
            RefAssign(4, _constant(7)),
            RefAssign(4, _binary("-", r4, r4)),
        )
        self._assert_program(2, statements)

    def test_c21_is_specialized_then_restored(self):
        statements = (
            RefAssign(1, _constant(4)),
            RefIfElse(
                "==",
                _measurement(21),
                _constant(1),
                (RefAssign(2, _constant(11)),),
                (RefAssign(2, _constant(-11)),),
            ),
            RefIfElse(
                "!=",
                _binary(
                    "-",
                    _binary("+", _measurement(21), _register(1)),
                    _constant(2),
                ),
                _binary("+", _register(2), _constant(3)),
                (RefAssign(3, _constant(17)),),
                (RefAssign(3, _constant(-17)),),
            ),
        )
        _, assembly = compile_hybrid(_hybrid_source(22, statements))
        self.assertTrue(assembly.startswith("beq x31, x0, L3_C21_ZERO\n"))
        self.assertEqual(assembly.count("L3_C21_ZERO:"), 1)
        self.assertEqual(assembly.count("L3_C21_END:"), 1)
        for measured in (0, 1):
            measurements = (0,) * 21 + (measured,)
            emulator = TinyRISCVEmulator()
            emulator.load_program(assembly)
            emulator.set_register("x31", measured)
            emulator.execute()
            expected = _interpret(statements, measurements)
            self.assertEqual(emulator.get_register("x2"), expected[2])
            self.assertEqual(emulator.get_register("x3"), expected[3])
            self.assertEqual(emulator.get_register("x31"), measured)

    def test_width_twenty_one_reserves_x31_and_preserves_c20(self):
        statements = (
            RefAssign(1, _binary("-", _measurement(20), _constant(-4))),
            RefIfElse(
                "!=",
                _binary("+", _register(1), _measurement(20)),
                _constant(5),
                (RefAssign(2, _binary("-", _register(1), _constant(7))),),
                (RefAssign(2, _binary("+", _register(1), _constant(-7))),),
            ),
        )
        _, assembly = compile_hybrid(_hybrid_source(21, statements))
        self.assertIn("x31", assembly)
        for measured in (0, 1):
            measurements = (0,) * 20 + (measured,)
            emulator = TinyRISCVEmulator()
            emulator.load_program(assembly)
            emulator.set_register("x30", measured)
            emulator.execute()
            expected = _interpret(statements, measurements)
            self.assertEqual(emulator.get_register("x1"), expected[1])
            self.assertEqual(emulator.get_register("x2"), expected[2])
            self.assertEqual(emulator.get_register("x30"), measured)

    def test_nested_full_linear_conditions_and_negative_constants(self):
        statements = (
            RefAssign(
                1,
                _binary(
                    "-",
                    _binary("-", _measurement(0), _measurement(1)),
                    _constant(2),
                ),
            ),
            RefAssign(2, _sum_repeated(_register(1), 3)),
            RefIfElse(
                "!=",
                _binary(
                    "-",
                    _binary("+", _register(1), _measurement(2)),
                    _constant(-3),
                ),
                _binary(
                    "+",
                    _binary("-", _register(2), _measurement(0)),
                    _constant(4),
                ),
                (
                    RefIfElse(
                        "==",
                        _binary(
                            "+",
                            _binary("-", _register(2), _register(1)),
                            _binary("-", _measurement(1), _constant(5)),
                        ),
                        _binary(
                            "-",
                            _binary("+", _measurement(2), _register(1)),
                            _constant(-2),
                        ),
                        (RefAssign(3, _constant(-19)),),
                        (RefAssign(3, _constant(23)),),
                    ),
                ),
                (RefAssign(3, _binary("-", _register(2), _constant(-7))),),
            ),
            RefAssign(
                4,
                _binary(
                    "-",
                    _binary("+", _register(3), _register(2)),
                    _register(1),
                ),
            ),
        )
        self._assert_program(3, statements)

    def test_fixed_seed_ast_differential_all_measurements(self):
        generator = _ProgramGenerator(seed=0x10A3, width=3)
        for case_index in range(32):
            statements = generator.statements(
                depth=2, count=generator.random.randint(3, 5)
            )
            with self.subTest(case=case_index):
                self._assert_program(3, statements)

    def test_twelve_sequential_if_statements_share_their_continuation(self):
        assembly = self._assert_program(
            8,
            _sequential_if_statements(12, tuple(range(8))),
            max_steps=300,
            max_lines=500,
            max_bytes=12000,
        )
        lines = assembly.splitlines()
        self.assertEqual(
            sum(line.startswith("L3_ELSE_") and line.endswith(":") for line in lines),
            12,
        )
        self.assertEqual(
            sum(line.startswith("L3_END_") and line.endswith(":") for line in lines),
            12,
        )

    def test_depth_four_shared_cfg_across_five_measurement_bits(self):
        assembly = self._assert_program(
            5,
            _nested_statements(4, 1, tuple(range(5))),
            max_steps=200,
            max_lines=1000,
            max_bytes=24000,
        )
        self.assertEqual(
            sum(
                line.startswith("L3_END_") and line.endswith(":")
                for line in assembly.splitlines()
            ),
            15,
        )

    def test_width22_sequential_if_output_is_bounded_at_twelve_and_twenty(self):
        active = (0, 1, 2, 3, 4, 5, 6, 21)
        assembly12 = self._assert_program(
            22,
            _sequential_if_statements(12, active),
            measurement_indices=active,
            max_steps=300,
            max_lines=800,
            max_bytes=16000,
        )
        assembly20 = self._assert_program(
            22,
            _sequential_if_statements(20, active),
            measurement_indices=active,
            max_steps=500,
            max_lines=1300,
            max_bytes=26000,
        )
        lines12 = assembly12.splitlines()
        lines20 = assembly20.splitlines()
        self.assertLessEqual(len(lines20), 2 * len(lines12))
        self.assertLessEqual(
            len(assembly20.encode("utf-8")),
            2 * len(assembly12.encode("utf-8")),
        )
        self.assertEqual(
            sum(line.startswith("L3_END_") and line.endswith(":") for line in lines12),
            24,
        )
        self.assertEqual(
            sum(line.startswith("L3_END_") and line.endswith(":") for line in lines20),
            40,
        )

    def test_width22_depth_four_restores_x31_for_every_active_measurement(self):
        active = (0, 3, 7, 12, 21)
        assembly = self._assert_program(
            22,
            _nested_statements(4, 1, active),
            measurement_indices=active,
            max_steps=200,
            max_lines=900,
            max_bytes=18000,
        )
        self.assertEqual(
            sum(
                line.startswith("L3_END_") and line.endswith(":")
                for line in assembly.splitlines()
            ),
            30,
        )


if __name__ == "__main__":
    unittest.main()
