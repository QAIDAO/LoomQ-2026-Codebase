"""Origin Quantum target emitter: canonical OriginIR subset."""

from __future__ import annotations

from ..compiler.ir import Circuit, Gate, Measurement


_GATE_NAMES = {
    "h": "H",
    "x": "X",
    "s": "S",
    "t": "T",
    "rz": "RZ",
    "ry": "RY",
    "cx": "CNOT",
    "cu1": "CR",
    "swap": "SWAP",
    "ccx": "TOFFOLI",
}


def _gate_lines(gate: Gate) -> list[str]:
    operands = ", ".join(f"q[{qubit}]" for qubit in gate.qubits)
    if gate.name == "sdg":
        return [f"S {operands}"] * 3
    if gate.name == "tdg":
        return [f"T {operands}"] * 7
    name = _GATE_NAMES[gate.name]
    if gate.params:
        parameter = format(gate.params[0], ".17g")
        return [f"{name} {operands},({parameter})"]
    return [f"{name} {operands}"]


def emit_originq(circuit: Circuit) -> str:
    lines = [f"QINIT {circuit.qubit_count}", f"CREG {circuit.cbit_count}"]
    for operation in circuit.operations:
        if isinstance(operation, Gate):
            lines.extend(_gate_lines(operation))
        elif isinstance(operation, Measurement):
            lines.append(f"MEASURE q[{operation.qubit}], c[{operation.cbit}]")
    return "\n".join(lines) + "\n"
