"""Unified circuit IR shared by all backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple, Union

Param = Union[float, str]
QubitRef = Tuple[str, int]


@dataclass(frozen=True)
class GateOp:
    name: str
    qubits: Tuple[QubitRef, ...]
    params: Tuple[float, ...] = ()


@dataclass(frozen=True)
class MeasureOp:
    qubit: QubitRef
    cbit: Tuple[str, int]


@dataclass
class Circuit:
    qregs: dict = field(default_factory=dict)  # name -> size
    cregs: dict = field(default_factory=dict)  # name -> size
    ops: List[Union[GateOp, MeasureOp]] = field(default_factory=list)

    def n_qubits(self) -> int:
        return sum(self.qregs.values())

    def n_clbits(self) -> int:
        return sum(self.cregs.values())

    def qubit_index(self, ref: QubitRef) -> int:
        name, local = ref
        if name not in self.qregs:
            raise KeyError(f"unknown qreg {name}")
        offset = 0
        for reg_name, size in self.qregs.items():
            if reg_name == name:
                if local < 0 or local >= size:
                    raise IndexError(f"qubit index out of range: {name}[{local}]")
                return offset + local
            offset += size
        raise KeyError(f"unknown qreg {name}")

    def cbit_index(self, ref: Tuple[str, int]) -> int:
        name, local = ref
        if name not in self.cregs:
            raise KeyError(f"unknown creg {name}")
        offset = 0
        for reg_name, size in self.cregs.items():
            if reg_name == name:
                if local < 0 or local >= size:
                    raise IndexError(f"cbit index out of range: {name}[{local}]")
                return offset + local
            offset += size
        raise KeyError(f"unknown creg {name}")

    def gate_ops(self) -> List[GateOp]:
        return [op for op in self.ops if isinstance(op, GateOp)]

    def measure_ops(self) -> List[MeasureOp]:
        return [op for op in self.ops if isinstance(op, MeasureOp)]
