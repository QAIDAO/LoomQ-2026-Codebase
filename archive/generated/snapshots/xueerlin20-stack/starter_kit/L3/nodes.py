"""Typed abstract syntax tree nodes for the Hybrid-QASM classical block."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Union


@dataclass(frozen=True)
class IntegerLiteral:
    value: int


@dataclass(frozen=True)
class RegisterRef:
    index: int


@dataclass(frozen=True)
class MeasurementRef:
    index: int


@dataclass(frozen=True)
class BinaryExpression:
    operator: str
    left: "Expression"
    right: "Expression"


Expression = Union[IntegerLiteral, RegisterRef, MeasurementRef, BinaryExpression]


@dataclass(frozen=True)
class Comparison:
    operator: str
    left: Expression
    right: Expression


@dataclass(frozen=True)
class Assignment:
    target: int
    expression: Expression


@dataclass(frozen=True)
class IfStatement:
    condition: Comparison
    then_body: Tuple["Statement", ...]
    else_body: Tuple["Statement", ...]


Statement = Union[Assignment, IfStatement]


@dataclass(frozen=True)
class HybridProgram:
    quantum_operations: Tuple[str, ...]
    classical_statements: Tuple[Statement, ...]
    classical_bit_count: int

