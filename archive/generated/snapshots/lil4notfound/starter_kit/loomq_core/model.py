"""Canonical circuit model used by all LoomQ adapters."""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Register:
    name: str
    size: int
    offset: int


@dataclass(frozen=True)
class BitRef:
    register: str
    index: int


@dataclass(frozen=True)
class Operation:
    name: str
    qubits: Tuple[BitRef, ...]
    parameter: Optional[float] = None


@dataclass(frozen=True)
class Measurement:
    qubit: BitRef
    classical: BitRef


@dataclass(frozen=True)
class Circuit:
    quantum_registers: Tuple[Register, ...]
    classical_registers: Tuple[Register, ...]
    operations: Tuple[Operation, ...]
    measurements: Tuple[Measurement, ...]

    @property
    def qubit_count(self) -> int:
        return sum(register.size for register in self.quantum_registers)

    @property
    def classical_bit_count(self) -> int:
        return sum(register.size for register in self.classical_registers)

    def quantum_index(self, bit: BitRef) -> int:
        return _global_index(self.quantum_registers, bit)

    def classical_index(self, bit: BitRef) -> int:
        return _global_index(self.classical_registers, bit)


def _global_index(registers: Tuple[Register, ...], bit: BitRef) -> int:
    for register in registers:
        if register.name == bit.register:
            if not 0 <= bit.index < register.size:
                raise ValueError(f"Index outside register {bit.register}: {bit.index}")
            return register.offset + bit.index
    raise ValueError(f"Unknown register: {bit.register}")
