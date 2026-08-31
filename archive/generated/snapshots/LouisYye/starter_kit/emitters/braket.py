try:
    from ..ir import Circuit
except ImportError:
    from ir import Circuit


BRAKET_GATE_NAMES = {
    "h": "h",
    "x": "x",
    "s": "s",
    "sdg": "si",
    "t": "t",
    "tdg": "ti",
    "ry": "ry",
    "rz": "rz",
    "cx": "cnot",
    "cu1": "cphaseshift",
    "swap": "swap",
    "ccx": "ccnot",
}


def emit_braket(
    circuit: Circuit,
    include_stdlib: bool = True,
) -> str:
    """Convert the shared Circuit IR into Braket OpenQASM 3."""

    lines = ["OPENQASM 3.0;"]

    if include_stdlib:
        lines.append('include "stdgates.inc";')

    lines.append(
        f"qubit[{circuit.num_qubits}] q;"
    )

    if circuit.num_bits > 0:
        lines.append(
            f"bit[{circuit.num_bits}] c;"
        )

    lines.append("")

    for gate in circuit.gates:
        target_name = BRAKET_GATE_NAMES.get(
            gate.name
        )

        if target_name is None:
            raise ValueError(
                f"Unsupported Braket gate: "
                f"{gate.name}"
            )

        qubits = ", ".join(
            f"q[{index}]"
            for index in gate.qubits
        )

        if gate.params:
            params = ", ".join(
                repr(float(param))
                for param in gate.params
            )

            lines.append(
                f"{target_name}({params}) "
                f"{qubits};"
            )
        else:
            lines.append(
                f"{target_name} {qubits};"
            )

    if circuit.measurements:
        lines.append("")

        for measurement in circuit.measurements:
            lines.append(
                f"c[{measurement.bit}] = "
                f"measure "
                f"q[{measurement.qubit}];"
            )

    return "\n".join(lines)