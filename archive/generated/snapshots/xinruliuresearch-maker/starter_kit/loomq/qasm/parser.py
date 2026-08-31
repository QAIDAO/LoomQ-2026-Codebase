"""Recursive-descent parser for a deliberately bounded OpenQASM 2 grammar."""

from __future__ import annotations

import math
from typing import List

from .ast import (
    BinaryExpr,
    Expression,
    GateStatement,
    Include,
    MeasureStatement,
    NumberExpr,
    PiExpr,
    Program,
    RegisterDecl,
    RegisterRef,
    Span,
    Statement,
    UnaryExpr,
)
from .errors import QASMParseError
from .lexer import Token, TokenKind, lex


class Parser:
    """Build an AST from QASM tokens; no semantic expansion happens here."""

    def __init__(self, source: str) -> None:
        self._tokens = lex(source)
        self._position = 0

    def parse(self) -> Program:
        magic = self._expect(
            TokenKind.IDENTIFIER,
            "OPENQASM",
            "Start the file with 'OPENQASM 2.0;'.",
        )
        if magic.text != "OPENQASM":
            self._raise(
                magic,
                f"expected 'OPENQASM', found {magic.text!r}",
                "Start the file with 'OPENQASM 2.0;'.",
            )

        version = self._expect(
            TokenKind.NUMBER,
            "an OpenQASM version number",
            "Use version 2.0.",
        )
        try:
            version_value = float(version.text)
        except ValueError:
            version_value = math.nan
        if not math.isfinite(version_value) or version_value != 2.0:
            self._raise(
                version,
                f"unsupported OpenQASM version {version.text!r}",
                "Use 'OPENQASM 2.0;'.",
            )
        self._expect_text(";", "Terminate the OPENQASM header with ';'.")

        includes: List[Include] = []
        declarations: List[RegisterDecl] = []
        statements: List[Statement] = []

        while not self._at_end():
            token = self._current()
            if token.kind is not TokenKind.IDENTIFIER:
                self._raise(
                    token,
                    f"expected a declaration or operation, found {self._describe(token)}",
                    "Use include, qreg, creg, measure, or a supported gate name.",
                )
            if token.text == "include":
                includes.append(self._parse_include())
            elif token.text in ("qreg", "creg"):
                declarations.append(self._parse_declaration())
            elif token.text == "measure":
                statements.append(self._parse_measurement())
            else:
                statements.append(self._parse_gate())

        return Program(
            version.text,
            tuple(includes),
            tuple(declarations),
            tuple(statements),
        )

    def _parse_include(self) -> Include:
        start = self._advance()
        path = self._expect(
            TokenKind.STRING,
            "a quoted include path",
            'Write an include such as include "qelib1.inc";.',
        )
        end = self._expect_text(";", "Terminate the include with ';'.")
        return Include(path.text, self._span_tokens(start, end))

    def _parse_declaration(self) -> RegisterDecl:
        start = self._advance()
        name = self._expect(
            TokenKind.IDENTIFIER,
            "a register name",
            "Choose a name beginning with a letter or underscore.",
        )
        self._expect_text("[", "Put the register size in square brackets.")
        size = self._expect(
            TokenKind.NUMBER,
            "an integer register size",
            "Use a positive integer such as 2.",
        )
        if not size.text.isdigit():
            self._raise(
                size,
                f"register size must be an integer, found {size.text!r}",
                "Use a positive integer with no decimal point or exponent.",
            )
        try:
            size_value = int(size.text, 10)
        except ValueError:
            self._raise(
                size,
                "register size integer literal is too long",
                "Use a reasonably sized positive integer.",
            )
        self._expect_text("]", "Close the register size with ']'.")
        end = self._expect_text(";", "Terminate the register declaration with ';'.")
        return RegisterDecl(
            start.text,
            name.text,
            size_value,
            self._span_tokens(start, end),
        )

    def _parse_measurement(self) -> MeasureStatement:
        start = self._advance()
        source = self._parse_register_ref()
        arrow = self._current()
        if arrow.kind is not TokenKind.ARROW:
            self._raise(
                arrow,
                f"expected '->', found {self._describe(arrow)}",
                "Write measurement as 'measure qubit -> classical_bit;'.",
            )
        self._advance()
        target = self._parse_register_ref()
        end = self._expect_text(";", "Terminate the measurement with ';'.")
        return MeasureStatement(source, target, self._span_tokens(start, end))

    def _parse_gate(self) -> GateStatement:
        start = self._advance()
        parameters: List[Expression] = []
        if self._matches_text("("):
            if self._matches_text(")"):
                self._raise(
                    self._previous(),
                    "an empty gate parameter list is not valid",
                    "Remove the parentheses or provide the required expression.",
                )
            parameters.append(self._parse_expression())
            while self._matches_text(","):
                parameters.append(self._parse_expression())
            self._expect_text(")", "Close the gate parameter list with ')'.")

        arguments = [self._parse_register_ref()]
        while self._matches_text(","):
            arguments.append(self._parse_register_ref())
        end = self._expect_text(";", "Terminate the gate operation with ';'.")
        return GateStatement(
            start.text,
            tuple(parameters),
            tuple(arguments),
            self._span_tokens(start, end),
        )

    def _parse_register_ref(self) -> RegisterRef:
        name = self._expect(
            TokenKind.IDENTIFIER,
            "a register name",
            "Use a declared register name, optionally followed by [index].",
        )
        index = None
        end = name
        if self._matches_text("["):
            index_token = self._expect(
                TokenKind.NUMBER,
                "an integer register index",
                "Use a non-negative integer index.",
            )
            if not index_token.text.isdigit():
                self._raise(
                    index_token,
                    f"register index must be an integer, found {index_token.text!r}",
                    "Use a non-negative integer with no sign, decimal point, or exponent.",
                )
            try:
                index = int(index_token.text, 10)
            except ValueError:
                self._raise(
                    index_token,
                    "register index integer literal is too long",
                    "Use an index that fits the declared register.",
                )
            end = self._expect_text("]", "Close the register index with ']'.")
        return RegisterRef(name.text, index, self._span_tokens(name, end))

    def _parse_expression(self) -> Expression:
        return self._parse_additive()

    def _parse_additive(self) -> Expression:
        expression = self._parse_multiplicative()
        while self._current().kind is TokenKind.SYMBOL and self._current().text in (
            "+",
            "-",
        ):
            operator = self._advance()
            right = self._parse_multiplicative()
            expression = BinaryExpr(
                expression,
                operator.text,
                right,
                self._merge_spans(expression.span, right.span),
            )
        return expression

    def _parse_multiplicative(self) -> Expression:
        expression = self._parse_unary()
        while self._current().kind is TokenKind.SYMBOL and self._current().text in (
            "*",
            "/",
        ):
            operator = self._advance()
            right = self._parse_unary()
            expression = BinaryExpr(
                expression,
                operator.text,
                right,
                self._merge_spans(expression.span, right.span),
            )
        return expression

    def _parse_unary(self) -> Expression:
        if self._current().kind is TokenKind.SYMBOL and self._current().text in (
            "+",
            "-",
        ):
            operator = self._advance()
            operand = self._parse_unary()
            return UnaryExpr(
                operator.text,
                operand,
                Span(
                    operator.line,
                    operator.column,
                    operand.span.end_line,
                    operand.span.end_column,
                ),
            )
        return self._parse_primary()

    def _parse_primary(self) -> Expression:
        token = self._current()
        if token.kind is TokenKind.NUMBER:
            self._advance()
            return NumberExpr(token.text, self._span_token(token))
        if token.kind is TokenKind.IDENTIFIER:
            self._advance()
            if token.text == "pi":
                return PiExpr(self._span_token(token))
            self._raise(
                token,
                f"unknown expression symbol {token.text!r}",
                "Only the constant 'pi' is supported in parameter expressions.",
            )
        if token.kind is TokenKind.SYMBOL and token.text == "(":
            self._advance()
            expression = self._parse_expression()
            self._expect_text(")", "Close the parameter subexpression with ')'.")
            return expression
        self._raise(
            token,
            f"expected a parameter expression, found {self._describe(token)}",
            "Use numbers, pi, parentheses, unary signs, or + - * /.",
        )

    def _current(self) -> Token:
        return self._tokens[self._position]

    def _previous(self) -> Token:
        return self._tokens[self._position - 1]

    def _advance(self) -> Token:
        token = self._current()
        if token.kind is not TokenKind.EOF:
            self._position += 1
        return token

    def _at_end(self) -> bool:
        return self._current().kind is TokenKind.EOF

    def _matches_text(self, text: str) -> bool:
        if self._current().text != text:
            return False
        self._advance()
        return True

    def _expect(self, kind: TokenKind, expected: str, suggestion: str) -> Token:
        token = self._current()
        if token.kind is not kind:
            self._raise(
                token,
                f"expected {expected}, found {self._describe(token)}",
                suggestion,
            )
        return self._advance()

    def _expect_text(self, text: str, suggestion: str) -> Token:
        token = self._current()
        if token.text != text:
            self._raise(
                token,
                f"expected {text!r}, found {self._describe(token)}",
                suggestion,
            )
        return self._advance()

    @staticmethod
    def _describe(token: Token) -> str:
        if token.kind is TokenKind.EOF:
            return "end of input"
        return repr(token.text)

    @staticmethod
    def _raise(token: Token, message: str, suggestion: str) -> None:
        raise QASMParseError(message, token.line, token.column, suggestion)

    @staticmethod
    def _span_token(token: Token) -> Span:
        return Span(token.line, token.column, token.end_line, token.end_column)

    @staticmethod
    def _span_tokens(start: Token, end: Token) -> Span:
        return Span(start.line, start.column, end.end_line, end.end_column)

    @staticmethod
    def _merge_spans(left: Span, right: Span) -> Span:
        return Span(left.line, left.column, right.end_line, right.end_column)


def parse_qasm2(source: str) -> Program:
    """Parse ``source`` into an immutable AST for the supported QASM 2 subset."""

    return Parser(source).parse()


__all__ = ["Parser", "parse_qasm2"]
