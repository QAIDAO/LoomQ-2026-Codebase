# Intermediate Representation (IR) for quantum circuits
from dataclasses import dataclass, field

# Represents one quantum gate instruction, with name (e.g., "h", "cx"), qubit indices(a list of integers with maximum length 3), and optional parameters (e.g., rotation angles)
@dataclass
class Gate:
    name: str
    qubits: list[int]
    params: list = field(default_factory=list)

# Represents one measurement operation, with the qubit index and the classical bit index storing the measurement result
@dataclass
class Measurement:
    qubit: int
    bit: int

# Quantum circuit built from a list of gates and measurements, with the total number of qubits and classical bits
@dataclass
class Circuit:
    num_qubits: int
    num_bits: int
    gates: list[Gate] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)