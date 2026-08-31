"""Semantic validation for the bounded LoomQ circuit language."""

from __future__ import annotations

import math
from typing import NoReturn

from .ir import Circuit, Gate, Measurement


GATE_SIGNATURES: dict[str, tuple[int, int]] = {
    "h": (1, 0),
    "x": (1, 0),
    "s": (1, 0),
    "sdg": (1, 0),
    "t": (1, 0),
    "tdg": (1, 0),
    "rz": (1, 1),
    "ry": (1, 1),
    "cx": (2, 0),
    "cu1": (2, 1),
    "swap": (2, 0),
    "ccx": (3, 0),
}
MAX_QUBITS = 30


class CircuitValidationError(ValueError):
    """Raised when parsed QASM violates the official circuit contract."""


def _fail(message: str, source: str = "") -> NoReturn:
    suffix = f" in `{source}`" if source else ""
    raise CircuitValidationError(message + suffix)


def validate_circuit(circuit: Circuit, *, require_measurements: bool = True) -> None:
    """Validate gate signatures, indices, resources, and final measurements."""

    if circuit.qubit_count <= 0 or circuit.qubit_count > MAX_QUBITS:
        _fail(f"qubit count must be between 1 and {MAX_QUBITS}")
    if circuit.cbit_count <= 0:
        _fail("classical bit count must be positive")
    if not circuit.operations:
        _fail("circuit has no operations")

    measurement_started = False
    written_cbits: set[int] = set()
    measurement_count = 0

    for operation in circuit.operations:
        if isinstance(operation, Gate):
            if measurement_started:
                _fail("gates after measurement are not supported", operation.source)
            signature = GATE_SIGNATURES.get(operation.name)
            if signature is None:
                _fail(f"unsupported gate `{operation.name}`", operation.source)
            expected_qubits, expected_params = signature
            if len(operation.qubits) != expected_qubits:
                _fail(
                    f"gate `{operation.name}` requires {expected_qubits} qubit operand(s)",
                    operation.source,
                )
            if len(operation.params) != expected_params:
                _fail(
                    f"gate `{operation.name}` requires {expected_params} parameter(s)",
                    operation.source,
                )
            if len(set(operation.qubits)) != len(operation.qubits):
                _fail("a gate cannot use the same qubit twice", operation.source)
            for qubit in operation.qubits:
                if qubit < 0 or qubit >= circuit.qubit_count:
                    _fail(f"qubit index {qubit} is out of range", operation.source)
            for parameter in operation.params:
                if not math.isfinite(parameter):
                    _fail("gate parameter must be finite", operation.source)
            continue

        if not isinstance(operation, Measurement):
            _fail("unknown IR operation")
        measurement_started = True
        measurement_count += 1
        if operation.qubit < 0 or operation.qubit >= circuit.qubit_count:
            _fail(f"measurement qubit {operation.qubit} is out of range", operation.source)
        if operation.cbit < 0 or operation.cbit >= circuit.cbit_count:
            _fail(f"measurement cbit {operation.cbit} is out of range", operation.source)
        if operation.cbit in written_cbits:
            _fail(f"classical bit c[{operation.cbit}] is measured more than once", operation.source)
        written_cbits.add(operation.cbit)

    if require_measurements and measurement_count == 0:
        _fail("circuit must contain at least one measurement")
