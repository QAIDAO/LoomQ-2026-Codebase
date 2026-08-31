"""Target IR code generators.

Each function renders a :class:`Circuit` into the exact subset specified
by ``target_ir_contract.md``:

- ``spinq``    -> complete executable OpenQASM 2.0 (qelib1 whitelist names)
- ``braket``   -> complete OpenQASM 3 (stdgates.inc names, bit-wise measure)
- ``originq``  -> OriginIR text (QINIT/CREG, MEASURE per bit)

The organizer parses and simulates these artifacts, so every emitted
statement must be part of the documented subset.
"""

from typing import List

try:
    from .circuit_ir import Circuit, GateOp
except ImportError:  # standalone-module fallback (evaluator imports by path)
    from circuit_ir import Circuit, GateOp

# originq -> allowed OriginIR spellings.
_ORIGINQ_NAMES = {
    "h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T", "tdg": "TDAG",
    "rz": "RZ", "ry": "RY", "cx": "CNOT", "cu1": "CU1", "swap": "SWAP",
    "ccx": "TOFFOLI",
}

# braket (OpenQASM 3 stdgates.inc) spellings.
_BRAKET_NAMES = {
    "h": "h", "x": "x", "s": "s", "sdg": "sdg", "t": "t", "tdg": "tdg",
    "rz": "rz", "ry": "ry", "cx": "cx", "cu1": "cp", "swap": "swap",
    "ccx": "ccx",
}

# spinq keeps qelib1 canonical names; u1 is a qelib1 gate so it stays as-is.
_SPINQ_NAMES = {
    "h": "h", "x": "x", "s": "s", "sdg": "sdg", "t": "t", "tdg": "tdg",
    "rz": "rz", "ry": "ry", "cx": "cx", "cu1": "cu1", "swap": "swap",
    "ccx": "ccx", "u1": "u1",
}


def _fmt(theta: float) -> str:
    """Compact float formatting that survives round trips."""
    return format(theta, ".12g")


def _params_suffix(op: GateOp) -> str:
    if not op.params:
        return ""
    return "(%s)" % ", ".join(_fmt(p) for p in op.params)


def _qubits(op: GateOp) -> str:
    return ", ".join("q[%d]" % q for q in op.qubits)


def to_spinq_qasm(circuit: Circuit) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";']
    lines.append("qreg q[%d];" % circuit.num_qubits)
    if circuit.num_cbits:
        lines.append("creg c[%d];" % circuit.num_cbits)
    for op in circuit.ops:
        lines.append("%s%s %s;" % (_SPINQ_NAMES[op.name], _params_suffix(op), _qubits(op)))
    for qubit, cbit in circuit.measures:
        lines.append("measure q[%d] -> c[%d];" % (qubit, cbit))
    return "\n".join(lines) + "\n"


def to_braket_qasm3(circuit: Circuit) -> str:
    lines = ["OPENQASM 3.0;", 'include "stdgates.inc";']
    lines.append("qubit[%d] q;" % circuit.num_qubits)
    if circuit.num_cbits:
        lines.append("bit[%d] c;" % circuit.num_cbits)
    for op in circuit.ops:
        lines.append("%s%s %s;" % (_BRAKET_NAMES[op.name], _params_suffix(op), _qubits(op)))
    for qubit, cbit in circuit.measures:
        lines.append("c[%d] = measure q[%d];" % (cbit, qubit))
    return "\n".join(lines) + "\n"


def to_originir(circuit: Circuit) -> str:
    lines = ["QINIT %d" % circuit.num_qubits]
    if circuit.num_cbits:
        lines.append("CREG %d" % circuit.num_cbits)
    for op in circuit.ops:
        lines.append(
            "%s%s %s" % (_ORIGINQ_NAMES[op.name], _params_suffix(op), _qubits(op))
        )
    for qubit, cbit in circuit.measures:
        lines.append("MEASURE q[%d], c[%d]" % (qubit, cbit))
    return "\n".join(lines) + "\n"
