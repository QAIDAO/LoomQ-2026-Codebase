"""Lexer for the classical block embedded in Hybrid-QASM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .errors import HybridSyntaxError


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


_SINGLE_CHARACTER_TOKENS = frozenset("{}()[];=+-")


def tokenize(source: str) -> List[Token]:
    """Tokenize one classical block, preserving useful error locations."""
    tokens: List[Token] = []
    index = 0
    line = 1
    column = 1

    while index < len(source):
        char = source[index]
        if char in " \t\r":
            index += 1
            column += 1
            continue
        if char == "\n":
            index += 1
            line += 1
            column = 1
            continue
        if source.startswith("//", index):
            while index < len(source) and source[index] != "\n":
                index += 1
                column += 1
            continue

        start_line, start_column = line, column
        if source.startswith("==", index) or source.startswith("!=", index):
            value = source[index : index + 2]
            tokens.append(Token("operator", value, start_line, start_column))
            index += 2
            column += 2
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < len(source) and (
                source[end].isalnum() or source[end] == "_"
            ):
                end += 1
            value = source[index:end]
            tokens.append(Token("identifier", value, start_line, start_column))
            column += end - index
            index = end
            continue
        if char.isdigit():
            end = index + 1
            while end < len(source) and source[end].isdigit():
                end += 1
            value = source[index:end]
            tokens.append(Token("integer", value, start_line, start_column))
            column += end - index
            index = end
            continue
        if char in _SINGLE_CHARACTER_TOKENS:
            kind = "operator" if char in "=+-" else "punctuation"
            tokens.append(Token(kind, char, start_line, start_column))
            index += 1
            column += 1
            continue

        raise HybridSyntaxError(
            "unexpected character %r at line %d, column %d"
            % (char, start_line, start_column)
        )

    tokens.append(Token("eof", "", line, column))
    return tokens

