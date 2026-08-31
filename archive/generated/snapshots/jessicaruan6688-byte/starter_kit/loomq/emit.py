"""Emit target-native IR from the unified circuit AST."""

from __future__ import annotations

from typing import List

from .circuit import Circuit, GateOp, MeasureOp
from .gates import decompose_gate, expand_circuit, format_angle


def _qref(name: str, idx: int) -> str:
    return f"{name}[{idx}]"


def _emit_qasm2_gate(op: GateOp) -> str:
    name = op.name
    args = ", ".join(_qref(q, i) for q, i in op.qubits)
    if op.params:
        return f"{name}({format_angle(op.params[0])}) {args};"
    return f"{name} {args};"


def emit_spinq_qasm2(circuit: Circuit) -> str:
    """SpinQ target: OpenQASM 2.0 with the whitelist gate set.

    Keep cu1/ccx/swap native (qelib1) so controlled-phase identities stay exact.
    """
    lines: List[str] = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
    ]
    for name, size in circuit.qregs.items():
        lines.append(f"qreg {name}[{size}];")
    for name, size in circuit.cregs.items():
        lines.append(f"creg {name}[{size}];")
    for op in circuit.ops:
        if isinstance(op, GateOp):
            lines.append(_emit_qasm2_gate(op))
        else:
            qn, qi = op.qubit
            cn, ci = op.cbit
            lines.append(f"measure {_qref(qn, qi)} -> {_qref(cn, ci)};")
    return "\n".join(lines) + "\n"


# Canonical OpenQASM 3 names from stdgates.inc, used for the submitted IR.
_QASM3_STDGATES = {
    "h": "h",
    "x": "x",
    "s": "s",
    "sdg": "sdg",
    "t": "t",
    "tdg": "tdg",
    "rz": "rz",
    "ry": "ry",
    "cx": "cx",
    "swap": "swap",
    "ccx": "ccx",
}

# Braket's built-in gate vocabulary, used only for local execution. Braket does
# not ship stdgates.inc and rejects the stdgates spellings below.
_BRAKET_NATIVE_GATE = {
    "h": "h",
    "x": "x",
    "s": "s",
    "sdg": "si",
    "t": "t",
    "tdg": "ti",
    "rz": "rz",
    "ry": "ry",
    "cx": "cnot",
    "cu1": "cphaseshift",
    "swap": "swap",
    "ccx": "ccnot",
}


def _emit_qasm3(circuit: Circuit, gate_names: dict, include_stdgates: bool) -> str:
    nq = circuit.n_qubits()
    nc = circuit.n_clbits()
    lines: List[str] = ["OPENQASM 3.0;"]
    if include_stdgates:
        lines.append('include "stdgates.inc";')
    lines.append(f"qubit[{nq}] q;")
    lines.append(f"bit[{nc}] c;")

    def emit_gate(op: GateOp) -> None:
        gate = gate_names.get(op.name)
        if gate is None:
            # stdgates.inc has no cu1/cphaseshift, so fall back to the official
            # rz/cx identity, which differs only by an unobservable global phase.
            if op.name == "cu1":
                for part in decompose_gate(op, mode="basic"):
                    emit_gate(part)
                return
            raise ValueError(f"unsupported OpenQASM 3 gate: {op.name}")
        qargs = ", ".join(f"q[{circuit.qubit_index(q)}]" for q in op.qubits)
        if op.params:
            lines.append(f"{gate}({format_angle(op.params[0])}) {qargs};")
        else:
            lines.append(f"{gate} {qargs};")

    for op in circuit.ops:
        if isinstance(op, GateOp):
            emit_gate(op)
        else:
            qi = circuit.qubit_index(op.qubit)
            ci = circuit.cbit_index(op.cbit)
            lines.append(f"c[{ci}] = measure q[{qi}];")
    return "\n".join(lines) + "\n"


def emit_braket_qasm3(circuit: Circuit) -> str:
    """Braket target IR per target_ir_contract.md: canonical OpenQASM 3."""
    return _emit_qasm3(circuit, _QASM3_STDGATES, include_stdgates=True)


def emit_braket_native_qasm3(circuit: Circuit) -> str:
    """Execution-only dialect for Braket's LocalSimulator.

    The contract IR is what gets submitted; this variant exists because the local
    simulator cannot resolve ``include "stdgates.inc"`` and only knows its own
    gate names.
    """
    return _emit_qasm3(circuit, _BRAKET_NATIVE_GATE, include_stdgates=False)


_ORIGIN_GATE = {
    "h": "H",
    "x": "X",
    "s": "S",
    "sdg": "SDAG",
    "t": "T",
    "tdg": "TDAG",
    "ry": "RY",
    "rz": "RZ",
    "cx": "CNOT",
    "cu1": "CU1",
    "swap": "SWAP",
    "ccx": "TOFFOLI",
}


def emit_originir(circuit: Circuit) -> str:
    """OriginQ target: OriginIR text subset from target_ir_contract.md."""
    # Keep high-level gates when OriginIR names them directly.
    expanded = expand_circuit(circuit, mode="none")
    nq = expanded.n_qubits()
    nc = expanded.n_clbits()
    lines: List[str] = [
        f"QINIT {nq}",
        f"CREG {nc}",
    ]
    for op in expanded.ops:
        if isinstance(op, GateOp):
            gate = _ORIGIN_GATE.get(op.name)
            if gate is None:
                raise ValueError(f"unsupported OriginIR gate: {op.name}")
            qs = [expanded.qubit_index(q) for q in op.qubits]
            qargs = ", ".join(f"q[{i}]" for i in qs)
            if op.params:
                lines.append(f"{gate}({format_angle(op.params[0])}) {qargs}")
            else:
                lines.append(f"{gate} {qargs}")
        else:
            qi = expanded.qubit_index(op.qubit)
            ci = expanded.cbit_index(op.cbit)
            lines.append(f"MEASURE q[{qi}], c[{ci}]")
    return "\n".join(lines) + "\n"


EMITTERS = {
    "spinq": emit_spinq_qasm2,
    "braket": emit_braket_qasm3,
    "originq": emit_originir,
}


def emit(circuit: Circuit, target: str) -> str:
    if target not in EMITTERS:
        raise ValueError(f"unsupported target '{target}', expected one of {sorted(EMITTERS)}")
    return EMITTERS[target](circuit)
