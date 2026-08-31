"""Amazon Braket target emitter: complete OpenQASM 3 program."""

from __future__ import annotations

from ..compiler.ir import Circuit, Gate, Measurement


_GATE_NAMES = {
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


def _gate(gate: Gate) -> str:
    name = _GATE_NAMES[gate.name]
    parameter = f"({format(gate.params[0], '.17g')})" if gate.params else ""
    operands = ", ".join(f"q[{qubit}]" for qubit in gate.qubits)
    return f"{name}{parameter} {operands};"


def emit_braket(circuit: Circuit) -> str:
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        f"qubit[{circuit.qubit_count}] q;",
        f"bit[{circuit.cbit_count}] c;",
    ]
    for operation in circuit.operations:
        if isinstance(operation, Gate):
            lines.append(_gate(operation))
        elif isinstance(operation, Measurement):
            lines.append(f"c[{operation.cbit}] = measure q[{operation.qubit}];")
    return "\n".join(lines) + "\n"
