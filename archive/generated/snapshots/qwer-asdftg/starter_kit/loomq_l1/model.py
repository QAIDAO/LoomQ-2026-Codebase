from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple


@dataclass(frozen=True)
class Register:
    name: str
    size: int
    offset: int

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError("register size must be positive")
        if self.offset < 0:
            raise ValueError("register offset must be non-negative")


@dataclass(frozen=True)
class Operation:
    name: str
    qubits: Tuple[int, ...]
    parameter: Optional[float] = None


@dataclass(frozen=True)
class Measurement:
    qubit: int
    cbit: int


@dataclass(frozen=True)
class Circuit:
    qregs: Tuple[Register, ...]
    cregs: Tuple[Register, ...]
    operations: Tuple[Operation, ...]
    measurements: Tuple[Measurement, ...]

    @property
    def num_qubits(self) -> int:
        return sum(register.size for register in self.qregs)

    @property
    def num_clbits(self) -> int:
        return sum(register.size for register in self.cregs)

    @property
    def gate_count(self) -> int:
        return len(self.operations)


@dataclass(frozen=True)
class RawExecution:
    backend: str
    job_id: str
    counts: Mapping[Any, int]
    key_format: str = "binary"
    reverse_bits: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
