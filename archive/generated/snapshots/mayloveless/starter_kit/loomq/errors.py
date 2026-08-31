"""Custom errors raised while parsing OpenQASM source."""

from typing import Optional


class QASMParseError(ValueError):
    """Raised when OpenQASM syntax cannot be parsed."""

    def __init__(
        self, message: str, *, line: Optional[int] = None, statement: str = ""
    ) -> None:
        details = message
        if line is not None:
            details = "line %d: %s" % (line, details)
        if statement:
            details = '%s (statement: "%s")' % (details, statement.strip())
        super().__init__(details)
        self.line = line
        self.statement = statement


class QASMSemanticError(QASMParseError):
    """Raised when valid-looking QASM violates circuit semantics."""


class UnsupportedGateError(QASMParseError):
    """Raised when a gate is outside the currently supported whitelist."""
