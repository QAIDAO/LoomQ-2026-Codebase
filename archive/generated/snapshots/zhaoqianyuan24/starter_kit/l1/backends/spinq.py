from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

import spinqit

from spinqit import (
    BasicSimulatorConfig,
    Circuit as SpinQitCircuit,
    get_basic_simulator,
    get_compiler,
)

from ..ir import (
    Circuit,
    Gate,
    Measurement,
)

from ..gates import (
    get_gate_name,
    parse_angle,
)

def normalize_spinq_counts(
    raw_counts: dict,
    circuit: Circuit
) -> dict:

    measurements = [
        operation
        for operation in circuit.operations
        if isinstance(operation, Measurement)
    ]

    if not measurements:
        raise ValueError(
            "Circuit contains no measurements"
        )

    normalized_counts = {}

    for raw_key, count in raw_counts.items():

        raw_key = str(raw_key)

        classical_bits = [
            "0"
            for _ in range(circuit.num_clbits)
        ]

        for measurement in measurements:

            qubit_idx = measurement.qubit_idx
            cbit_idx = measurement.cbit_idx

            classical_bits[cbit_idx] = (
                raw_key[qubit_idx]
            )

        normalized_key = "".join(
            reversed(classical_bits)
        )

        normalized_counts[normalized_key] = (
            normalized_counts.get(
                normalized_key,
                0
            )
            + int(count)
        )

    return normalized_counts
def run_spinq(circuit: Circuit,shots: int) -> Dict[str, Any]:


    if shots <= 0:
        raise ValueError("shots must be positive")

    spinq_circuit = SpinQitCircuit()

    qubits = spinq_circuit.allocateQubits(
        circuit.num_qubits
    )
    for operation in circuit.operations:

      if isinstance(operation, Measurement):
          continue
  
      if not isinstance(operation, Gate):
          raise TypeError(
              f"Unknown operation type: "
              f"{type(operation)}"
          )
  
      sdk_gate_name = get_gate_name(
          operation.name,
          "spinq",
          sdk= True
      )
      
      spinq_gate = getattr(
          spinqit,
          sdk_gate_name
      )     
  
      target_qubits = tuple(
          qubits[idx]
          for idx in operation.qubit_indices
      )
  
      if len(target_qubits) == 1:
          spinq_target = target_qubits[0]
      else:
          spinq_target = target_qubits
  
      if operation.parameter is None:
  
          spinq_circuit << (
              spinq_gate,
              spinq_target
          )
  
      else:
  
          angle = parse_angle(
              operation.parameter
          )
  
          spinq_circuit << (
              spinq_gate,
              spinq_target,
              angle
          )
    compiler = get_compiler("native")

    executable = compiler.compile(
        spinq_circuit,
        0
    )

    simulator = get_basic_simulator()

    config = BasicSimulatorConfig()
    config.configure_shots(shots)

    result = simulator.execute(
        executable,
        config
    )

    raw_counts = result.counts
    counts = normalize_spinq_counts(
        raw_counts,
        circuit
    )

    timestamp = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    return {
        "backend": "spinq_basic_simulator",
        "job_id": f"local-{uuid4()}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": timestamp,
    }

