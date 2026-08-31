"""Stable response schema for LoomQ Agent consumers."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

try:
    from ..loomq_core.model import Circuit
    from ..loomq_core.simulator import circuit_depth
except ImportError:
    from loomq_core.model import Circuit
    from loomq_core.simulator import circuit_depth


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class OperationArtifact:
    name: str
    qubits: Tuple[int, ...]
    parameter: Optional[float]


@dataclass(frozen=True)
class MeasurementArtifact:
    qubit: int
    classical_bit: int


@dataclass(frozen=True)
class CircuitArtifact:
    qubit_count: int
    classical_bit_count: int
    depth: int
    operations: Tuple[OperationArtifact, ...]
    measurements: Tuple[MeasurementArtifact, ...]

    @classmethod
    def from_circuit(cls, circuit: Circuit) -> "CircuitArtifact":
        operations = tuple(
            OperationArtifact(
                operation.name,
                tuple(circuit.quantum_index(qubit) for qubit in operation.qubits),
                operation.parameter,
            )
            for operation in circuit.operations
        )
        measurements = tuple(
            MeasurementArtifact(
                circuit.quantum_index(measurement.qubit),
                circuit.classical_index(measurement.classical),
            )
            for measurement in circuit.measurements
        )
        return cls(
            circuit.qubit_count,
            circuit.classical_bit_count,
            circuit_depth(circuit),
            operations,
            measurements,
        )


@dataclass(frozen=True)
class SimulationArtifact:
    method: str
    shots: int
    counts: Dict[str, int]
    fidelity: Optional[float]


@dataclass(frozen=True)
class BackendSelectionArtifact:
    constraints: Tuple[str, ...]
    candidates: Tuple[Dict[str, Any], ...]
    alternatives: Tuple[Dict[str, Any], ...]


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class AgentArtifacts:
    qasm: Optional[str] = None
    circuit: Optional[CircuitArtifact] = None
    simulation: Optional[SimulationArtifact] = None
    backend_selection: Optional[BackendSelectionArtifact] = None


@dataclass(frozen=True)
class AgentResponse:
    task: str
    answer: str
    artifacts: AgentArtifacts
    diagnostics: Tuple[Diagnostic, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
