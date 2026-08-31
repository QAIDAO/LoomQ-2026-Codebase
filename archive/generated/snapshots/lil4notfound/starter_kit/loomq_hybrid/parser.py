"""Parser for the classical block embedded in Hybrid-QASM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from .model import (
    Assignment,
    BinaryExpression,
    ClassicalReference,
    Condition,
    Expression,
    IfStatement,
    IntegerLiteral,
    RegisterReference,
    Statement,
    UnaryExpression,
)


_TOKEN = re.compile(
    r"(?P<SPACE>\s+)"
    r"|(?P<CREF>[A-Za-z_]\w*\s*\[\s*\d+\s*\])"
    r"|(?P<INTEGER>\d+)"
    r"|(?P<EQUAL>==)"
    r"|(?P<NOT_EQUAL>!=)"
    r"|(?P<ASSIGN>=)"
    r"|(?P<PLUS>\+)"
    r"|(?P<MINUS>-)"
    r"|(?P<LPAREN>\()"
    r"|(?P<RPAREN>\))"
    r"|(?P<LBRACE>\{)"
    r"|(?P<RBRACE>\})"
    r"|(?P<SEMICOLON>;)"
    r"|(?P<IDENTIFIER>[A-Za-z_]\w*)"
)
_REGISTER = re.compile(r"r([1-9])$", re.I)
_CLASSICAL = re.compile(r"([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$")


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int


def parse_classical_block(source: str) -> Tuple[Statement, ...]:
    """Parse one classical block body into immutable statements."""
    return _Parser(_tokenize(source)).parse()


def _tokenize(source: str) -> Tuple[Token, ...]:
    tokens: List[Token] = []
    position = 0
    while position < len(source):
        match = _TOKEN.match(source, position)
        if match is None:
            excerpt = source[position : position + 24].splitlines()[0]
            raise ValueError(f"Invalid classical syntax near: {excerpt}")
        kind = match.lastgroup
        if kind != "SPACE":
            tokens.append(Token(str(kind), match.group(), position))
        position = match.end()
    tokens.append(Token("EOF", "", len(source)))
    return tuple(tokens)


class _Parser:
    def __init__(self, tokens: Tuple[Token, ...]):
        self.tokens = tokens
        self.index = 0

    def parse(self) -> Tuple[Statement, ...]:
        statements = []
        while self.current.kind != "EOF":
            statements.append(self._statement())
        return tuple(statements)

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def _advance(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def _expect(self, kind: str) -> Token:
        if self.current.kind != kind:
            raise ValueError(
                f"Expected {kind} at classical offset {self.current.position}, "
                f"found {self.current.value or 'end of input'}"
            )
        return self._advance()

    def _is_keyword(self, keyword: str) -> bool:
        return self.current.kind == "IDENTIFIER" and self.current.value.lower() == keyword

    def _expect_keyword(self, keyword: str) -> None:
        if not self._is_keyword(keyword):
            raise ValueError(f"Expected {keyword} at classical offset {self.current.position}")
        self._advance()

    def _statement(self) -> Statement:
        if self._is_keyword("if"):
            return self._if_statement()
        return self._assignment()

    def _assignment(self) -> Assignment:
        target = self._expect("IDENTIFIER")
        register = _REGISTER.fullmatch(target.value)
        if register is None:
            raise ValueError("Assignment target must be r1..r9")
        self._expect("ASSIGN")
        expression = self._expression()
        self._expect("SEMICOLON")
        return Assignment(int(register.group(1)), expression)

    def _if_statement(self) -> IfStatement:
        self._expect_keyword("if")
        self._expect("LPAREN")
        left = self._expression()
        if self.current.kind not in {"EQUAL", "NOT_EQUAL"}:
            raise ValueError("Hybrid-QASM conditions require == or !=")
        operator = self._advance().value
        right = self._expression()
        self._expect("RPAREN")
        then_body = self._block()
        self._expect_keyword("else")
        else_body = self._block()
        return IfStatement(Condition(operator, left, right), then_body, else_body)

    def _block(self) -> Tuple[Statement, ...]:
        self._expect("LBRACE")
        statements = []
        while self.current.kind != "RBRACE":
            if self.current.kind == "EOF":
                raise ValueError("Unterminated classical block")
            statements.append(self._statement())
        self._advance()
        return tuple(statements)

    def _expression(self) -> Expression:
        expression = self._unary()
        while self.current.kind in {"PLUS", "MINUS"}:
            operator = self._advance().value
            expression = BinaryExpression(operator, expression, self._unary())
        return expression

    def _unary(self) -> Expression:
        if self.current.kind in {"PLUS", "MINUS"}:
            operator = self._advance().value
            return UnaryExpression(operator, self._unary())
        return self._primary()

    def _primary(self) -> Expression:
        if self.current.kind == "INTEGER":
            return IntegerLiteral(int(self._advance().value))
        if self.current.kind == "IDENTIFIER":
            token = self._advance()
            register = _REGISTER.fullmatch(token.value)
            if register is None:
                raise ValueError(f"Unknown classical identifier: {token.value}")
            return RegisterReference(int(register.group(1)))
        if self.current.kind == "CREF":
            token = self._advance()
            match = _CLASSICAL.fullmatch(token.value)
            if match is None:
                raise ValueError(f"Invalid classical bit reference: {token.value}")
            return ClassicalReference(match.group(1), int(match.group(2)))
        if self.current.kind == "LPAREN":
            self._advance()
            expression = self._expression()
            self._expect("RPAREN")
            return expression
        raise ValueError(
            f"Expected expression at classical offset {self.current.position}, "
            f"found {self.current.value or 'end of input'}"
        )
