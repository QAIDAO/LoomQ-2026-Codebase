"""Real target SDK runners and unified result helpers."""

from __future__ import annotations

from collections.abc import Callable

from ..compiler.ir import Circuit
from . import braket as braket_runner
from .braket import run_braket
from . import originq as originq_runner
from .originq import run_originq
from .result import BACKEND_IDS, build_result, normalize_counts, remap_measured_qubits
from . import spinq as spinq_runner
from .spinq import run_spinq


_RUNNERS: dict[str, Callable[[Circuit, int], dict[str, object]]] = {
    "spinq": run_spinq,
    "originq": run_originq,
    "braket": run_braket,
}


def backend_availability() -> dict[str, dict[str, object]]:
    """Return safe import availability for the canonical local backends.

    This is a read-only Web preflight. It deliberately exposes no exception
    text, filesystem paths, credentials, or runner internals, and it does not
    change how ``run_circuit`` dispatches or executes a backend.
    """

    modules = {
        "spinq": (spinq_runner, "spinqit==0.2.4"),
        "originq": (originq_runner, "pyqpanda"),
        "braket": (braket_runner, "amazon-braket-sdk"),
    }
    availability: dict[str, dict[str, object]] = {}
    for backend_id, (module, dependency) in modules.items():
        available = getattr(module, "_IMPORT_ERROR", None) is None
        availability[backend_id] = {
            "available": available,
            "dependency": dependency,
            "status": "available" if available else "missing dependency",
        }
    return availability


def run_circuit(circuit: Circuit, target: str, shots: int) -> dict[str, object]:
    try:
        runner = _RUNNERS[target]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unsupported target: {target}") from exc
    if isinstance(shots, bool) or not isinstance(shots, int) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    return runner(circuit, shots)


__all__ = [
    "BACKEND_IDS",
    "backend_availability",
    "build_result",
    "normalize_counts",
    "remap_measured_qubits",
    "run_braket",
    "run_circuit",
    "run_originq",
    "run_spinq",
]
