try:
    from ..ir import Circuit, Gate
except ImportError:
    from ir import Circuit, Gate


SPINQ_GATE_NAMES = {
    "h": "h",
    "x": "x",
    "s": "s",
    "sdg": "sdg",
    "t": "t",
    "tdg": "tdg",
    "ry": "ry",
    "rz": "rz",
    "cx": "cx",
    "cu1": "cu1",
    "swap": "swap",
    "ccx": "ccx",
}


def _emit_gate(gate: Gate) -> str:
    target_name = SPINQ_GATE_NAMES.get(gate.name)
    if target_name is None:
        raise ValueError(f"Unsupported SpinQ gate: {gate.name}")

    qubits = ", ".join(f"q[{index}]" for index in gate.qubits)

    if gate.name in {"ry", "rz", "cu1"}:
        if len(gate.params) != 1:
            raise ValueError(
                f"SpinQ gate {gate.name} requires one parameter, "
                f"got {len(gate.params)}"
            )
        return f"{target_name}({repr(float(gate.params[0]))}) {qubits};"

    if gate.params:
        raise ValueError(
            f"SpinQ gate {gate.name} does not accept parameters"
        )

    return f"{target_name} {qubits};"


def emit_spinq(circuit: Circuit) -> str:
    """Convert the shared Circuit IR into complete OpenQASM 2.0."""

    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{circuit.num_qubits}];",
    ]

    if circuit.num_bits > 0:
        lines.append(f"creg c[{circuit.num_bits}];")

    lines.append("")

    for gate in circuit.gates:
        lines.append(_emit_gate(gate))

    if circuit.measurements:
        lines.append("")
        for measurement in circuit.measurements:
            lines.append(
                f"measure q[{measurement.qubit}] -> c[{measurement.bit}];"
            )

    return "\n".join(lines)
