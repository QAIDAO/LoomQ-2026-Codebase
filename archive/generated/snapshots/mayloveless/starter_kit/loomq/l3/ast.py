"""Hybrid-QASM 经典子语言的抽象语法树。"""

from dataclasses import dataclass
from typing import Tuple, Union


@dataclass(frozen=True)
class IntegerLiteral:
    value: int


@dataclass(frozen=True)
class RegisterRef:
    index: int


@dataclass(frozen=True)
class ClassicalBitRef:
    index: int


@dataclass(frozen=True)
class BinaryExpr:
    operator: str
    left: "Expression"
    right: "Expression"


Expression = Union[IntegerLiteral, RegisterRef, ClassicalBitRef, BinaryExpr]


@dataclass(frozen=True)
class Comparison:
    operator: str
    left: Expression
    right: Expression


@dataclass(frozen=True)
class Assignment:
    target: RegisterRef
    expression: Expression


@dataclass(frozen=True)
class IfElse:
    condition: Comparison
    then_body: Tuple["Statement", ...]
    else_body: Tuple["Statement", ...]


Statement = Union[Assignment, IfElse]


@dataclass(frozen=True)
class Program:
    quantum_operations: Tuple[str, ...]
    statements: Tuple[Statement, ...]
    classical_bit_count: int

