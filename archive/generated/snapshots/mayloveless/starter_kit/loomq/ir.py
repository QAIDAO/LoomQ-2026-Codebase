"""Platform-independent intermediate representation for quantum circuits."""

from dataclasses import dataclass, field
from typing import Tuple, Union


@dataclass(frozen=True)
class QuantumRegister:
    name: str
    size: int


@dataclass(frozen=True)
class ClassicalRegister:
    name: str
    size: int


@dataclass(frozen=True)
class QubitRef:
    register: str
    index: int


@dataclass(frozen=True)
class ClassicalBitRef:
    register: str
    index: int


@dataclass(frozen=True)
class QuantumRegisterRef:
    register: str


@dataclass(frozen=True)
class ClassicalRegisterRef:
    register: str


@dataclass(frozen=True)
class GateOperation:
    name: str
    qubits: Tuple[QubitRef, ...]
    parameters: Tuple[float, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MeasureOperation:
    quantum: Union[QubitRef, QuantumRegisterRef]
    classical: Union[ClassicalBitRef, ClassicalRegisterRef]


Operation = Union[GateOperation, MeasureOperation]


@dataclass(frozen=True)
class Circuit:
    openqasm_version: str
    quantum_registers: Tuple[QuantumRegister, ...]
    classical_registers: Tuple[ClassicalRegister, ...]
    operations: Tuple[Operation, ...]
