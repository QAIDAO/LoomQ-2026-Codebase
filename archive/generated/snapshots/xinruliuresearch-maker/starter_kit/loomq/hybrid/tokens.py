"""Tokens and lexer for the deterministic Hybrid-QASM parser.

The lexer understands the punctuation needed by both the OpenQASM envelope and
the small classical language.  Keeping a single token stream lets the parser
remove classical blocks without using regular-expression brace matching (which
would be fragile in comments and strings).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class HybridSyntaxError(ValueError):
    """Raised when a Hybrid-QASM source cannot be parsed."""


class TokenKind(Enum):
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    SEMICOLON = auto()
    COMMA = auto()
    LBRACE = auto()
    RBRACE = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    ASSIGN = auto()
    EQUAL = auto()
    NOT_EQUAL = auto()
    ARROW = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str
    line: int
    column: int


_SINGLE_CHARACTER_TOKENS = {
    ";": TokenKind.SEMICOLON,
    ",": TokenKind.COMMA,
    "{": TokenKind.LBRACE,
    "}": TokenKind.RBRACE,
    "(": TokenKind.LPAREN,
    ")": TokenKind.RPAREN,
    "[": TokenKind.LBRACKET,
    "]": TokenKind.RBRACKET,
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.STAR,
    "/": TokenKind.SLASH,
    "=": TokenKind.ASSIGN,
}


class HybridLexer:
    """Turn Hybrid-QASM source text into location-aware tokens."""

    def __init__(self, source: str):
        if not isinstance(source, str):
            raise TypeError("Hybrid-QASM source must be a string")
        self._source = source
        self._length = len(source)
        self._index = 0
        self._line = 1
        self._column = 1

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        while self._index < self._length:
            char = self._peek()
            if self._index == 0 and char == "\ufeff":
                self._advance()
                continue
            if char.isspace():
                self._advance()
                continue
            if char == "/" and self._peek(1) == "/":
                self._skip_line_comment()
                continue
            if char == "/" and self._peek(1) == "*":
                self._skip_block_comment()
                continue

            line, column = self._line, self._column
            if char.isalpha() or char == "_":
                tokens.append(Token(TokenKind.IDENTIFIER, self._identifier(), line, column))
                continue
            if char.isdigit() or (char == "." and self._peek(1).isdigit()):
                tokens.append(Token(TokenKind.NUMBER, self._number(), line, column))
                continue
            if char in ('"', "'"):
                tokens.append(Token(TokenKind.STRING, self._string(), line, column))
                continue

            pair = char + self._peek(1)
            if pair == "==":
                self._advance(2)
                tokens.append(Token(TokenKind.EQUAL, pair, line, column))
                continue
            if pair == "!=":
                self._advance(2)
                tokens.append(Token(TokenKind.NOT_EQUAL, pair, line, column))
                continue
            if pair == "->":
                self._advance(2)
                tokens.append(Token(TokenKind.ARROW, pair, line, column))
                continue
            kind = _SINGLE_CHARACTER_TOKENS.get(char)
            if kind is not None:
                self._advance()
                tokens.append(Token(kind, char, line, column))
                continue
            self._fail(f"unexpected character {char!r}", line, column)

        tokens.append(Token(TokenKind.EOF, "", self._line, self._column))
        return tokens

    def _peek(self, offset: int = 0) -> str:
        position = self._index + offset
        return self._source[position] if position < self._length else ""

    def _advance(self, count: int = 1) -> None:
        for _ in range(count):
            if self._index >= self._length:
                return
            char = self._source[self._index]
            self._index += 1
            if char == "\n":
                self._line += 1
                self._column = 1
            else:
                self._column += 1

    def _identifier(self) -> str:
        start = self._index
        while True:
            char = self._peek()
            if not (char.isalnum() or char == "_"):
                break
            self._advance()
        return self._source[start : self._index]

    def _number(self) -> str:
        start = self._index
        saw_digits = False
        while self._peek().isdigit():
            saw_digits = True
            self._advance()
        if self._peek() == ".":
            self._advance()
            while self._peek().isdigit():
                saw_digits = True
                self._advance()
        if not saw_digits:
            self._fail("invalid numeric literal", self._line, self._column)
        if self._peek() in ("e", "E"):
            exponent_line, exponent_column = self._line, self._column
            self._advance()
            if self._peek() in ("+", "-"):
                self._advance()
            exponent_start = self._index
            while self._peek().isdigit():
                self._advance()
            if exponent_start == self._index:
                self._fail("invalid exponent", exponent_line, exponent_column)
        return self._source[start : self._index]

    def _string(self) -> str:
        start = self._index
        quote = self._peek()
        self._advance()
        escaped = False
        while self._index < self._length:
            char = self._peek()
            if char == "\n" and not escaped:
                self._fail("unterminated string literal", self._line, self._column)
            self._advance()
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                return self._source[start : self._index]
        self._fail("unterminated string literal", self._line, self._column)
        raise AssertionError("unreachable")

    def _skip_line_comment(self) -> None:
        self._advance(2)
        while self._index < self._length and self._peek() != "\n":
            self._advance()

    def _skip_block_comment(self) -> None:
        line, column = self._line, self._column
        self._advance(2)
        while self._index < self._length:
            if self._peek() == "*" and self._peek(1) == "/":
                self._advance(2)
                return
            self._advance()
        self._fail("unterminated block comment", line, column)

    @staticmethod
    def _fail(message: str, line: int, column: int) -> None:
        raise HybridSyntaxError(f"line {line}, column {column}: {message}")


def tokenize(source: str) -> List[Token]:
    """Convenience function used by tests and the parser."""

    return HybridLexer(source).tokenize()
