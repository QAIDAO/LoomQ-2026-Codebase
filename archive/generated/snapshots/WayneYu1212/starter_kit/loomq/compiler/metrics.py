"""Small deterministic circuit metrics used in result metadata."""

from __future__ import annotations

from .ir import Circuit


def circuit_metrics(circuit: Circuit) -> dict[str, int]:
    """Count logical gates and ASAP depth without backend-specific rewrites."""

    qubit_depths = [0] * circuit.qubit_count
    depth = 0
    for gate in circuit.gates:
        layer = 1 + max(qubit_depths[qubit] for qubit in gate.qubits)
        for qubit in gate.qubits:
            qubit_depths[qubit] = layer
        depth = max(depth, layer)
    return {"transpiled_gates": len(circuit.gates), "depth": depth}
