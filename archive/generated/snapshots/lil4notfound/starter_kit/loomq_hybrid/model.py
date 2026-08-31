"""Abstract syntax tree for the Hybrid-QASM classical subset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Union


@dataclass(frozen=True)
class IntegerLiteral:
    value: int


@dataclass(frozen=True)
class RegisterReference:
    index: int


@dataclass(frozen=True)
class ClassicalReference:
    register: str
    index: int


@dataclass(frozen=True)
class UnaryExpression:
    operator: str
    operand: "Expression"


@dataclass(frozen=True)
class BinaryExpression:
    operator: str
    left: "Expression"
    right: "Expression"


Expression = Union[
    IntegerLiteral,
    RegisterReference,
    ClassicalReference,
    UnaryExpression,
    BinaryExpression,
]


@dataclass(frozen=True)
class Assignment:
    target: int
    expression: Expression


@dataclass(frozen=True)
class Condition:
    operator: str
    left: Expression
    right: Expression


@dataclass(frozen=True)
class IfStatement:
    condition: Condition
    then_body: Tuple["Statement", ...]
    else_body: Tuple["Statement", ...]


Statement = Union[Assignment, IfStatement]
