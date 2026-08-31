"""Semantic analysis and scalar normalization for parsed QASM programs."""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import math
from typing import Dict, List, Sequence, Tuple

from ._gates import GATE_SIGNATURES
from .ast import (
    BinaryExpr,
    Expression,
    GateOp,
    GateStatement,
    MeasureOp,
    MeasureStatement,
    NormalizedCircuit,
    NumberExpr,
    PiExpr,
    Program,
    RegisterDecl,
    RegisterRef,
    Span,
    UnaryExpr,
)
from .errors import QASMSemanticError


_RESERVED_NAMES = {
    "OPENQASM",
    "include",
    "qreg",
    "creg",
    "gate",
    "opaque",
    "barrier",
    "measure",
    "reset",
    "if",
    "pi",
}.union(GATE_SIGNATURES)


@dataclass(frozen=True, slots=True)
class _Register:
    kind: str
    name: str
    size: int
    offset: int
    span: Span


@dataclass(frozen=True, slots=True)
class _ResolvedRef:
    indices: Tuple[int, ...]
    whole_register: bool
    register: _Register


class Normalizer:
    """Resolve symbols, evaluate parameters, and expand register broadcasts."""

    def __init__(self, program: Program) -> None:
        if not isinstance(program, Program):
            raise TypeError("program must be a qasm.ast.Program")
        self._program = program
        self._registers: Dict[str, _Register] = {}
        self._qubit_count = 0
        self._classical_count = 0

    def normalize(self) -> NormalizedCircuit:
        self._validate_program_metadata()
        for declaration in self._program.declarations:
            self._declare(declaration)

        operations: List[GateOp | MeasureOp] = []
        for statement in self._program.statements:
            if isinstance(statement, GateStatement):
                operations.extend(self._normalize_gate(statement))
            elif isinstance(statement, MeasureStatement):
                operations.extend(self._normalize_measurement(statement))
            else:
                raise QASMSemanticError(
                    f"unsupported AST statement {type(statement).__name__}",
                    1,
                    1,
                    "Build the program with GateStatement or MeasureStatement nodes.",
                )

        return NormalizedCircuit(
            self._qubit_count,
            self._classical_count,
            tuple(operations),
        )

    def _validate_program_metadata(self) -> None:
        try:
            version = float(self._program.version)
        except (TypeError, ValueError, OverflowError):
            version = math.nan
        if not math.isfinite(version) or version != 2.0:
            raise QASMSemanticError(
                f"unsupported OpenQASM version {self._program.version!r}",
                1,
                1,
                "Use OpenQASM version 2.0.",
            )
        for include in self._program.includes:
            if include.path != "qelib1.inc":
                self._error(
                    include.span,
                    f"unsupported include path {include.path!r}",
                    'Only the standard include "qelib1.inc" is supported; no files are read.',
                )

    def _declare(self, declaration: RegisterDecl) -> None:
        if declaration.kind not in ("qreg", "creg"):
            self._error(
                declaration.span,
                f"unknown register kind {declaration.kind!r}",
                "Use qreg for qubits or creg for classical bits.",
            )
        if declaration.name in self._registers:
            first = self._registers[declaration.name]
            self._error(
                declaration.span,
                f"duplicate declaration of register {declaration.name!r}; "
                f"first declared at line {first.span.line}, column {first.span.column}",
                "Rename this register or remove the duplicate declaration.",
            )
        if declaration.name in _RESERVED_NAMES:
            self._error(
                declaration.span,
                f"register name {declaration.name!r} is reserved",
                "Choose a non-keyword identifier such as data_q or result_c.",
            )
        if isinstance(declaration.size, bool) or not isinstance(declaration.size, int):
            self._error(
                declaration.span,
                f"register {declaration.name!r} has a non-integer size",
                "Use a positive integer register size.",
            )
        if declaration.size <= 0:
            self._error(
                declaration.span,
                f"register {declaration.name!r} must have positive size, got {declaration.size}",
                "Declare at least one bit, for example [1].",
            )

        if declaration.kind == "qreg":
            offset = self._qubit_count
            self._qubit_count += declaration.size
        else:
            offset = self._classical_count
            self._classical_count += declaration.size
        self._registers[declaration.name] = _Register(
            declaration.kind,
            declaration.name,
            declaration.size,
            offset,
            declaration.span,
        )

    def _normalize_gate(self, statement: GateStatement) -> Sequence[GateOp]:
        signature = GATE_SIGNATURES.get(statement.name)
        if signature is None:
            suggestion = self._gate_suggestion(statement.name)
            self._error(
                statement.span,
                f"unsupported gate {statement.name!r}",
                suggestion,
            )
        parameter_arity, qubit_arity = signature
        if len(statement.parameters) != parameter_arity:
            self._error(
                statement.span,
                f"gate {statement.name!r} expects {parameter_arity} parameter(s), "
                f"got {len(statement.parameters)}",
                self._parameter_arity_suggestion(statement.name, parameter_arity),
            )
        if len(statement.arguments) != qubit_arity:
            self._error(
                statement.span,
                f"gate {statement.name!r} expects {qubit_arity} qubit argument(s), "
                f"got {len(statement.arguments)}",
                f"Pass exactly {qubit_arity} quantum register reference(s).",
            )

        params = tuple(self._evaluate(expression) for expression in statement.parameters)
        resolved = tuple(
            self._resolve(reference, "qreg") for reference in statement.arguments
        )
        whole_widths = [
            len(reference.indices) for reference in resolved if reference.whole_register
        ]
        if whole_widths and any(width != whole_widths[0] for width in whole_widths[1:]):
            details = ", ".join(
                f"{reference.register.name}[{len(reference.indices)}]"
                for reference in resolved
                if reference.whole_register
            )
            self._error(
                statement.span,
                f"cannot broadcast gate {statement.name!r} across unequal register sizes: {details}",
                "Use equally sized whole registers or indexed qubits.",
            )
        width = whole_widths[0] if whole_widths else 1

        operations: List[GateOp] = []
        for position in range(width):
            qubits = tuple(
                reference.indices[position]
                if reference.whole_register
                else reference.indices[0]
                for reference in resolved
            )
            operations.append(GateOp(statement.name, params, qubits))
        return operations

    def _normalize_measurement(
        self, statement: MeasureStatement
    ) -> Sequence[MeasureOp]:
        source = self._resolve(statement.source, "qreg")
        target = self._resolve(statement.target, "creg")

        if source.whole_register != target.whole_register:
            self._error(
                statement.span,
                "measurement operands must both be indexed bits or both be whole registers",
                "Index both operands, or remove both indices for a register measurement.",
            )
        if len(source.indices) != len(target.indices):
            self._error(
                statement.span,
                f"measurement register sizes differ: {source.register.name} has "
                f"{len(source.indices)} bit(s), {target.register.name} has "
                f"{len(target.indices)}",
                "Measure into a classical register of the same size.",
            )
        return [
            MeasureOp(qubit, cbit)
            for qubit, cbit in zip(source.indices, target.indices)
        ]

    def _resolve(self, reference: RegisterRef, expected_kind: str) -> _ResolvedRef:
        register = self._registers.get(reference.name)
        kind_label = "quantum" if expected_kind == "qreg" else "classical"
        if register is None:
            candidates = [
                item.name
                for item in self._registers.values()
                if item.kind == expected_kind
            ]
            matches = difflib.get_close_matches(reference.name, candidates, n=1)
            if matches:
                suggestion = f"Did you mean {matches[0]!r}?"
            else:
                suggestion = f"Declare a {kind_label} register before using it."
            self._error(
                reference.span,
                f"unknown register {reference.name!r}",
                suggestion,
            )
        if register.kind != expected_kind:
            actual_label = "quantum" if register.kind == "qreg" else "classical"
            self._error(
                reference.span,
                f"register {reference.name!r} is {actual_label}, but a {kind_label} register is required",
                f"Use a declared {kind_label} register here.",
            )

        if reference.index is None:
            return _ResolvedRef(
                tuple(range(register.offset, register.offset + register.size)),
                True,
                register,
            )
        if isinstance(reference.index, bool) or not isinstance(reference.index, int):
            self._error(
                reference.span,
                f"register index for {reference.name!r} is not an integer",
                "Use a non-negative integer index.",
            )
        if reference.index < 0 or reference.index >= register.size:
            self._error(
                reference.span,
                f"index {reference.index} is out of range for register {reference.name!r} "
                f"of size {register.size}",
                f"Use an index from 0 through {register.size - 1}.",
            )
        return _ResolvedRef(
            (register.offset + reference.index,),
            False,
            register,
        )

    def _evaluate(self, expression: Expression) -> float:
        if isinstance(expression, NumberExpr):
            try:
                value = float(expression.text)
            except (TypeError, ValueError, OverflowError):
                self._error(
                    expression.span,
                    f"invalid numeric literal {expression.text!r}",
                    "Use a decimal number with an optional scientific exponent.",
                )
            return self._finite(value, expression.span)
        if isinstance(expression, PiExpr):
            return math.pi
        if isinstance(expression, UnaryExpr):
            operand = self._evaluate(expression.operand)
            if expression.operator == "+":
                value = operand
            elif expression.operator == "-":
                value = -operand
            else:
                self._error(
                    expression.span,
                    f"unsupported unary operator {expression.operator!r}",
                    "Use unary + or -.",
                )
            return self._finite(value, expression.span)
        if isinstance(expression, BinaryExpr):
            left = self._evaluate(expression.left)
            right = self._evaluate(expression.right)
            if expression.operator == "+":
                value = left + right
            elif expression.operator == "-":
                value = left - right
            elif expression.operator == "*":
                value = left * right
            elif expression.operator == "/":
                if right == 0.0:
                    self._error(
                        expression.right.span,
                        "division by zero in gate parameter expression",
                        "Use a non-zero denominator.",
                    )
                value = left / right
            else:
                self._error(
                    expression.span,
                    f"unsupported binary operator {expression.operator!r}",
                    "Use +, -, *, or /.",
                )
            return self._finite(value, expression.span)
        span = getattr(expression, "span", Span(1, 1, 1, 1))
        self._error(
            span,
            f"unsupported expression node {type(expression).__name__}",
            "Use numeric, pi, unary, or binary expression nodes.",
        )

    def _finite(self, value: float, span: Span) -> float:
        if not math.isfinite(value):
            self._error(
                span,
                "gate parameter expression is not finite",
                "Use finite operands whose calculation does not overflow.",
            )
        # Avoid propagating a surprising negative zero into canonical output.
        return 0.0 if value == 0.0 else value

    @staticmethod
    def _gate_suggestion(name: str) -> str:
        if name.lower() in GATE_SIGNATURES:
            return f"Gate names are case-sensitive; use {name.lower()!r}."
        matches = difflib.get_close_matches(name, GATE_SIGNATURES.keys(), n=1)
        if matches:
            return f"Did you mean {matches[0]!r}?"
        return "Use one of: " + ", ".join(GATE_SIGNATURES) + "."

    @staticmethod
    def _parameter_arity_suggestion(name: str, arity: int) -> str:
        if arity == 0:
            return f"Write {name} without a parameter list."
        return f"Write {name}(expression) with exactly {arity} parameter expression(s)."

    @staticmethod
    def _error(span: Span, message: str, suggestion: str) -> None:
        raise QASMSemanticError(message, span.line, span.column, suggestion)


def normalize_program(program: Program) -> NormalizedCircuit:
    """Validate and flatten a parsed :class:`Program`."""

    return Normalizer(program).normalize()


__all__ = ["Normalizer", "normalize_program"]
