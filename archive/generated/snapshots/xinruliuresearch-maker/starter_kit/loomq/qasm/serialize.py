"""Canonical OpenQASM 2 serialization for normalized circuits."""

from __future__ import annotations

import math
from typing import List

from ._gates import GATE_SIGNATURES
from .ast import GateOp, MeasureOp, NormalizedCircuit
from .errors import QASMSerializationError


def serialize_qasm2(circuit: NormalizedCircuit) -> str:
    """Serialize a normalized circuit using canonical ``q`` and ``c`` registers.

    Register-level syntax has already been expanded by normalization, so every
    emitted operation is indexed.  The result always ends with a newline.
    """

    if not isinstance(circuit, NormalizedCircuit):
        raise TypeError("circuit must be a qasm.ast.NormalizedCircuit")
    _validate_count("qubit_count", circuit.qubit_count)
    _validate_count("classical_count", circuit.classical_count)

    lines: List[str] = ['OPENQASM 2.0;', 'include "qelib1.inc";']
    if circuit.qubit_count:
        lines.append(f"qreg q[{circuit.qubit_count}];")
    if circuit.classical_count:
        lines.append(f"creg c[{circuit.classical_count}];")

    for operation_index, operation in enumerate(circuit.operations):
        if isinstance(operation, GateOp):
            lines.append(
                _serialize_gate(operation, circuit.qubit_count, operation_index)
            )
        elif isinstance(operation, MeasureOp):
            _validate_index(
                "measurement qubit",
                operation.qubit,
                circuit.qubit_count,
                operation_index,
            )
            _validate_index(
                "measurement classical bit",
                operation.cbit,
                circuit.classical_count,
                operation_index,
            )
            lines.append(f"measure q[{operation.qubit}] -> c[{operation.cbit}];")
        else:
            raise QASMSerializationError(
                f"operation {operation_index} has unsupported type "
                f"{type(operation).__name__}",
                suggestion="Use GateOp or MeasureOp values.",
            )
    return "\n".join(lines) + "\n"


def _serialize_gate(operation: GateOp, qubit_count: int, position: int) -> str:
    signature = GATE_SIGNATURES.get(operation.name)
    if signature is None:
        raise QASMSerializationError(
            f"operation {position} uses unsupported gate {operation.name!r}",
            suggestion="Use a gate supported by the normalized QASM subset.",
        )
    parameter_arity, qubit_arity = signature
    if len(operation.params) != parameter_arity:
        raise QASMSerializationError(
            f"operation {position} gate {operation.name!r} expects "
            f"{parameter_arity} parameter(s), got {len(operation.params)}",
            suggestion="Correct the normalized gate parameter tuple.",
        )
    if len(operation.qubits) != qubit_arity:
        raise QASMSerializationError(
            f"operation {position} gate {operation.name!r} expects "
            f"{qubit_arity} qubit(s), got {len(operation.qubits)}",
            suggestion="Correct the normalized gate qubit tuple.",
        )

    rendered_params: List[str] = []
    for parameter_index, parameter in enumerate(operation.params):
        if isinstance(parameter, bool) or not isinstance(parameter, (int, float)):
            raise QASMSerializationError(
                f"operation {position} parameter {parameter_index} is not numeric",
                suggestion="Use a finite int or float parameter.",
            )
        try:
            value = float(parameter)
        except (ValueError, OverflowError):
            raise QASMSerializationError(
                f"operation {position} parameter {parameter_index} cannot be "
                "represented as a finite float",
                suggestion="Use a finite binary64-sized gate parameter.",
            ) from None
        if not math.isfinite(value):
            raise QASMSerializationError(
                f"operation {position} parameter {parameter_index} is not finite",
                suggestion="Use a finite gate parameter.",
            )
        rendered_params.append(_format_float(value))

    for qubit_position, qubit in enumerate(operation.qubits):
        _validate_index(
            f"gate qubit {qubit_position}", qubit, qubit_count, position
        )
    prefix = operation.name
    if rendered_params:
        prefix += "(" + ",".join(rendered_params) + ")"
    operands = ",".join(f"q[{qubit}]" for qubit in operation.qubits)
    return f"{prefix} {operands};"


def _validate_count(label: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise QASMSerializationError(
            f"{label} must be a non-negative integer, got {value!r}",
            suggestion="Construct the circuit with valid bit counts.",
        )


def _validate_index(label: str, value: int, size: int, position: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise QASMSerializationError(
            f"operation {position} {label} index must be an integer, got {value!r}",
            suggestion="Use a flattened integer bit index.",
        )
    if value < 0 or value >= size:
        raise QASMSerializationError(
            f"operation {position} {label} index {value} is outside [0, {size})",
            suggestion="Keep operation indices within the circuit bit counts.",
        )


def _format_float(value: float) -> str:
    if value == 0.0:
        return "0"
    return format(value, ".17g")


__all__ = ["serialize_qasm2"]
