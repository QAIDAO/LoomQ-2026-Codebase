"""Small reference interpreter used for Hybrid compiler differential tests."""

from __future__ import annotations

from typing import Dict, Mapping, MutableMapping, Union

from .ast import (
    Assignment,
    BinaryExpression,
    ClassicalStatement,
    Condition,
    Expression,
    HybridProgram,
    IfStatement,
    IntegerLiteral,
    MeasurementReference,
    RegisterReference,
    UnaryExpression,
)
from .parser import parse_hybrid_program


def evaluate_expression(
    expression: Expression,
    registers: Mapping[int, int],
    measurements: Mapping[int, int],
) -> int:
    """Evaluate a side-effect-free classical expression."""

    if isinstance(expression, IntegerLiteral):
        return expression.value
    if isinstance(expression, RegisterReference):
        return int(registers.get(expression.index, 0))
    if isinstance(expression, MeasurementReference):
        return int(measurements.get(expression.index, 0))
    if isinstance(expression, UnaryExpression):
        value = evaluate_expression(expression.operand, registers, measurements)
        if expression.operator == "+":
            return value
        if expression.operator == "-":
            return -value
        raise ValueError(f"unsupported unary operator: {expression.operator}")
    if isinstance(expression, BinaryExpression):
        left = evaluate_expression(expression.left, registers, measurements)
        right = evaluate_expression(expression.right, registers, measurements)
        if expression.operator == "+":
            return left + right
        if expression.operator == "-":
            return left - right
        raise ValueError(f"unsupported binary operator: {expression.operator}")
    raise TypeError(f"unknown expression node: {type(expression).__name__}")


def evaluate_condition(
    condition: Condition,
    registers: Mapping[int, int],
    measurements: Mapping[int, int],
) -> bool:
    left = evaluate_expression(condition.left, registers, measurements)
    right = evaluate_expression(condition.right, registers, measurements)
    if condition.operator == "==":
        return left == right
    if condition.operator == "!=":
        return left != right
    raise ValueError(f"unsupported comparison operator: {condition.operator}")


def _execute_statements(
    statements: tuple[ClassicalStatement, ...],
    registers: MutableMapping[int, int],
    measurements: Mapping[int, int],
) -> None:
    for statement in statements:
        if isinstance(statement, Assignment):
            # Evaluate before updating the target, which matters for expressions
            # such as r1 = 5 - r1.
            value = evaluate_expression(statement.value, registers, measurements)
            registers[statement.target.index] = value
        elif isinstance(statement, IfStatement):
            branch = (
                statement.then_body
                if evaluate_condition(statement.condition, registers, measurements)
                else statement.else_body
            )
            _execute_statements(branch, registers, measurements)
        else:
            raise TypeError(f"unknown classical statement: {type(statement).__name__}")


def execute_program(
    program: HybridProgram,
    measurements: Mapping[int, int],
    initial_registers: Mapping[int, int] | None = None,
) -> Dict[int, int]:
    """Execute all classical blocks and return r1..r9 by source register index."""

    registers: Dict[int, int] = {index: 0 for index in range(1, 10)}
    if initial_registers is not None:
        for index, value in initial_registers.items():
            if index < 1 or index > 9:
                raise ValueError(f"initial register index must be 1..9, got {index}")
            registers[index] = int(value)
    normalized_measurements: Dict[int, int] = {}
    for index, value in measurements.items():
        if index < 0 or index > 21:
            raise ValueError(f"measurement index must be 0..21, got {index}")
        normalized_measurements[index] = int(value)
    _execute_statements(program.classical_statements, registers, normalized_measurements)
    return registers


def interpret_hybrid_program(
    source_or_program: Union[str, HybridProgram],
    measurements: Mapping[int, int],
    initial_registers: Mapping[int, int] | None = None,
) -> Dict[str, int]:
    """Parse and interpret a program, returning keys ``r1`` .. ``r9``."""

    program = (
        parse_hybrid_program(source_or_program)
        if isinstance(source_or_program, str)
        else source_or_program
    )
    values = execute_program(program, measurements, initial_registers)
    return {f"r{index}": values[index] for index in range(1, 10)}
