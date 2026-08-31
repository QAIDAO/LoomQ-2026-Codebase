"""Target emitters fed exclusively by the typed LoomQ IR."""

from __future__ import annotations

from .ir import Circuit, Gate, Measure, format_angle


SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def _parameter(operation: Gate) -> str:
    return "(" + ",".join(format_angle(value) for value in operation.parameters) + ")" if operation.parameters else ""


def emit_spinq(circuit: Circuit) -> str:
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";']
    lines.extend(f"qreg {name}[{size}];" for name, size in circuit.qregs.items())
    lines.extend(f"creg {name}[{size}];" for name, size in circuit.cregs.items())
    for operation in circuit.operations:
        if isinstance(operation, Gate):
            args = ", ".join(ref.qasm() for ref in operation.qubits)
            lines.append(f"{operation.name}{_parameter(operation)} {args};")
        else:
            lines.append(f"measure {operation.qubit.qasm()} -> {operation.cbit.qasm()};")
    return "\n".join(lines) + "\n"


def emit_braket(circuit: Circuit) -> str:
    lines = ['OPENQASM 3.0;', 'include "stdgates.inc";']
    lines.extend(f"qubit[{size}] {name};" for name, size in circuit.qregs.items())
    lines.extend(f"bit[{size}] {name};" for name, size in circuit.cregs.items())
    names = {"cx": "cnot", "cu1": "cp"}
    for operation in circuit.operations:
        if isinstance(operation, Gate):
            name = names.get(operation.name, operation.name)
            args = ", ".join(ref.qasm() for ref in operation.qubits)
            lines.append(f"{name}{_parameter(operation)} {args};")
        else:
            lines.append(f"{operation.cbit.qasm()} = measure {operation.qubit.qasm()};")
    return "\n".join(lines) + "\n"


def emit_originq(circuit: Circuit) -> str:
    lines = [f"QINIT {circuit.total_qubits}", f"CREG {circuit.total_cbits}"]
    names = {
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
        "ccx": "TOFFOLI",
    }
    for operation in circuit.operations:
        if isinstance(operation, Gate):
            name = names[operation.name]
            parameter = _parameter(operation)
            args = ", ".join(f"q[{circuit.qubit_index(ref)}]" for ref in operation.qubits)
            lines.append(f"{name}{parameter} {args}")
        else:
            qindex = circuit.qubit_index(operation.qubit)
            cindex = circuit.cbit_index(operation.cbit)
            lines.append(f"MEASURE q[{qindex}], c[{cindex}]")
    return "\n".join(lines) + "\n"


def emit_target(circuit: Circuit, target: str) -> str:
    normalized = target.strip().lower() if isinstance(target, str) else ""
    if normalized == "spinq":
        return emit_spinq(circuit)
    if normalized == "originq":
        return emit_originq(circuit)
    if normalized == "braket":
        return emit_braket(circuit)
    raise ValueError(f"unsupported target {target!r}; expected one of {SUPPORTED_TARGETS}")
