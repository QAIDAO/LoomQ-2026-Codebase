from dataclasses import dataclass
from typing import List, Optional, Tuple, Union
@dataclass
class Gate:
    name: str
    qubit_indices: tuple
    parameter: str | None=None

@dataclass
class Measurement:
    qubit_idx: int
    cbit_idx: int

Operation = Union[
    Gate,
    Measurement,
]


@dataclass
class Circuit:
    num_qubits: int
    num_clbits: int
    operations: List[Operation]

