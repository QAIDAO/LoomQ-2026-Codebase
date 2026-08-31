"""Safe evaluation of LoomQ parameter expressions."""

import math
from typing import List, Tuple

from .errors import ExpressionError


_Token = Tuple[str, object]

# Resource limits keep hostile input from consuming unbounded parser or float
# conversion work while leaving normal QASM parameter expressions unaffected.
_MAX_EXPRESSION_SOURCE_LENGTH = 65536
_MAX_NUMERIC_LITERAL_LENGTH = 1024
_MAX_EXPRESSION_NESTING = 64
_ASCII_WHITESPACE = " \t\r\n"


def _is_ascii_digit(character: str) -> bool:
    return "0" <= character <= "9"


def _tokenize(source: str) -> List[_Token]:
    if type(source) is not str:
        raise ExpressionError("expression must be a string")
    if len(source) > _MAX_EXPRESSION_SOURCE_LENGTH:
        raise ExpressionError("expression source is too long")

    tokens: List[_Token] = []
    index = 0
    while index < len(source):
        character = source[index]
        if character in _ASCII_WHITESPACE:
            index += 1
            continue

        if _is_ascii_digit(character) or (
            character == "."
            and index + 1 < len(source)
            and _is_ascii_digit(source[index + 1])
        ):
            start = index
            if character == ".":
                index += 1
            while index < len(source) and _is_ascii_digit(source[index]):
                index += 1
                if index - start > _MAX_NUMERIC_LITERAL_LENGTH:
                    raise ExpressionError("numeric literal is too long")
            if index < len(source) and source[index] == ".":
                index += 1
                if index - start > _MAX_NUMERIC_LITERAL_LENGTH:
                    raise ExpressionError("numeric literal is too long")
                while index < len(source) and _is_ascii_digit(source[index]):
                    index += 1
                    if index - start > _MAX_NUMERIC_LITERAL_LENGTH:
                        raise ExpressionError("numeric literal is too long")
            text = source[start:index]
            try:
                value = float(text)
            except ValueError as error:
                raise ExpressionError("malformed number") from error
            if not math.isfinite(value):
                raise ExpressionError("number is not finite")
            tokens.append(("NUMBER", value))
            continue

        if source.startswith("pi", index):
            end = index + 2
            if end < len(source) and (source[end].isalnum() or source[end] == "_"):
                raise ExpressionError("unknown identifier")
            tokens.append(("PI", math.pi))
            index = end
            continue

        token_types = {
            "+": "PLUS",
            "-": "MINUS",
            "*": "STAR",
            "/": "SLASH",
            "(": "LPAREN",
            ")": "RPAREN",
        }
        token_type = token_types.get(character)
        if token_type is None:
            raise ExpressionError("invalid character in expression")
        tokens.append((token_type, character))
        index += 1

    if not tokens:
        raise ExpressionError("expression is empty")
    tokens.append(("EOF", None))
    return tokens


def _validate_nesting(tokens: List[_Token]) -> None:
    """Reject excessive nesting before recursive parser calls can occur."""
    parenthesis_depth = 0
    unary_depth = 0
    expects_operand = True

    for token, _ in tokens:
        if token == "EOF":
            break
        if token == "LPAREN":
            parenthesis_depth += 1
            if parenthesis_depth > _MAX_EXPRESSION_NESTING:
                raise ExpressionError("parenthesis nesting is too deep")
            unary_depth = 0
            expects_operand = True
        elif token in ("PLUS", "MINUS"):
            if expects_operand:
                unary_depth += 1
                if unary_depth > _MAX_EXPRESSION_NESTING:
                    raise ExpressionError("unary nesting is too deep")
            else:
                unary_depth = 1
            expects_operand = True
        elif token in ("STAR", "SLASH"):
            unary_depth = 0
            expects_operand = True
        elif token in ("NUMBER", "PI"):
            unary_depth = 0
            expects_operand = False
        elif token == "RPAREN":
            parenthesis_depth = max(0, parenthesis_depth - 1)
            unary_depth = 0
            expects_operand = False


class _Parser:
    def __init__(self, tokens: List[_Token]) -> None:
        self._tokens = tokens
        self._position = 0
        self._parenthesis_depth = 0

    def parse(self) -> float:
        value = self._expression()
        if self._current()[0] != "EOF":
            raise ExpressionError("trailing tokens")
        return value

    def _current(self) -> _Token:
        return self._tokens[self._position]

    def _take(self, token_type: str) -> object:
        token, value = self._current()
        if token != token_type:
            raise ExpressionError("unexpected token")
        self._position += 1
        return value

    def _expression(self) -> float:
        value = self._term()
        while self._current()[0] in ("PLUS", "MINUS"):
            operator = self._current()[0]
            self._position += 1
            right = self._term()
            value = value + right if operator == "PLUS" else value - right
            self._ensure_finite(value)
        return value

    def _term(self) -> float:
        value = self._unary()
        while self._current()[0] in ("STAR", "SLASH"):
            operator = self._current()[0]
            self._position += 1
            right = self._unary()
            if operator == "SLASH":
                if right == 0:
                    raise ExpressionError("division by zero")
                value /= right
            else:
                value *= right
            self._ensure_finite(value)
        return value

    def _unary(self, depth: int = 0) -> float:
        token = self._current()[0]
        if token == "PLUS":
            if depth >= _MAX_EXPRESSION_NESTING:
                raise ExpressionError("unary nesting is too deep")
            self._position += 1
            return self._unary(depth + 1)
        if token == "MINUS":
            if depth >= _MAX_EXPRESSION_NESTING:
                raise ExpressionError("unary nesting is too deep")
            self._position += 1
            value = -self._unary(depth + 1)
            self._ensure_finite(value)
            return value
        return self._primary()

    def _primary(self) -> float:
        token = self._current()[0]
        if token in ("NUMBER", "PI"):
            value = self._current()[1]
            self._position += 1
            return float(value)
        if token == "LPAREN":
            if self._parenthesis_depth >= _MAX_EXPRESSION_NESTING:
                raise ExpressionError("parenthesis nesting is too deep")
            self._position += 1
            self._parenthesis_depth += 1
            try:
                value = self._expression()
                self._take("RPAREN")
            finally:
                self._parenthesis_depth -= 1
            return value
        raise ExpressionError("expected a number, pi, or parenthesized expression")

    @staticmethod
    def _ensure_finite(value: float) -> None:
        if not math.isfinite(value):
            raise ExpressionError("expression result is not finite")


def evaluate_expression(source: str) -> float:
    """Evaluate the supported arithmetic expression grammar safely."""
    tokens = _tokenize(source)
    _validate_nesting(tokens)
    return _Parser(tokens).parse()


__all__ = ["evaluate_expression"]
