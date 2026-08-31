"""A small, deterministic lexer for the supported OpenQASM 2 subset."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List

from .errors import QASMLexError


class TokenKind(str, Enum):
    IDENTIFIER = "identifier"
    NUMBER = "number"
    STRING = "string"
    SYMBOL = "symbol"
    ARROW = "arrow"
    EOF = "end of input"


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    line: int
    column: int
    end_line: int
    end_column: int


class Lexer:
    """Convert source characters to tokens without executing or rewriting it."""

    def __init__(self, source: str) -> None:
        if not isinstance(source, str):
            raise TypeError("QASM source must be a string")
        self._source = source
        self._offset = 0
        self._line = 1
        self._column = 1

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        if self._current() == "\ufeff":
            self._advance()

        while self._offset < len(self._source):
            char = self._current()
            if char in " \t\v\f\r\n":
                self._skip_whitespace()
                continue
            if char == "/" and self._peek() == "/":
                self._skip_comment()
                continue
            if self._is_identifier_start(char):
                tokens.append(self._identifier())
                continue
            if self._is_digit(char) or (
                char == "." and self._is_digit(self._peek())
            ):
                tokens.append(self._number())
                continue
            if char == '"':
                tokens.append(self._string())
                continue
            if char == "-" and self._peek() == ">":
                tokens.append(self._arrow())
                continue
            if char in ";,()[]+-*/":
                tokens.append(self._single(TokenKind.SYMBOL))
                continue
            raise QASMLexError(
                f"unexpected character {char!r}",
                self._line,
                self._column,
                "Remove it or replace it with a supported QASM token.",
            )

        tokens.append(
            Token(
                TokenKind.EOF,
                "",
                self._line,
                self._column,
                self._line,
                self._column,
            )
        )
        return tokens

    def _current(self) -> str:
        if self._offset >= len(self._source):
            return ""
        return self._source[self._offset]

    def _peek(self, distance: int = 1) -> str:
        position = self._offset + distance
        if position >= len(self._source):
            return ""
        return self._source[position]

    def _advance(self) -> str:
        char = self._current()
        if not char:
            return ""
        self._offset += 1
        if char == "\r":
            if self._current() == "\n":
                self._offset += 1
            self._line += 1
            self._column = 1
        elif char == "\n":
            self._line += 1
            self._column = 1
        elif char == "\t":
            # Columns count source characters, not display-cell tab stops.
            self._column += 1
        else:
            self._column += 1
        return char

    def _skip_whitespace(self) -> None:
        while self._current() in " \t\v\f\r\n" and self._current():
            self._advance()

    def _skip_comment(self) -> None:
        self._advance()
        self._advance()
        while self._current() not in ("", "\r", "\n"):
            self._advance()

    @staticmethod
    def _is_identifier_start(char: str) -> bool:
        return char == "_" or "A" <= char <= "Z" or "a" <= char <= "z"

    @staticmethod
    def _is_identifier_part(char: str) -> bool:
        return Lexer._is_identifier_start(char) or Lexer._is_digit(char)

    @staticmethod
    def _is_digit(char: str) -> bool:
        return "0" <= char <= "9"

    def _identifier(self) -> Token:
        start_offset = self._offset
        line, column = self._line, self._column
        while self._is_identifier_part(self._current()):
            self._advance()
        return Token(
            TokenKind.IDENTIFIER,
            self._source[start_offset : self._offset],
            line,
            column,
            self._line,
            self._column,
        )

    def _number(self) -> Token:
        start_offset = self._offset
        line, column = self._line, self._column

        if self._current() == ".":
            self._advance()
            while self._is_digit(self._current()):
                self._advance()
        else:
            while self._is_digit(self._current()):
                self._advance()
            if self._current() == ".":
                self._advance()
                while self._is_digit(self._current()):
                    self._advance()

        if self._current() in ("e", "E"):
            exponent_line, exponent_column = self._line, self._column
            self._advance()
            if self._current() in ("+", "-"):
                self._advance()
            if not self._is_digit(self._current()):
                raise QASMLexError(
                    "scientific notation exponent has no digits",
                    exponent_line,
                    exponent_column,
                    "Add one or more digits after the exponent marker.",
                )
            while self._is_digit(self._current()):
                self._advance()

        return Token(
            TokenKind.NUMBER,
            self._source[start_offset : self._offset],
            line,
            column,
            self._line,
            self._column,
        )

    def _string(self) -> Token:
        line, column = self._line, self._column
        self._advance()
        value_start = self._offset
        while self._current() not in ('"', "", "\r", "\n"):
            if self._current() == "\\":
                raise QASMLexError(
                    "escape sequences are not valid in QASM include paths",
                    self._line,
                    self._column,
                    "Use a plain quoted include path such as \"qelib1.inc\".",
                )
            self._advance()
        if self._current() != '"':
            raise QASMLexError(
                "unterminated string literal",
                line,
                column,
                "Close the include path with a double quote.",
            )
        value = self._source[value_start : self._offset]
        self._advance()
        return Token(
            TokenKind.STRING,
            value,
            line,
            column,
            self._line,
            self._column,
        )

    def _arrow(self) -> Token:
        line, column = self._line, self._column
        self._advance()
        self._advance()
        return Token(
            TokenKind.ARROW,
            "->",
            line,
            column,
            self._line,
            self._column,
        )

    def _single(self, kind: TokenKind) -> Token:
        line, column = self._line, self._column
        text = self._advance()
        return Token(kind, text, line, column, self._line, self._column)


def lex(source: str) -> List[Token]:
    return Lexer(source).tokenize()


__all__ = ["Lexer", "Token", "TokenKind", "lex"]
