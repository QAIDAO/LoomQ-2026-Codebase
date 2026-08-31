"""Source-aware exceptions raised by the OpenQASM 2 front end."""

from __future__ import annotations

from typing import Optional


class QASMError(ValueError):
    """Base class for all user-facing QASM errors.

    ``line`` and ``column`` are one-based when the error refers to source text.
    A separate ``suggestion`` keeps recovery advice machine-readable while the
    string representation remains useful at a command line.
    """

    def __init__(
        self,
        message: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        self.message = message
        self.line = line
        self.column = column
        self.suggestion = suggestion
        super().__init__(self.__str__())

    def __str__(self) -> str:
        if self.line is None:
            rendered = self.message
        else:
            rendered = f"line {self.line}, column {self.column}: {self.message}"
        if self.suggestion:
            rendered += f" Suggestion: {self.suggestion}"
        return rendered


class QASMLexError(QASMError):
    """The input contains a character sequence that cannot be tokenized."""


class QASMParseError(QASMError):
    """The token stream does not follow the supported OpenQASM 2 grammar."""


class QASMSemanticError(QASMError):
    """A syntactically valid program violates a semantic constraint."""


class QASMSerializationError(QASMError):
    """A normalized circuit cannot be represented as supported QASM 2."""


__all__ = [
    "QASMError",
    "QASMLexError",
    "QASMParseError",
    "QASMSemanticError",
    "QASMSerializationError",
]
