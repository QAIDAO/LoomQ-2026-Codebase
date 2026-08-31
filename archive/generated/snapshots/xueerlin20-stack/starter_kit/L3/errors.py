"""Errors raised by the deterministic Hybrid-QASM compiler."""


class HybridCompileError(ValueError):
    """Base class for invalid Hybrid-QASM input."""


class HybridSyntaxError(HybridCompileError):
    """A lexical or grammatical error with source location information."""

