"""Target-native text emitters sharing the LoomQ circuit IR."""

from __future__ import annotations

from collections.abc import Callable

from ..compiler.ir import Circuit
from .braket import emit_braket
from .originq import emit_originq
from .spinq import emit_spinq


SUPPORTED_TARGETS = ("spinq", "originq", "braket")
_EMITTERS: dict[str, Callable[[Circuit], str]] = {
    "spinq": emit_spinq,
    "originq": emit_originq,
    "braket": emit_braket,
}


def emit(circuit: Circuit, target: str) -> str:
    try:
        emitter = _EMITTERS[target]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unsupported target: {target}") from exc
    return emitter(circuit)


__all__ = [
    "SUPPORTED_TARGETS",
    "emit",
    "emit_braket",
    "emit_originq",
    "emit_spinq",
]
