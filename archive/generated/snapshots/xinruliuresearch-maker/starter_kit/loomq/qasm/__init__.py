"""Clean-room OpenQASM 2 front end and normalized circuit IR.

The public pipeline is intentionally small::

    program = parse_qasm2(source)
    circuit = normalize_program(program)

or, equivalently, ``parse_and_normalize(source)``.  No include files are read,
no input is evaluated as Python, and only the documented gate subset is
accepted.
"""

from __future__ import annotations

from .ast import (
    BinaryExpr,
    Expression,
    GateOp,
    GateStatement,
    Include,
    MeasureOp,
    MeasureStatement,
    NormalizedCircuit,
    NumberExpr,
    Operation,
    PiExpr,
    Program,
    RegisterDecl,
    RegisterRef,
    Span,
    Statement,
    UnaryExpr,
)
from .errors import (
    QASMError,
    QASMLexError,
    QASMParseError,
    QASMSerializationError,
    QASMSemanticError,
)
from .normalize import Normalizer, normalize_program
from .parser import Parser, parse_qasm2
from .serialize import serialize_qasm2


def parse_and_normalize(source: str) -> NormalizedCircuit:
    """Parse and semantically normalize supported OpenQASM 2 source."""

    return normalize_program(parse_qasm2(source))


__all__ = [
    "BinaryExpr",
    "Expression",
    "GateOp",
    "GateStatement",
    "Include",
    "MeasureOp",
    "MeasureStatement",
    "NormalizedCircuit",
    "Normalizer",
    "NumberExpr",
    "Operation",
    "Parser",
    "PiExpr",
    "Program",
    "QASMError",
    "QASMLexError",
    "QASMParseError",
    "QASMSerializationError",
    "QASMSemanticError",
    "RegisterDecl",
    "RegisterRef",
    "Span",
    "Statement",
    "UnaryExpr",
    "normalize_program",
    "parse_and_normalize",
    "parse_qasm2",
    "serialize_qasm2",
]
