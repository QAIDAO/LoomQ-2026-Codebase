from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from braket.devices import LocalSimulator
from braket.ir.openqasm import Program

from ..ir import (
    Circuit,
    Measurement,
)

from ..emitters import emit_braket

def normalize_braket_counts(
    result,
    circuit: Circuit
) -> Dict[str, int]:

    measurement_ops = [
        operation
        for operation in circuit.operations
        if isinstance(operation, Measurement)
    ]

    if not measurement_ops:
        raise ValueError(
            "Circuit contains no measurements"
        )

    measured_qubits = [
        int(qubit_idx)
        for qubit_idx in result.measured_qubits
    ]

    qubit_positions = {
        qubit_idx: position
        for position, qubit_idx
        in enumerate(measured_qubits)
    }

    counts = {}

    for row in result.measurements:

        # 内部：
        # [c0, c1, c2, ...]
        classical_bits = [
            "0"
            for _ in range(circuit.num_clbits)
        ]

        for measurement in measurement_ops:

            qubit_idx = measurement.qubit_idx
            cbit_idx = measurement.cbit_idx

            if qubit_idx not in qubit_positions:
                raise ValueError(
                    f"Braket did not return "
                    f"measurement for q[{qubit_idx}]"
                )

            position = qubit_positions[
                qubit_idx
            ]

            classical_bits[cbit_idx] = str(
                int(row[position])
            )

        # LoomQ:
        # c[n-1] ... c[1] c[0]
        key = "".join(
            reversed(classical_bits)
        )

        counts[key] = (
            counts.get(key, 0) + 1
        )

    return counts


def run_braket(
    circuit: Circuit,
    shots: int
) -> Dict[str, Any]:

    if (
        not isinstance(shots, int)
        or isinstance(shots, bool)
        or shots <= 0
    ):
        raise ValueError(
            "shots must be a positive integer"
        )

    qasm3 = emit_braket(
        circuit,
        include_stdgates=False
    )
    program = Program(
        source=qasm3
    )

    simulator = LocalSimulator()

    task = simulator.run(
        program,
        shots=shots
    )

    result = task.result()

    counts = normalize_braket_counts(
        result,
        circuit
    )

    timestamp = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    return {
        "backend": "braket_local_simulator",
        "job_id": f"local-{uuid4()}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": timestamp,
    }

