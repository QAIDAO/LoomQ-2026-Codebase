"""Semantic verification utilities for independently read target IR."""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from .model import Circuit
from .target_ir import parse_target_ir


@dataclass(frozen=True)
class SemanticOperation:
    name: str
    qubits: Tuple[int, ...]
    parameter: Optional[float]


@dataclass(frozen=True)
class SemanticCircuit:
    qubit_count: int
    classical_bit_count: int
    operations: Tuple[SemanticOperation, ...]
    measurements: Tuple[Tuple[int, int], ...]


def semantic_view(circuit: Circuit) -> SemanticCircuit:
    """Normalize register names and partitions into global bit indices."""
    return SemanticCircuit(
        qubit_count=circuit.qubit_count,
        classical_bit_count=circuit.classical_bit_count,
        operations=tuple(
            SemanticOperation(
                operation.name,
                tuple(circuit.quantum_index(bit) for bit in operation.qubits),
                operation.parameter,
            )
            for operation in circuit.operations
        ),
        measurements=tuple(
            (
                circuit.quantum_index(measurement.qubit),
                circuit.classical_index(measurement.classical),
            )
            for measurement in circuit.measurements
        ),
    )


def circuit_difference(
    expected: Circuit, actual: Circuit, *, angle_tolerance: float = 1e-12
) -> Optional[str]:
    """Return the first semantic mismatch, or None when circuits are equivalent."""
    left = semantic_view(expected)
    right = semantic_view(actual)
    if left.qubit_count != right.qubit_count:
        return f"qubit count differs: {left.qubit_count} != {right.qubit_count}"
    if left.classical_bit_count != right.classical_bit_count:
        return (
            "classical bit count differs: "
            f"{left.classical_bit_count} != {right.classical_bit_count}"
        )
    if len(left.operations) != len(right.operations):
        return f"operation count differs: {len(left.operations)} != {len(right.operations)}"
    for index, (expected_op, actual_op) in enumerate(
        zip(left.operations, right.operations)
    ):
        if expected_op.name != actual_op.name:
            return (
                f"operation {index} name differs: "
                f"{expected_op.name} != {actual_op.name}"
            )
        if expected_op.qubits != actual_op.qubits:
            return (
                f"operation {index} qubits differ: "
                f"{expected_op.qubits} != {actual_op.qubits}"
            )
        if not _parameters_equal(
            expected_op.parameter, actual_op.parameter, angle_tolerance
        ):
            return (
                f"operation {index} parameter differs: "
                f"{expected_op.parameter} != {actual_op.parameter}"
            )
    if left.measurements != right.measurements:
        return f"measurements differ: {left.measurements} != {right.measurements}"
    return None


def verify_target_roundtrip(
    expected: Circuit,
    target: str,
    target_source: str,
    *,
    angle_tolerance: float = 1e-12,
) -> Circuit:
    """Read emitted target IR and reject any semantic change."""
    actual = parse_target_ir(target_source, target)
    difference = circuit_difference(
        expected, actual, angle_tolerance=angle_tolerance
    )
    if difference is not None:
        raise ValueError(f"{target} round-trip mismatch: {difference}")
    return actual


def _parameters_equal(
    expected: Optional[float], actual: Optional[float], tolerance: float
) -> bool:
    if expected is None or actual is None:
        return expected is actual
    return math.isclose(expected, actual, rel_tol=0.0, abs_tol=tolerance)
