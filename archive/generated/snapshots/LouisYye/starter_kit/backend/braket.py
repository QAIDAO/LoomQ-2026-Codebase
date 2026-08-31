from datetime import datetime, timezone
from typing import Any, Dict

from braket.devices import LocalSimulator
from braket.ir.openqasm import Program


def normalize_counts(
    raw_counts: Dict[str, int],
    measured_qubits: list[int],
    measurement_map: Dict[int, int],
    num_bits: int,
) -> Dict[str, int]:
    normalized = {}

    for raw_key, count in raw_counts.items():
        classical_bits = ["0"] * num_bits

        for value, qubit in zip(
            raw_key,
            measured_qubits,
        ):
            classical_bit = measurement_map[qubit]
            classical_bits[classical_bit] = value

        # Competition format: c[n-1]...c[1]c[0]
        normalized_key = "".join(
            reversed(classical_bits)
        )

        normalized[normalized_key] = (
            normalized.get(normalized_key, 0)
            + count
        )

    return normalized


def run_braket(
    qasm3: str,
    shots: int,
    measurement_map: Dict[int, int],
    num_bits: int,
) -> Dict[str, Any]:
    if shots <= 0:
        raise ValueError("shots must be positive")

    device = LocalSimulator()
    program = Program(source=qasm3)

    task = device.run(
        program,
        shots=shots,
    )

    result = task.result()

    counts = normalize_counts(
        raw_counts=dict(result.measurement_counts),
        measured_qubits=list(result.measured_qubits),
        measurement_map=measurement_map,
        num_bits=num_bits,
    )

    return {
        "backend": "braket_local_simulator",
        "job_id": result.task_metadata.id,
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "meta": {
            "is_mock": False,
        },
    }