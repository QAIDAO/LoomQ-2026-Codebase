from dataclasses import dataclass
from typing import List, Optional


# ============================================================
# Expressions
# ============================================================


class Expr:
    pass


@dataclass(frozen=True)
class IntLiteral(Expr):
    value: int


@dataclass(frozen=True)
class RegisterRef(Expr):
    index: int


@dataclass(frozen=True)
class MeasurementRef(Expr):
    index: int


@dataclass(frozen=True)
class UnaryOp(Expr):
    op: str
    operand: Expr


@dataclass(frozen=True)
class BinaryOp(Expr):
    left: Expr
    op: str
    right: Expr


# ============================================================
# Statements
# ============================================================


class Stmt:
    pass


@dataclass(frozen=True)
class Assign(Stmt):
    target: int
    value: Expr


@dataclass(frozen=True)
class IfStmt(Stmt):
    condition: BinaryOp
    then_body: List[Stmt]
    else_body: Optional[List[Stmt]]


@dataclass(frozen=True)
class ClassicalBlock:
    statements: List[Stmt]
