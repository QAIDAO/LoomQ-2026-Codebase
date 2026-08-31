"""Recursive-descent parser for the Hybrid-QASM classical mini-language."""

from __future__ import annotations

import re
from typing import List, Tuple

from .errors import HybridSyntaxError
from .lexer import Token, tokenize
from .nodes import (
    Assignment,
    BinaryExpression,
    Comparison,
    Expression,
    IfStatement,
    IntegerLiteral,
    MeasurementRef,
    RegisterRef,
    Statement,
)


_REGISTER = re.compile(r"r([1-9])$")


class ClassicalParser:
    def __init__(self, source: str, classical_bit_count: int) -> None:
        self._tokens = tokenize(source)
        self._position = 0
        self._classical_bit_count = classical_bit_count

    def parse(self) -> Tuple[Statement, ...]:
        statements = self._parse_statements(stop_value=None)
        self._expect_kind("eof")
        return tuple(statements)

    def _parse_statements(self, stop_value: str | None) -> List[Statement]:
        statements: List[Statement] = []
        while self._current.kind != "eof" and (
            stop_value is None or self._current.value != stop_value
        ):
            statements.append(self._parse_statement())
        return statements

    def _parse_statement(self) -> Statement:
        if self._current.value == "if":
            return self._parse_if()
        return self._parse_assignment()

    def _parse_assignment(self) -> Assignment:
        target_token = self._expect_kind("identifier")
        target = self._register_index(target_token)
        self._expect_value("=")
        expression = self._parse_expression()
        self._expect_value(";")
        return Assignment(target, expression)

    def _parse_if(self) -> IfStatement:
        self._expect_value("if")
        self._expect_value("(")
        left = self._parse_expression()
        operator = self._current.value
        if operator not in {"==", "!="}:
            self._error("expected == or !=")
        self._advance()
        right = self._parse_expression()
        self._expect_value(")")
        then_body = self._parse_block()
        self._expect_value("else")
        else_body = self._parse_block()
        return IfStatement(Comparison(operator, left, right), then_body, else_body)

    def _parse_block(self) -> Tuple[Statement, ...]:
        self._expect_value("{")
        statements = self._parse_statements(stop_value="}")
        self._expect_value("}")
        return tuple(statements)

    def _parse_expression(self) -> Expression:
        expression = self._parse_unary()
        while self._current.value in {"+", "-"}:
            operator = self._current.value
            self._advance()
            expression = BinaryExpression(operator, expression, self._parse_unary())
        return expression

    def _parse_unary(self) -> Expression:
        if self._current.value == "+":
            self._advance()
            return self._parse_unary()
        if self._current.value == "-":
            self._advance()
            operand = self._parse_unary()
            if isinstance(operand, IntegerLiteral):
                return IntegerLiteral(-operand.value)
            return BinaryExpression("-", IntegerLiteral(0), operand)
        return self._parse_atom()

    def _parse_atom(self) -> Expression:
        token = self._current
        if token.kind == "integer":
            self._advance()
            return IntegerLiteral(int(token.value))
        if token.value == "(":
            self._advance()
            expression = self._parse_expression()
            self._expect_value(")")
            return expression
        if token.kind == "identifier":
            register = _REGISTER.fullmatch(token.value)
            if register:
                self._advance()
                return RegisterRef(int(register.group(1)))
            if token.value == "c":
                return self._parse_measurement_ref()
        self._error("expected integer, r1..r9, c[k], or parenthesized expression")

    def _parse_measurement_ref(self) -> MeasurementRef:
        self._expect_value("c")
        self._expect_value("[")
        index_token = self._expect_kind("integer")
        self._expect_value("]")
        index = int(index_token.value)
        if index >= self._classical_bit_count:
            raise HybridSyntaxError(
                "classical bit c[%d] is outside declared c[%d] at line %d, column %d"
                % (
                    index,
                    self._classical_bit_count,
                    index_token.line,
                    index_token.column,
                )
            )
        return MeasurementRef(index)

    def _register_index(self, token: Token) -> int:
        match = _REGISTER.fullmatch(token.value)
        if not match:
            raise HybridSyntaxError(
                "assignment target must be r1..r9 at line %d, column %d"
                % (token.line, token.column)
            )
        return int(match.group(1))

    @property
    def _current(self) -> Token:
        return self._tokens[self._position]

    def _advance(self) -> Token:
        token = self._current
        if token.kind != "eof":
            self._position += 1
        return token

    def _expect_value(self, value: str) -> Token:
        if self._current.value != value:
            self._error("expected %r" % value)
        return self._advance()

    def _expect_kind(self, kind: str) -> Token:
        if self._current.kind != kind:
            self._error("expected %s" % kind)
        return self._advance()

    def _error(self, message: str):
        token = self._current
        raise HybridSyntaxError(
            "%s at line %d, column %d near %r"
            % (message, token.line, token.column, token.value)
        )


def parse_classical_block(
    source: str, classical_bit_count: int
) -> Tuple[Statement, ...]:
    return ClassicalParser(source, classical_bit_count).parse()

