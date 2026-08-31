"""SpinQ target emitter: complete OpenQASM 2.0."""

from __future__ import annotations

from ..compiler.ir import Circuit, Gate, Measurement


def _number(value: float) -> str:
    return format(value, ".17g")


def _gate(gate: Gate) -> str:
    parameter = f"({_number(gate.params[0])})" if gate.params else ""
    operands = ", ".join(f"q[{qubit}]" for qubit in gate.qubits)
    return f"{gate.name}{parameter} {operands};"


def emit_spinq(circuit: Circuit) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{circuit.qubit_count}];",
        f"creg c[{circuit.cbit_count}];",
    ]
    for operation in circuit.operations:
        if isinstance(operation, Gate):
            lines.append(_gate(operation))
        elif isinstance(operation, Measurement):
            lines.append(f"measure q[{operation.qubit}] -> c[{operation.cbit}];")
    return "\n".join(lines) + "\n"
