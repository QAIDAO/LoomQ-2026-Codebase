"""Lazy local-simulator runners for LoomQ L1 native IR artifacts."""

from ..errors import UnsupportedTargetError
from ..model import RawExecution
from .braket import run_braket
from .originq import run_originq
from .spinq import run_spinq


_RUNNERS = {
    "spinq": run_spinq,
    "originq": run_originq,
    "braket": run_braket,
}


def run(native_ir: str, target: str, shots: int) -> RawExecution:
    """Run *native_ir* for an exact supported *target*."""
    if type(target) is not str or target not in _RUNNERS:
        raise UnsupportedTargetError(f"unsupported target: {target!r}")
    return _RUNNERS[target](native_ir, shots)


__all__ = ["run", "run_braket", "run_originq", "run_spinq"]
