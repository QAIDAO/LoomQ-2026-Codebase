"""Typed, immutable intermediate representation shared by every backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True, slots=True)
class Gate:
    name: str
    qubits: tuple[int, ...]
    params: tuple[float, ...] = ()
    source: str = ""


@dataclass(frozen=True, slots=True)
class Measurement:
    qubit: int
    cbit: int
    source: str = ""


Operation = Union[Gate, Measurement]


@dataclass(frozen=True, slots=True)
class Circuit:
    qubit_count: int
    cbit_count: int
    operations: tuple[Operation, ...]

    @property
    def gates(self) -> tuple[Gate, ...]:
        return tuple(op for op in self.operations if isinstance(op, Gate))

    @property
    def measurements(self) -> tuple[Measurement, ...]:
        return tuple(op for op in self.operations if isinstance(op, Measurement))
