"""Independent evaluator for the classical subset of Hybrid-QASM.

This module deliberately does not inspect generated RISC-V.  Tests can compare
its source-level result with the official TinyRISCVEmulator result, making the
compiler and oracle fail independently.
"""

from __future__ import annotations

from collections.abc import Sequence

from .hybrid import (
    Assign,
    Binary,
    If,
    Integer,
    MeasurementValue,
    RegisterValue,
    parse_hybrid,
)


def interpret_classical(
    hybrid_qasm: str, measurements: Sequence[int]
) -> dict[str, int]:
    """Evaluate one injected measurement assignment at source level."""

    _operations, width, statements = parse_hybrid(hybrid_qasm)
    bits = _validated_measurements(measurements, width)
    registers = {index: 0 for index in range(1, 10)}
    _execute(statements, registers, bits)
    return {
        f"x{index}": value
        for index, value in registers.items()
        if value != 0
    }


def _execute(
    statements: Sequence[object],
    registers: dict[int, int],
    measurements: tuple[int, ...],
) -> None:
    for statement in statements:
        if isinstance(statement, Assign):
            registers[statement.target] = _evaluate(
                statement.expression, registers, measurements
            )
            continue
        if isinstance(statement, If):
            left = _evaluate(statement.left, registers, measurements)
            right = _evaluate(statement.right, registers, measurements)
            condition = left == right
            if statement.operator == "!=":
                condition = not condition
            branch = statement.then_body if condition else statement.else_body
            _execute(branch, registers, measurements)
            continue
        raise ValueError(f"unsupported Hybrid-QASM statement node: {type(statement).__name__}")


def _evaluate(
    expression: object,
    registers: dict[int, int],
    measurements: tuple[int, ...],
) -> int:
    if isinstance(expression, Integer):
        return expression.value
    if isinstance(expression, RegisterValue):
        return registers[expression.index]
    if isinstance(expression, MeasurementValue):
        return measurements[expression.index]
    if isinstance(expression, Binary):
        left = _evaluate(expression.left, registers, measurements)
        right = _evaluate(expression.right, registers, measurements)
        if expression.operator == "+":
            return left + right
        if expression.operator == "-":
            return left - right
    raise ValueError(f"unsupported Hybrid-QASM expression node: {type(expression).__name__}")


def _validated_measurements(
    values: Sequence[int], width: int
) -> tuple[int, ...]:
    bits = tuple(values)
    if len(bits) != width:
        raise ValueError(
            f"expected {width} injected measurement bits, received {len(bits)}"
        )
    if any(isinstance(value, bool) or value not in {0, 1} for value in bits):
        raise ValueError("injected measurements must be integer bits 0 or 1")
    return bits
