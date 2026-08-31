"""Central gate policy shared by the L1, L2, and L3 implementations.

The competition promises that scored circuits use exactly this twelve-gate
OpenQASM 2.0 subset.  Keeping the policy in one module prevents a generated
L2 circuit, an L3 quantum operation, or a backend path from silently growing a
different gate vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .qasm import Program


PUBLIC_GATE_ARITY = {
    "h": 1,
    "x": 1,
    "s": 1,
    "sdg": 1,
    "t": 1,
    "tdg": 1,
    "rz": 1,
    "ry": 1,
    "cx": 2,
    "cu1": 2,
    "swap": 2,
    "ccx": 3,
}
PUBLIC_GATE_WHITELIST = frozenset(PUBLIC_GATE_ARITY)
PARAMETERIZED_GATES = frozenset({"rz", "ry", "cu1"})


@dataclass(frozen=True)
class BasisLoweringReport:
    """Audit data produced by the public-basis lowering boundary."""

    input_gate_count: int
    output_gate_count: int
    rewritten_gate_count: int
    output_gates: tuple[str, ...]


def lower_to_public_basis(program: "Program") -> tuple["Program", BasisLoweringReport]:
    """Return a program proven to use only the competition gate basis.

    The public parser rejects out-of-contract gates before this boundary, so
    the current lowering is intentionally idempotent.  It is still a real,
    explicit pass: every L1/L2/L3 path can share the same invariant and trace
    it.  Backend-specific decompositions, if ever required, belong after this
    pass and must not change the public intermediate representation.
    """

    from .qasm import GateOperation

    gates = tuple(
        operation.name
        for operation in program.operations
        if isinstance(operation, GateOperation)
    )
    assert_gate_names(gates)
    report = BasisLoweringReport(
        input_gate_count=len(gates),
        output_gate_count=len(gates),
        rewritten_gate_count=0,
        output_gates=tuple(sorted(set(gates))),
    )
    return program, report


def assert_gate_names(names: Iterable[str]) -> None:
    """Raise a stable error when a quantum operation leaves the public basis."""

    unknown = sorted({str(name).lower() for name in names} - PUBLIC_GATE_WHITELIST)
    if unknown:
        raise ValueError(
            "quantum operations must use the LoomQ public gate whitelist; "
            "unsupported: " + ", ".join(unknown)
        )
