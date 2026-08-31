"""Immutable AST and normalized IR types for the supported QASM subset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Union


@dataclass(frozen=True, slots=True)
class Span:
    """One-based, half-open location in the original source."""

    line: int
    column: int
    end_line: int
    end_column: int


@dataclass(frozen=True, slots=True)
class NumberExpr:
    text: str
    span: Span


@dataclass(frozen=True, slots=True)
class PiExpr:
    span: Span


@dataclass(frozen=True, slots=True)
class UnaryExpr:
    operator: str
    operand: "Expression"
    span: Span


@dataclass(frozen=True, slots=True)
class BinaryExpr:
    left: "Expression"
    operator: str
    right: "Expression"
    span: Span


Expression = Union[NumberExpr, PiExpr, UnaryExpr, BinaryExpr]


@dataclass(frozen=True, slots=True)
class Include:
    path: str
    span: Span


@dataclass(frozen=True, slots=True)
class RegisterDecl:
    kind: str
    name: str
    size: int
    span: Span


@dataclass(frozen=True, slots=True)
class RegisterRef:
    name: str
    index: int | None
    span: Span


@dataclass(frozen=True, slots=True)
class GateStatement:
    name: str
    parameters: Tuple[Expression, ...]
    arguments: Tuple[RegisterRef, ...]
    span: Span


@dataclass(frozen=True, slots=True)
class MeasureStatement:
    source: RegisterRef
    target: RegisterRef
    span: Span


Statement = Union[GateStatement, MeasureStatement]


@dataclass(frozen=True, slots=True)
class Program:
    """Parsed QASM program before symbol resolution and broadcasting."""

    version: str
    includes: Tuple[Include, ...]
    declarations: Tuple[RegisterDecl, ...]
    statements: Tuple[Statement, ...]


@dataclass(frozen=True, slots=True)
class GateOp:
    """A scalar gate over flattened, zero-based qubit indices."""

    name: str
    params: Tuple[float, ...]
    qubits: Tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MeasureOp:
    """A scalar measurement from a flattened qubit to classical bit."""

    qubit: int
    cbit: int


Operation = Union[GateOp, MeasureOp]


@dataclass(frozen=True, slots=True)
class NormalizedCircuit:
    """Backend-neutral circuit with all register operations expanded."""

    qubit_count: int
    classical_count: int
    operations: Tuple[Operation, ...]


__all__ = [
    "BinaryExpr",
    "Expression",
    "GateOp",
    "GateStatement",
    "Include",
    "MeasureOp",
    "MeasureStatement",
    "NormalizedCircuit",
    "NumberExpr",
    "Operation",
    "PiExpr",
    "Program",
    "RegisterDecl",
    "RegisterRef",
    "Span",
    "Statement",
    "UnaryExpr",
]
