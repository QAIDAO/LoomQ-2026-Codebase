#!/usr/bin/env python3
"""Dialect emitters: flat Circuit -> target-native IR text.

Three emitters share one walk driven entirely by the dialect spellings in
gates.py; a new textual backend is a new GateDef column plus one emitter
function, not a copy of the pipeline. Parameter rendering is pi-aware
(`pi/4`, `2*pi/3`, decimal fallback) for QASM dialects and decimal-only for
OriginIR, per target_ir_contract.md.
"""

from __future__ import annotations

import math
from typing import Callable

try:
    from .gates import GATES
    from .ir import Circuit
except ImportError:
    from gates import GATES
    from ir import Circuit


def format_pi_expression(value: float) -> str:
    if abs(value) < 1e-12:
        return "0"
    quotient = value / math.pi
    if abs(quotient - round(quotient)) < 1e-9:
        n = int(round(quotient))
        return {0: "0", 1: "pi", -1: "-pi"}.get(n, "%d*pi" % n)
    for denominator in (2, 3, 4, 6, 8, 12, 16):
        scaled = quotient * denominator
        if abs(scaled - round(scaled)) < 1e-9:
            numerator = int(round(scaled))
            divisor = _gcd(abs(numerator), denominator)
            numerator //= divisor
            denominator //= divisor
            sign = "-" if numerator < 0 else ""
            magnitude = abs(numerator)
            if denominator == 1:
                return "%s%s" % (sign, "pi" if magnitude == 1 else "%d*pi" % magnitude)
            if magnitude == 1:
                return "%spi/%d" % (sign, denominator)
            return "%s%d*pi/%d" % (sign, magnitude, denominator)
    return "%.12g" % value


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a or 1


def format_decimal(value: float) -> str:
    if abs(value) < 1e-12:
        return "0"
    text = "%.15g" % value
    return text


def _render_call(dialect: str, gate: str, params: tuple[float, ...],
                 qubits: tuple[int, ...],
                 formatter: Callable[[float], str]) -> str:
    definition = GATES[gate]
    spelling = definition.dialect.get(dialect)
    if spelling is None:
        raise ValueError("gate %r has no %s spelling" % (gate, dialect))
    head = spelling
    if params:
        head += "(%s)" % ",".join(formatter(p) for p in params)
    args = ", ".join("q[%d]" % q for q in qubits)
    return "%s %s" % (head, args)


def _identity_measures(circuit: Circuit) -> bool:
    n = min(circuit.n_qubits, circuit.n_clbits)
    pairs = set(circuit.measures)
    return circuit.n_qubits == circuit.n_clbits and \
        all((i, i) in pairs for i in range(n))


# --------------------------------------------------------------------------
# emitters (one per textual dialect)
# --------------------------------------------------------------------------

def emit_openqasm2(circuit: Circuit) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";',
             "qreg q[%d];" % circuit.n_qubits, "creg c[%d];" % circuit.n_clbits]
    lines.extend(_render_call("qasm2", g, p, qs, format_pi_expression) + ";"
                 for g, p, qs in circuit.ops)
    measures = circuit.measures or [(i, i) for i in range(circuit.n_qubits)]
    lines.extend("measure q[%d] -> c[%d];" % m for m in measures)
    return "\n".join(lines) + "\n"


def emit_openqasm3(circuit: Circuit) -> str:
    lines = ["OPENQASM 3.0;", 'include "stdgates.inc";',
             "qubit[%d] q;" % circuit.n_qubits, "bit[%d] c;" % circuit.n_clbits]
    lines.extend(_render_call("qasm3", g, p, qs, format_pi_expression) + ";"
                 for g, p, qs in circuit.ops)
    measures = circuit.measures or [(i, i) for i in range(circuit.n_qubits)]
    if _identity_measures(circuit):
        lines.append("c = measure q;")
    else:
        lines.extend("c[%d] = measure q[%d];" % (c, q) for q, c in measures)
    return "\n".join(lines) + "\n"


def emit_originir(circuit: Circuit) -> str:
    lines = ["QINIT %d" % circuit.n_qubits, "CREG %d" % circuit.n_clbits]
    lines.extend(_render_call("originir", g, p, qs, format_decimal)
                 for g, p, qs in circuit.ops)
    measures = circuit.measures or [(i, i) for i in range(circuit.n_qubits)]
    lines.extend("MEASURE q[%d], c[%d]" % m for m in measures)
    return "\n".join(lines) + "\n"


EMITTERS: dict[str, Callable[[Circuit], str]] = {
    "qasm2": emit_openqasm2,
    "qasm3": emit_openqasm3,
    "originir": emit_originir,
}
