"""Target IR transpilers for SpinQ, OriginQ and AWS Braket."""

from __future__ import annotations

import math
import re
from typing import List, Tuple

try:
    from qasm_engine import Circuit, Gate, parse_qasm
except ImportError:
    from starter_kit.qasm_engine import Circuit, Gate, parse_qasm

Gate = Tuple[str, List[int], List[float]]

SUPPORTED_TARGETS = ("spinq", "originq", "braket")

_ORIGINQ_MAP = {
    "h": "H",
    "x": "X",
    "s": "S",
    "sdg": "SDAG",
    "t": "T",
    "tdg": "TDAG",
    "rz": "RZ",
    "ry": "RY",
    "cx": "CNOT",
    "cu1": "CU1",
    "swap": "SWAP",
    "ccx": "CCX",
}


def _fmt_angle(theta: float) -> str:
    if abs(theta - math.pi) < 1e-9:
        return "pi"
    if abs(theta - math.pi / 2) < 1e-9:
        return "pi/2"
    if abs(theta + math.pi / 2) < 1e-9:
        return "-pi/2"
    if abs(theta - math.pi / 4) < 1e-9:
        return "pi/4"
    if abs(theta + math.pi / 4) < 1e-9:
        return "-pi/4"
    return f"{theta:.12g}"


def _decompose_gate(gate: str, qubits: List[int], params: List[float]) -> List[Gate]:
    if gate == "swap" and len(qubits) == 2:
        a, b = qubits
        return [
            ("cx", [a, b], []),
            ("cx", [b, a], []),
            ("cx", [a, b], []),
        ]
    if gate == "cu1" and len(qubits) == 2:
        a, b = qubits
        theta = params[0]
        return [
            ("u1", [a], [theta / 2]),
            ("cx", [a, b], []),
            ("u1", [b], [-theta / 2]),
            ("cx", [a, b], []),
            ("u1", [b], [theta / 2]),
        ]
    if gate == "ccx" and len(qubits) == 3:
        a, b, c = qubits
        return [
            ("h", [c], []),
            ("cx", [b, c], []),
            ("tdg", [c], []),
            ("cx", [a, c], []),
            ("t", [c], []),
            ("cx", [b, c], []),
            ("tdg", [c], []),
            ("cx", [a, c], []),
            ("t", [b], []),
            ("t", [c], []),
            ("h", [c], []),
            ("cx", [a, b], []),
            ("t", [a], []),
            ("tdg", [b], []),
            ("cx", [a, b], []),
        ]
    return [(gate, qubits, params)]


def _normalize_gates(circuit: Circuit, target: str) -> List[Gate]:
    expanded: List[Gate] = []
    for gate, qubits, params in circuit.gates:
        if gate == "u1":
            expanded.append(("u1", qubits, params))
            continue
        if gate in {"swap", "cu1", "ccx"} and target in {"originq"}:
            expanded.extend(_decompose_gate(gate, qubits, params))
        else:
            expanded.append((gate, qubits, params))
    return expanded


def _gate_to_qasm2(gate: str, qubits: List[int], params: List[float]) -> str:
    qargs = ", ".join("q[%d]" % q for q in qubits)
    if gate == "u1":
        return "u1(%s) %s;" % (_fmt_angle(params[0]), qargs)
    if params:
        return "%s(%s) %s;" % (gate, _fmt_angle(params[0]), qargs)
    return "%s %s;" % (gate, qargs)


def transpile_spinq(qasm_str: str) -> str:
    circuit = parse_qasm(qasm_str)
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{circuit.num_qubits}];",
        f"creg c[{circuit.num_clbits}];",
    ]
    for gate, qubits, params in _normalize_gates(circuit, "spinq"):
        if gate == "u1":
            lines.append(f"u1({_fmt_angle(params[0])}) q[{qubits[0]}];")
        else:
            lines.append(_gate_to_qasm2(gate, qubits, params))
    if circuit.measure_all:
        lines.append("measure q -> c;")
    else:
        for i in range(circuit.num_qubits):
            lines.append(f"measure q[{i}] -> c[{i}];")
    return "\n".join(lines) + "\n"


def transpile_braket(qasm_str: str) -> str:
    circuit = parse_qasm(qasm_str)
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        f"qubit[{circuit.num_qubits}] q;",
        f"bit[{circuit.num_clbits}] c;",
    ]
    for gate, qubits, params in _normalize_gates(circuit, "braket"):
        if gate == "cx":
            lines.append(f"cnot q[{qubits[0]}], q[{qubits[1]}];")
        elif gate == "u1":
            lines.append(f"u1({_fmt_angle(params[0])}) q[{qubits[0]}];")
        elif len(params) == 0:
            if len(qubits) == 1:
                lines.append(f"{gate} q[{qubits[0]}];")
            elif gate == "ccx":
                lines.append(f"ccx q[{qubits[0]}], q[{qubits[1]}], q[{qubits[2]}];")
            else:
                lines.append(f"{gate} q[{qubits[0]}], q[{qubits[1]}];")
        elif len(qubits) == 1:
            lines.append(f"{gate}({_fmt_angle(params[0])}) q[{qubits[0]}];")
        else:
            lines.append(f"{gate}({_fmt_angle(params[0])}) q[{qubits[0]}], q[{qubits[1]}];")
    lines.append("c = measure q;")
    return "\n".join(lines) + "\n"


def transpile_originq(qasm_str: str) -> str:
    circuit = parse_qasm(qasm_str)
    lines = [f"QINIT {circuit.num_qubits}", f"CREG {circuit.num_clbits}"]
    for gate, qubits, params in _normalize_gates(circuit, "originq"):
        op = _ORIGINQ_MAP.get(gate, gate.upper())
        if gate == "u1":
            lines.append(f"U1 q[{qubits[0]}],({_fmt_angle(params[0])})")
            continue
        if len(params) == 0:
            if len(qubits) == 1:
                lines.append(f"{op} q[{qubits[0]}]")
            elif len(qubits) == 2:
                lines.append(f"{op} q[{qubits[0]}], q[{qubits[1]}]")
            else:
                lines.append(f"{op} q[{qubits[0]}], q[{qubits[1]}], q[{qubits[2]}]")
        elif len(qubits) == 1:
            lines.append(f"{op} q[{qubits[0]}],({_fmt_angle(params[0])})")
        else:
            lines.append(f"{op} q[{qubits[0]}], q[{qubits[1]}],({_fmt_angle(params[0])})")
    for i in range(circuit.num_qubits):
        lines.append(f"MEASURE q[{i}], c[{i}]")
    return "\n".join(lines) + "\n"


def transpile(qasm_str: str, target: str) -> str:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")
    if target == "spinq":
        return transpile_spinq(qasm_str)
    if target == "braket":
        return transpile_braket(qasm_str)
    return transpile_originq(qasm_str)
