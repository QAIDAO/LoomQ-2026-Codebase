"""Target IR emitters for the three LoomQ backends.

All emitters consume the same Circuit IR, so backend support is a pure
function of the IR -- no per-backend special-casing of input programs.

- spinq   -> normalized OpenQASM 2.0 (the whitelist is native qelib1)
- braket  -> OpenQASM 3.0 with stdgates.inc (cu1 lowered via the validated
             p/cnot decomposition from gate_identities.md)
- originq -> canonical OriginIR subset from target_ir_contract.md

Each emitter has a matching ``parse_*`` reader for the exact subset it emits,
so ``run()`` can execute the *transpiled* artifact on the reference
simulator -- transpilation bugs can never hide behind the executor.
"""

from __future__ import annotations

import re
from typing import List

from .qasm import Circuit, Gate, parse_qasm2, _split_top_level_commas


def _fmt_angle(value: float) -> str:
    return repr(float(value))


# ---------------------------------------------------------------------------
# spinq: normalized OpenQASM 2.0
# ---------------------------------------------------------------------------

def emit_spinq(circuit: Circuit) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % circuit.num_qubits,
        "creg c[%d];" % max(circuit.num_clbits, circuit.num_qubits),
    ]
    for gate in circuit.gates:
        lines.append(_format_qasm2_gate(gate))
    for qubit, clbit in _sorted_measurements(circuit):
        lines.append("measure q[%d] -> c[%d];" % (qubit, clbit))
    return "\n".join(lines) + "\n"


def _sorted_measurements(circuit: Circuit):
    if circuit.measurements:
        return sorted(circuit.measurements)
    return [(k, k) for k in range(circuit.num_qubits)]


def _format_qasm2_gate(gate: Gate) -> str:
    operands = ", ".join("q[%d]" % q for q in gate.qubits)
    if gate.params:
        params = ", ".join(_fmt_angle(p) for p in gate.params)
        return "%s(%s) %s;" % (gate.name, params, operands)
    return "%s %s;" % (gate.name, operands)


# ---------------------------------------------------------------------------
# braket: OpenQASM 3.0
# ---------------------------------------------------------------------------

_BRAKET_GATE_NAMES = {
    "h": "h", "x": "x", "s": "s", "sdg": "sdg", "t": "t", "tdg": "tdg",
    "rz": "rz", "ry": "ry", "u1": "p", "p": "p",
    "cx": "cx", "swap": "swap", "ccx": "ccx",
}


def emit_braket(circuit: Circuit) -> str:
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        "qubit[%d] q;" % circuit.num_qubits,
        "bit[%d] c;" % max(circuit.num_clbits, circuit.num_qubits),
    ]
    for gate in _lower_for_braket(circuit.gates):
        name = _BRAKET_GATE_NAMES[gate.name]
        operands = ", ".join("q[%d]" % q for q in gate.qubits)
        if gate.params:
            params = ", ".join(_fmt_angle(p) for p in gate.params)
            lines.append("%s(%s) %s;" % (name, params, operands))
        else:
            lines.append("%s %s;" % (name, operands))
    for qubit, clbit in _sorted_measurements(circuit):
        lines.append("c[%d] = measure q[%d];" % (clbit, qubit))
    return "\n".join(lines) + "\n"


def _lower_for_braket(gates: List[Gate]) -> List[Gate]:
    """stdgates.inc has no cu1; lower it with the validated decomposition.

    cu1(theta) a, b  ==  p(theta/2) a; cx a, b; p(-theta/2) b; cx a, b; p(theta/2) b
    """
    lowered: List[Gate] = []
    for gate in gates:
        if gate.name != "cu1":
            lowered.append(gate)
            continue
        theta = gate.params[0]
        a, b = gate.qubits
        lowered.extend(
            [
                Gate("p", (theta / 2,), (a,)),
                Gate("cx", (), (a, b)),
                Gate("p", (-theta / 2,), (b,)),
                Gate("cx", (), (a, b)),
                Gate("p", (theta / 2,), (b,)),
            ]
        )
    return lowered


# ---------------------------------------------------------------------------
# originq: canonical OriginIR subset
# ---------------------------------------------------------------------------

_ORIGINQ_GATE_NAMES = {
    "h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T", "tdg": "TDAG",
    "rz": "RZ", "ry": "RY", "u1": "U1", "p": "P",
    "cx": "CNOT", "cu1": "CU1", "swap": "SWAP", "ccx": "TOFFOLI",
}


def emit_originq(circuit: Circuit) -> str:
    lines = [
        "QINIT %d" % circuit.num_qubits,
        "CREG %d" % max(circuit.num_clbits, circuit.num_qubits),
    ]
    for gate in circuit.gates:
        name = _ORIGINQ_GATE_NAMES[gate.name]
        operands = ", ".join("q[%d]" % q for q in gate.qubits)
        if gate.params:
            params = ", ".join(_fmt_angle(p) for p in gate.params)
            lines.append("%s(%s) %s" % (name, params, operands))
        else:
            lines.append("%s %s" % (name, operands))
    for qubit, clbit in _sorted_measurements(circuit):
        lines.append("MEASURE q[%d], c[%d]" % (qubit, clbit))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Round-trip readers for the emitted subsets
# ---------------------------------------------------------------------------

def parse_target_ir(target: str, text: str) -> Circuit:
    """Parse a target IR artifact back into the Circuit IR for execution."""
    if target == "spinq":
        return parse_qasm2(text)
    if target == "braket":
        return _parse_braket_qasm3(text)
    if target == "originq":
        return _parse_originir(text)
    raise ValueError("unknown target: %s" % target)


def _parse_braket_qasm3(text: str) -> Circuit:
    num_qubits = num_clbits = 0
    gates: List[Gate] = []
    measurements = []
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        m = re.fullmatch(r"qubit\[(\d+)\]\s+q;", line)
        if m:
            num_qubits = int(m.group(1))
            continue
        m = re.fullmatch(r"bit\[(\d+)\]\s+c;", line)
        if m:
            num_clbits = int(m.group(1))
            continue
        m = re.fullmatch(r"c\[(\d+)\]\s*=\s*measure\s+q\[(\d+)\];", line)
        if m:
            measurements.append((int(m.group(2)), int(m.group(1))))
            continue
        m = re.fullmatch(r"c\s*=\s*measure\s+q;", line)
        if m:
            measurements.extend((k, k) for k in range(num_qubits))
            continue
        if line.startswith(("OPENQASM", "include")):
            continue
        m = re.fullmatch(
            r"([A-Za-z][A-Za-z0-9]*)(?:\((.+)\))?\s+((?:q\[\d+\])(?:\s*,\s*q\[\d+\])*);",
            line,
        )
        if m:
            name = m.group(1).lower()
            if name == "cnot":
                name = "cx"
            if name == "cp":
                name = "cu1"
            params = ()
            if m.group(2) is not None:
                params = tuple(float(p) for p in _split_top_level_commas(m.group(2)))
            qubits = tuple(int(x) for x in re.findall(r"q\[(\d+)\]", m.group(3)))
            gates.append(Gate(name, params, qubits))
            continue
        raise ValueError("unparseable OpenQASM 3 line: %r" % line)
    if not num_qubits:
        raise ValueError("no qubit register in OpenQASM 3 artifact")
    return Circuit(num_qubits, num_clbits, gates, measurements)


def _parse_originir(text: str) -> Circuit:
    num_qubits = num_clbits = 0
    gates: List[Gate] = []
    measurements = []
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        m = re.fullmatch(r"QINIT\s+(\d+)", line)
        if m:
            num_qubits = int(m.group(1))
            continue
        m = re.fullmatch(r"CREG\s+(\d+)", line)
        if m:
            num_clbits = int(m.group(1))
            continue
        m = re.fullmatch(r"MEASURE\s+q\[(\d+)\]\s*,\s*c\[(\d+)\]", line)
        if m:
            measurements.append((int(m.group(1)), int(m.group(2))))
            continue
        m = re.fullmatch(
            r"([A-Za-z][A-Za-z0-9]*)(?:\((.+)\))?\s+((?:q\[\d+\])(?:\s*,\s*q\[\d+\])*)",
            line,
        )
        if m:
            name = m.group(1).upper()
            name = {"SDAG": "sdg", "TDAG": "tdg", "CNOT": "cx", "TOFFOLI": "ccx",
                    "CCX": "ccx", "CR": "cu1", "U1": "u1", "P": "p"}.get(name, name.lower())
            params = ()
            if m.group(2) is not None:
                params = tuple(float(p) for p in _split_top_level_commas(m.group(2)))
            qubits = tuple(int(x) for x in re.findall(r"q\[(\d+)\]", m.group(3)))
            gates.append(Gate(name, params, qubits))
            continue
        raise ValueError("unparseable OriginIR line: %r" % line)
    if not num_qubits:
        raise ValueError("no QINIT in OriginIR artifact")
    return Circuit(num_qubits, num_clbits, gates, measurements)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_EMITTERS = {"spinq": emit_spinq, "braket": emit_braket, "originq": emit_originq}


def transpile_circuit(circuit: Circuit, target: str) -> str:
    if target not in _EMITTERS:
        raise ValueError(
            "unsupported target %r; expected one of %s" % (target, sorted(_EMITTERS))
        )
    return _EMITTERS[target](circuit)
