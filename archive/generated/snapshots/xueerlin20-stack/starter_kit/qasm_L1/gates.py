"""Gate registry and per-target rendering specs.

The 12-gate whitelist and each target's gate mapping live here so that the
:class:`Translator` stays a pure, declarative engine.  Adding a new target is
just a new :class:`TargetSpec`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

try:
    from .ir import Circuit, Measurement, QubitRef
except ImportError:
    from ir import Circuit, Measurement, QubitRef

WHITELIST = frozenset(
    {"h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx"}
)

ARITY = {
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

PARAM_GATES = frozenset({"rz", "ry", "cu1"})


@dataclass(frozen=True)
class GateRule:
    """One input gate's declarative translation to a target gate."""

    name: str
    fixed_params: Optional[Tuple[float, ...]] = None


@dataclass
class TargetSpec:
    """Declarative description of how to render a Circuit for one target."""

    header: Callable[[Circuit], List[str]]
    gates: Dict[str, GateRule]
    qubit_token: Callable[[QubitRef], str]
    measure: Callable[[Measurement], List[str]]
    params_after_qubits: bool = False
    terminator: str = ";"


def format_param(value: float) -> str:
    """Stable, lossy-but-plenty-precise numeric rendering for parameters."""
    if value == 0 or abs(value) < 1e-14:
        return "0"
    return format(value, ".12g")


def _qasm2_header(circuit: Circuit) -> List[str]:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";']
    lines.extend(f"qreg {name}[{size}];" for name, size in circuit.qregs)
    lines.extend(f"creg {name}[{size}];" for name, size in circuit.cregs)
    return lines


def _qasm3_header(circuit: Circuit) -> List[str]:
    lines = ["OPENQASM 3.0;", 'include "stdgates.inc";']
    lines.extend(f"qubit[{size}] {name};" for name, size in circuit.qregs)
    lines.extend(f"bit[{size}] {name};" for name, size in circuit.cregs)
    return lines


def _originir_header(circuit: Circuit) -> List[str]:
    return [f"QINIT {circuit.qubit_count}", f"CREG {circuit.cbit_count}"]


def _qasm2_measure(measurement: Measurement) -> List[str]:
    if measurement.whole_register:
        return [f"measure {measurement.qubits[0].reg} -> {measurement.cbits[0].reg};"]
    return [
        f"measure {qubit.token} -> {cbit.token};"
        for qubit, cbit in zip(measurement.qubits, measurement.cbits)
    ]


def _qasm3_measure(measurement: Measurement) -> List[str]:
    if measurement.whole_register:
        return [f"{measurement.cbits[0].reg} = measure {measurement.qubits[0].reg};"]
    return [
        f"{cbit.token} = measure {qubit.token};"
        for qubit, cbit in zip(measurement.qubits, measurement.cbits)
    ]


def _originir_measure(measurement: Measurement) -> List[str]:
    return [
        f"MEASURE q[{qubit.global_index}], c[{cbit.global_index}]"
        for qubit, cbit in zip(measurement.qubits, measurement.cbits)
    ]


SPINQ_GATES = {name: GateRule(name) for name in WHITELIST}

BRAKET_GATES = {
    "h": GateRule("h"),
    "x": GateRule("x"),
    "s": GateRule("s"),
    "sdg": GateRule("si"),
    "t": GateRule("t"),
    "tdg": GateRule("ti"),
    "rz": GateRule("rz"),
    "ry": GateRule("ry"),
    "cx": GateRule("cnot"),
    "cu1": GateRule("cphaseshift"),
    "swap": GateRule("swap"),
    "ccx": GateRule("ccnot"),
}

ORIGINQ_GATES = {
    "h": GateRule("H"),
    "x": GateRule("X"),
    "s": GateRule("S"),
    "sdg": GateRule("RZ", fixed_params=(-math.pi / 2,)),
    "t": GateRule("T"),
    "tdg": GateRule("RZ", fixed_params=(-math.pi / 4,)),
    "rz": GateRule("RZ"),
    "ry": GateRule("RY"),
    "cx": GateRule("CNOT"),
    "cu1": GateRule("CR"),
    "swap": GateRule("SWAP"),
    "ccx": GateRule("TOFFOLI"),
}

assert SPINQ_GATES.keys() == WHITELIST
assert BRAKET_GATES.keys() == WHITELIST
assert ORIGINQ_GATES.keys() == WHITELIST


def qasm2_spec() -> TargetSpec:
    return TargetSpec(
        _qasm2_header,
        dict(SPINQ_GATES),
        lambda ref: ref.token,
        _qasm2_measure,
    )


def qasm3_spec() -> TargetSpec:
    return TargetSpec(
        _qasm3_header,
        dict(BRAKET_GATES),
        lambda ref: ref.token,
        _qasm3_measure,
    )


def originir_spec() -> TargetSpec:
    return TargetSpec(
        _originir_header,
        dict(ORIGINQ_GATES),
        lambda ref: f"q[{ref.global_index}]",
        _originir_measure,
        params_after_qubits=True,
        terminator="",
    )
