"""Gate decomposition helpers for backends with incomplete native gate sets."""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence

from .circuit import Circuit, GateOp, MeasureOp


def _u1(theta: float, qubit) -> GateOp:
    # Represent u1 via rz for IR that only keeps whitelist names.
    # For emit paths that need true phase, emitters may rewrite rz->u1/p.
    return GateOp(name="rz", qubits=(qubit,), params=(theta,))


def decompose_gate(op: GateOp, mode: str = "basic") -> List[GateOp]:
    """Expand a gate into more primitive whitelist gates when needed.

    mode:
      - 'basic': expand swap/cu1/ccx using identities from gate_identities.md
      - 'none': keep as-is
    """
    if mode == "none":
        return [op]

    name = op.name
    qs = op.qubits
    if name == "swap":
        a, b = qs
        return [
            GateOp("cx", (a, b)),
            GateOp("cx", (b, a)),
            GateOp("cx", (a, b)),
        ]
    if name == "cu1":
        theta = op.params[0]
        a, b = qs
        # Official identity uses u1; we encode as rz (global-phase-safe for
        # standalone use). Emitters targeting OriginIR/Braket map rz carefully.
        return [
            GateOp("rz", (a,), (theta / 2.0,)),
            GateOp("cx", (a, b)),
            GateOp("rz", (b,), (-theta / 2.0,)),
            GateOp("cx", (a, b)),
            GateOp("rz", (b,), (theta / 2.0,)),
        ]
    if name == "ccx":
        a, b, c = qs
        return [
            GateOp("h", (c,)),
            GateOp("cx", (b, c)),
            GateOp("tdg", (c,)),
            GateOp("cx", (a, c)),
            GateOp("t", (c,)),
            GateOp("cx", (b, c)),
            GateOp("tdg", (c,)),
            GateOp("cx", (a, c)),
            GateOp("t", (b,)),
            GateOp("t", (c,)),
            GateOp("h", (c,)),
            GateOp("cx", (a, b)),
            GateOp("t", (a,)),
            GateOp("tdg", (b,)),
            GateOp("cx", (a, b)),
        ]
    if name in {"s", "sdg", "t", "tdg"} and mode == "phase_as_rz":
        mapping = {
            "s": math.pi / 2,
            "sdg": -math.pi / 2,
            "t": math.pi / 4,
            "tdg": -math.pi / 4,
        }
        return [GateOp("rz", qs, (mapping[name],))]
    return [op]


def expand_circuit(circuit: Circuit, mode: str = "basic") -> Circuit:
    out = Circuit(qregs=dict(circuit.qregs), cregs=dict(circuit.cregs), ops=[])
    for op in circuit.ops:
        if isinstance(op, MeasureOp):
            out.ops.append(op)
        else:
            out.ops.extend(decompose_gate(op, mode=mode))
    return out


def format_angle(theta: float) -> str:
    """Pretty-print common multiples of pi; otherwise use float repr."""
    if abs(theta) < 1e-15:
        return "0"
    ratio = theta / math.pi
    for denom in range(1, 17):
        numer = round(ratio * denom)
        if abs(ratio * denom - numer) < 1e-10:
            if numer == 0:
                return "0"
            if denom == 1:
                return "pi" if numer == 1 else ("-pi" if numer == -1 else f"{numer}*pi")
            if abs(numer) == 1:
                return f"pi/{denom}" if numer > 0 else f"-pi/{denom}"
            return f"{numer}*pi/{denom}"
    return repr(float(theta))
