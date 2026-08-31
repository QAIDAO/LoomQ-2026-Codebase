"""Safe, user-facing failures for hardware execution.

Messages in these exception classes must never include credential values or
raw vendor exceptions.  The CLI prints only these messages.
"""


class HardwareError(RuntimeError):
    """Base class for an expected, safely reportable hardware failure."""


class ConfigurationError(HardwareError):
    """Credentials or command inputs are absent or invalid."""


class HardwareQualificationError(HardwareError):
    """The selected backend cannot be proven to be an available real QPU."""


class VendorExecutionError(HardwareError):
    """A vendor call failed without exposing the underlying secret-bearing error."""


class ResultValidationError(HardwareError):
    """A vendor response cannot be admitted as a complete hardware result."""


class EvidenceError(HardwareError):
    """An evidence bundle is invalid or cannot be committed atomically."""
