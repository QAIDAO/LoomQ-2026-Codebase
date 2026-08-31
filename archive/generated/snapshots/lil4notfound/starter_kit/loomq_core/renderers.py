"""Render the canonical circuit model into competition target formats."""

from typing import Callable, Dict, List

from .model import BitRef, Circuit, Operation


def render_spinq(circuit: Circuit) -> str:
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";']
    lines.extend(f"qreg {item.name}[{item.size}];" for item in circuit.quantum_registers)
    lines.extend(f"creg {item.name}[{item.size}];" for item in circuit.classical_registers)
    lines.extend(_qasm_gate(operation, qasm3=False) for operation in circuit.operations)
    lines.extend(
        f"measure {_bit(item.qubit)} -> {_bit(item.classical)};"
        for item in circuit.measurements
    )
    return "\n".join(lines) + "\n"


def render_braket(circuit: Circuit) -> str:
    lines = ['OPENQASM 3.0;', 'include "stdgates.inc";']
    lines.extend(f"qubit[{item.size}] {item.name};" for item in circuit.quantum_registers)
    lines.extend(f"bit[{item.size}] {item.name};" for item in circuit.classical_registers)
    lines.extend(_qasm_gate(operation, qasm3=True) for operation in circuit.operations)
    lines.extend(
        f"{_bit(item.classical)} = measure {_bit(item.qubit)};"
        for item in circuit.measurements
    )
    return "\n".join(lines) + "\n"


def render_originq(circuit: Circuit) -> str:
    names = {
        "h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T",
        "tdg": "TDAG", "rz": "RZ", "ry": "RY", "cx": "CNOT",
        "cu1": "CU1", "swap": "SWAP", "ccx": "TOFFOLI",
    }
    lines = [f"QINIT {circuit.qubit_count}", f"CREG {circuit.classical_bit_count}"]
    for operation in circuit.operations:
        qubits = [f"q[{circuit.quantum_index(bit)}]" for bit in operation.qubits]
        gate = names[operation.name]
        if operation.parameter is not None:
            gate += f"({_number(operation.parameter)})"
        lines.append(f"{gate} {', '.join(qubits)}")
    lines.extend(
        f"MEASURE q[{circuit.quantum_index(item.qubit)}], c[{circuit.classical_index(item.classical)}]"
        for item in circuit.measurements
    )
    return "\n".join(lines) + "\n"


RENDERERS: Dict[str, Callable[[Circuit], str]] = {
    "spinq": render_spinq,
    "originq": render_originq,
    "braket": render_braket,
}


def _qasm_gate(operation: Operation, qasm3: bool) -> str:
    name = operation.name
    if qasm3:
        name = {"cx": "cnot", "cu1": "cp"}.get(name, name)
    parameter = "" if operation.parameter is None else f"({_number(operation.parameter)})"
    return f"{name}{parameter} {', '.join(_bit(bit) for bit in operation.qubits)};"


def _bit(bit: BitRef) -> str:
    return f"{bit.register}[{bit.index}]"


def _number(value: float) -> str:
    if value == 0:
        return "0"
    return format(value, ".17g")
