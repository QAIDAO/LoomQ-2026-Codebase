"""Small shared helpers for deterministic target emitters."""

import math
from typing import Any, Iterable, Tuple


def format_angle(value: float) -> str:
    """Serialize a finite angle without losing binary64 precision."""
    if not math.isfinite(value):
        raise ValueError("gate angle must be finite")
    rendered = format(value, ".17g")
    return "0" if rendered == "-0" else rendered


def gate_fields(operation: Any) -> Tuple[str, Tuple[float, ...], Tuple[int, ...]]:
    """Read the stable normalized GateOp protocol without backend coupling."""
    name = getattr(operation, "name", None)
    qubits = getattr(operation, "qubits", None)
    params = getattr(operation, "params", ())
    if not isinstance(name, str) or qubits is None:
        raise TypeError("operation is not a normalized gate")
    return name, tuple(float(item) for item in params), tuple(int(item) for item in qubits)


def is_measurement(operation: Any) -> bool:
    return hasattr(operation, "qubit") and hasattr(operation, "cbit") and not hasattr(operation, "qubits")


def measurement_fields(operation: Any) -> Tuple[int, int]:
    if not is_measurement(operation):
        raise TypeError("operation is not a normalized measurement")
    return int(operation.qubit), int(operation.cbit)


def format_operands(qubits: Iterable[int]) -> str:
    return ", ".join("q[%d]" % qubit for qubit in qubits)
