"""Immutable AST nodes for the Hybrid-QASM classical subset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Union


@dataclass(frozen=True)
class IntegerLiteral:
    value: int


@dataclass(frozen=True)
class RegisterReference:
    """A source-level ``r1`` .. ``r9`` reference."""

    index: int


@dataclass(frozen=True)
class MeasurementReference:
    """A source-level ``c[k]`` measurement reference."""

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
    MeasurementReference,
    UnaryExpression,
    BinaryExpression,
]


@dataclass(frozen=True)
class Condition:
    operator: str
    left: Expression
    right: Expression


@dataclass(frozen=True)
class Assignment:
    target: RegisterReference
    value: Expression


@dataclass(frozen=True)
class IfStatement:
    condition: Condition
    then_body: Tuple["ClassicalStatement", ...]
    else_body: Tuple["ClassicalStatement", ...] = ()
    has_else: bool = False


ClassicalStatement = Union[Assignment, IfStatement]


@dataclass(frozen=True)
class QuantumStatement:
    """A normalized top-level OpenQASM statement."""

    text: str
    is_operation: bool


@dataclass(frozen=True)
class ClassicalBlock:
    statements: Tuple[ClassicalStatement, ...]


ProgramSegment = Union[QuantumStatement, ClassicalBlock]


@dataclass(frozen=True)
class HybridProgram:
    """Hybrid program with source-order segments retained."""

    segments: Tuple[ProgramSegment, ...]
    declared_measurements: Tuple[int, ...] = ()

    @property
    def quantum_operations(self) -> Tuple[str, ...]:
        return tuple(
            segment.text
            for segment in self.segments
            if isinstance(segment, QuantumStatement) and segment.is_operation
        )

    @property
    def classical_statements(self) -> Tuple[ClassicalStatement, ...]:
        statements = []
        for segment in self.segments:
            if isinstance(segment, ClassicalBlock):
                statements.extend(segment.statements)
        return tuple(statements)
