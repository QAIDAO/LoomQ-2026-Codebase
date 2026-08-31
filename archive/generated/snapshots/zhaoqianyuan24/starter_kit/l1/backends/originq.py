from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

import pyqpanda as pq

from ..ir import (
    Circuit,
    Gate,
    Measurement,
)

from ..gates import (
    get_gate_name,
    parse_angle,
)

def build_originq_gate(
    operation: Gate,
    qubits
):

    sdk_gate_name = get_gate_name(
        operation.name,
        "originq",
        sdk=True
    )

    gate_function = getattr(
        pq,
        sdk_gate_name
    )

    target_qubits = [
        qubits[idx]
        for idx in operation.qubit_indices
    ]

    # SDAG / TDAG
    if operation.name in {
        "sdg",
        "tdg",
    }:

        gate = gate_function(
            target_qubits[0]
        )

        return gate.dagger()

    # RY / RZ / CU1
    if operation.parameter is not None:

        angle = parse_angle(
            operation.parameter
        )

        return gate_function(
            *target_qubits,
            angle
        )

    # H / X / S / T /
    # CNOT / SWAP / Toffoli
    return gate_function(
        *target_qubits
    )


def run_originq(
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

    qvm = pq.CPUQVM()

    qvm.init_qvm()

    try:

        qubits = qvm.qAlloc_many(
            circuit.num_qubits
        )

        cbits = qvm.cAlloc_many(
            circuit.num_clbits
        )

        program = pq.QProg()

        for operation in circuit.operations:

            if isinstance(operation, Gate):

                gate = build_originq_gate(
                    operation,
                    qubits
                )

                program << gate

            elif isinstance(
                operation,
                Measurement
            ):

                program << pq.Measure(
                    qubits[
                        operation.qubit_idx
                    ],
                    cbits[
                        operation.cbit_idx
                    ]
                )

            else:

                raise TypeError(
                    f"Unknown operation type: "
                    f"{type(operation)}"
                )

        raw_counts = (
            qvm.run_with_configuration(
                program,
                cbits,
                shots
            )
        )

        counts = {
            str(key): int(value)
            for key, value
            in raw_counts.items()
        }

    finally:

        qvm.finalize()

    timestamp = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    return {
        "backend": "originq_cpuqvm",
        "job_id": f"local-{uuid4()}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": timestamp,
    }

