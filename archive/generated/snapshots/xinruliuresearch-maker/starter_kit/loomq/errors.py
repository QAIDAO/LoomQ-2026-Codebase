"""Shared public errors for the LoomQ implementation."""


class LoomQError(ValueError):
    """Base class for deterministic, user-correctable LoomQ failures."""


class InputValidationError(LoomQError):
    """Raised when a public adapter argument is outside its contract."""


class UnsupportedTargetError(InputValidationError):
    """Raised when a backend target is not in the official allowlist."""


class SimulationError(LoomQError):
    """Raised when a circuit cannot be executed by the local reference engine."""
