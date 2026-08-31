"""Allowlisted dispatch for target IR emitters."""

from typing import Any, Callable, Dict

from ..errors import UnsupportedTargetError
from . import braket, originq, spinq


SUPPORTED_TARGETS = ("spinq", "originq", "braket")
EMITTERS: Dict[str, Callable[[Any], str]] = {
    "spinq": spinq.emit,
    "originq": originq.emit,
    "braket": braket.emit,
}


def validate_target(target: str) -> str:
    if not isinstance(target, str):
        raise UnsupportedTargetError("target must be a string")
    normalized = target.strip().lower()
    if normalized not in EMITTERS:
        raise UnsupportedTargetError(
            "unsupported target %r; expected one of %s"
            % (target, ", ".join(SUPPORTED_TARGETS))
        )
    return normalized


def emit_target_ir(circuit: Any, target: str) -> str:
    normalized = validate_target(target)
    artifact = EMITTERS[normalized](circuit)
    if not artifact.strip():
        raise RuntimeError("target emitter returned an empty artifact")
    return artifact
