#!/usr/bin/env python3
"""Shared tokenizer for OpenQASM 2.0 and the Hybrid-QASM classical block.

One lexer feeds both the quantum front-end (parser.py) and the hybrid
compiler (hybrid_compiler.py). Tokens carry line/column so every later
stage can raise precise, user-facing syntax errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


class LexError(ValueError):
    def __init__(self, message: str, line: int, col: int):
        super().__init__("line %d col %d: %s" % (line, col, message))
        self.line = line
        self.col = col


@dataclass(frozen=True)
class Token:
    kind: str          # "id" | "num" | "sym"
    value: str         # raw text; numbers keep their literal spelling
    line: int
    col: int

    @property
    def number(self) -> float:
        text = self.value
        try:
            return float(text)
        except ValueError:
            raise LexError("bad numeric literal %r" % text, self.line, self.col)

    @property
    def integer(self) -> int:
        value = float(self.value)
        if value != int(value):
            raise LexError("expected an integer, got %r" % self.value,
                           self.line, self.col)
        return int(value)

    def is_id(self, *names: str) -> bool:
        return self.kind == "id" and (not names or self.value.lower() in names)

    def is_sym(self, *symbols: str) -> bool:
        return self.kind == "sym" and self.value in symbols


_SYMBOLS = (
    "->", "==", "!=",
    "[", "]", "(", ")", "{", "}", ",", ";", "=", "+", "-", "*", "/",
)


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    i, line, col, length = 0, 1, 1, len(source)
    while i < length:
        ch = source[i]
        if ch == "\n":
            i += 1
            line += 1
            col = 1
            continue
        if ch in " \t\r":
            i += 1
            col += 1
            continue
        if source.startswith("//", i):
            end = source.find("\n", i)
            i = length if end < 0 else end
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            if end < 0:
                raise LexError("unterminated block comment", line, col)
            skipped = source[i:end + 2]
            line += skipped.count("\n")
            last_nl = skipped.rfind("\n")
            col = (len(skipped) - last_nl) if last_nl >= 0 else col + len(skipped)
            i = end + 2
            continue
        start_line, start_col = line, col
        if ch == '"':
            end = source.find('"', i + 1)
            if end < 0:
                raise LexError("unterminated string literal", line, col)
            tokens.append(Token("str", source[i + 1:end], start_line, start_col))
            advance = end + 1 - i
            i = end + 1
            col += advance
            continue
        matched = False
        for symbol in _SYMBOLS:
            if source.startswith(symbol, i):
                tokens.append(Token("sym", symbol, start_line, start_col))
                advance = len(symbol)
                i += advance
                col += advance
                matched = True
                break
        if matched:
            continue
        if ch.isdigit() or (ch == "." and i + 1 < length and source[i + 1].isdigit()):
            j = i
            while j < length and (source[j].isdigit() or source[j] == "."):
                j += 1
            if j < length and source[j] in "eE":
                k = j + 1
                if k < length and source[k] in "+-":
                    k += 1
                if k < length and source[k].isdigit():
                    j = k
                    while j < length and source[j].isdigit():
                        j += 1
            text = source[i:j]
            tokens.append(Token("num", text, start_line, start_col))
            col += j - i
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < length and (source[j].isalnum() or source[j] == "_"):
                j += 1
            tokens.append(Token("id", source[i:j], start_line, start_col))
            col += j - i
            i = j
            continue
        raise LexError("unexpected character %r" % ch, line, col)
    return tokens


class TokenStream:
    """One-token-lookahead cursor over a token list."""

    def __init__(self, tokens: Iterator[Token] | list[Token]):
        self._tokens = list(tokens)
        self.pos = 0

    def peek(self) -> Token | None:
        return self._tokens[self.pos] if self.pos < len(self._tokens) else None

    def next(self) -> Token:
        token = self.peek()
        if token is None:
            raise LexError("unexpected end of input", 0, 0)
        self.pos += 1
        return token

    def accept_sym(self, *symbols: str) -> Token | None:
        token = self.peek()
        if token is not None and token.is_sym(*symbols):
            self.pos += 1
            return token
        return None

    def expect_sym(self, symbol: str) -> Token:
        token = self.peek()
        if token is None or not token.is_sym(symbol):
            found = "end of input" if token is None else repr(token.value)
            where = token or (self._tokens[-1] if self._tokens else None)
            line, col = (where.line, where.col) if where else (0, 0)
            raise LexError("expected %r, found %s" % (symbol, found), line, col)
        self.pos += 1
        return token

    def expect_id(self, *names: str) -> Token:
        token = self.peek()
        if token is None or not token.is_id():
            raise LexError("expected identifier", *( (token.line, token.col) if token else (0, 0)))
        if names and token.value.lower() not in names:
            raise LexError("expected one of %s, got %r" % (", ".join(names), token.value),
                           token.line, token.col)
        self.pos += 1
        return token

    def at_end(self) -> bool:
        return self.pos >= len(self._tokens)
