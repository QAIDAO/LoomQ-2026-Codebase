"""Fail-closed adapters and evidence handling for real quantum hardware.

Vendor SDKs are intentionally optional.  Importing :mod:`loomq.hardware` never
imports a vendor package or performs network I/O.
"""

from .errors import (
    ConfigurationError,
    EvidenceError,
    HardwareError,
    HardwareQualificationError,
    ResultValidationError,
    VendorExecutionError,
)
from .evidence import (
    EvidenceBundle,
    make_hardware_result,
    normalize_counts,
    record_evidence,
    validate_hardware_result,
)

__all__ = [
    "ConfigurationError",
    "EvidenceBundle",
    "EvidenceError",
    "HardwareError",
    "HardwareQualificationError",
    "ResultValidationError",
    "VendorExecutionError",
    "make_hardware_result",
    "normalize_counts",
    "record_evidence",
    "validate_hardware_result",
]
