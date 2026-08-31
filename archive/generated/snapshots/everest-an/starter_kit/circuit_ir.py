"""LoomQ L1 intermediate representation.

A minimal, backend-agnostic circuit IR: parsed OpenQASM 2.0 lives here,
and each target code generator consumes it. Keeping the IR dumb and flat
makes the transpiler a pure function of (circuit, target).
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass(frozen=True)
class GateOp:
    """A single quantum gate application.

    ``name`` is the canonical lowercase qelib1 name (h, x, s, sdg, t, tdg,
    rz, ry, cx, cu1, swap, ccx, u1). ``params`` holds floating-point
    arguments (empty for non-parameterized gates). ``qubits`` holds global
    qubit indices (resolved across all qregs at parse time).
    """

    name: str
    params: List[float]
    qubits: List[int]


@dataclass
class Circuit:
    """Flat circuit model consumed by the simulator and the code generators."""

    num_qubits: int
    num_cbits: int
    ops: List[GateOp] = field(default_factory=list)
    measures: List[Tuple[int, int]] = field(default_factory=list)  # (qubit, cbit)
