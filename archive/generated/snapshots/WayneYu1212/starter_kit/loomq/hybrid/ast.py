"""Immutable AST for the published Hybrid-QASM classical language."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True, slots=True)
class IntLiteral:
    value: int


@dataclass(frozen=True, slots=True)
class RegisterRef:
    index: int


@dataclass(frozen=True, slots=True)
class MeasurementRef:
    index: int


@dataclass(frozen=True, slots=True)
class BinaryExpr:
    operator: str
    left: "Expr"
    right: "Expr"


Expr = Union[IntLiteral, RegisterRef, MeasurementRef, BinaryExpr]


@dataclass(frozen=True, slots=True)
class Condition:
    operator: str
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class Assign:
    target: int
    value: Expr


@dataclass(frozen=True, slots=True)
class IfStmt:
    condition: Condition
    then_body: tuple["Stmt", ...]
    else_body: tuple["Stmt", ...]


Stmt = Union[Assign, IfStmt]


@dataclass(frozen=True, slots=True)
class HybridProgram:
    quantum_ops: tuple[str, ...]
    statements: tuple[Stmt, ...]
    measurement_indices: frozenset[int]
