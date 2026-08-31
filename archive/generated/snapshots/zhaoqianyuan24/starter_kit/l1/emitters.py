from .ir import (
    Circuit,
    Gate,
    Measurement,
)

from .gates import get_gate_name

def emit_spinq(circuit: Circuit) -> str:
    lines = []

    lines.append("OPENQASM 2.0;")
    lines.append('include "qelib1.inc";')
    lines.append("")

    lines.append(
        f"qreg q[{circuit.num_qubits}];"
    )

    lines.append(
        f"creg c[{circuit.num_clbits}];"
    )

    lines.append("")
    for operation in circuit.operations:
    
        if isinstance(operation, Gate):
    
            gate_name = get_gate_name(
                operation.name,
                "spinq"
            )
    
            qubits = ", ".join(
                f"q[{idx}]"
                for idx in operation.qubit_indices
            )
    
            if operation.parameter is None:
                line = (
                    f"{gate_name} "
                    f"{qubits};"
                )
    
            else:
                line = (
                    f"{gate_name}"
                    f"({operation.parameter}) "
                    f"{qubits};"
                )
    
            lines.append(line)
        elif isinstance(operation, Measurement):

            line = (
                f"measure q[{operation.qubit_idx}] "
                f"-> c[{operation.cbit_idx}];"
            )

            lines.append(line)

        else:
            raise TypeError(
                f"Unknown operation type: {type(operation)}"
            )

    return "\n".join(lines) + "\n"
def emit_braket(
    circuit: Circuit,
    include_stdgates: bool = True,
) -> str:

    lines = []

    lines.append("OPENQASM 3.0;")

    if include_stdgates:
        lines.append(
            'include "stdgates.inc";'
        )

    lines.append("")

    lines.append(
        f"qubit[{circuit.num_qubits}] q;"
    )

    lines.append(
        f"bit[{circuit.num_clbits}] c;"
    )

    lines.append("")

    for operation in circuit.operations:

        if isinstance(operation, Gate):

            gate_name = get_gate_name(
                operation.name,
                "braket"
            )

            qubits = ", ".join(
                f"q[{idx}]"
                for idx in operation.qubit_indices
            )

            if operation.parameter is None:

                lines.append(
                    f"{gate_name} {qubits};"
                )

            else:

                lines.append(
                    f"{gate_name}"
                    f"({operation.parameter}) "
                    f"{qubits};"
                )

        elif isinstance(operation, Measurement):

            lines.append(
                f"c[{operation.cbit_idx}] = "
                f"measure q[{operation.qubit_idx}];"
            )

        else:

            raise TypeError(
                f"Unknown operation type: "
                f"{type(operation)}"
            )

    return "\n".join(lines) + "\n"
def emit_originq(circuit: Circuit) -> str:
    lines = []

    lines.append(
        f"QINIT {circuit.num_qubits}"
    )

    lines.append(
        f"CREG {circuit.num_clbits}"
    )

    for operation in circuit.operations:

        if isinstance(operation, Gate):

            gate_name = get_gate_name(
                operation.name,
                "originq"
            )

            qubits = ", ".join(
                f"q[{idx}]"
                for idx in operation.qubit_indices
            )

            if operation.parameter is None:
                lines.append(
                    f"{gate_name} {qubits}"
                )

            else:
                lines.append(
                    f"{gate_name}"
                    f"({operation.parameter}) "
                    f"{qubits}"
                )

        elif isinstance(operation, Measurement):

            lines.append(
                f"MEASURE "
                f"q[{operation.qubit_idx}], "
                f"c[{operation.cbit_idx}]"
            )

        else:
            raise TypeError(
                f"Unknown operation type: "
                f"{type(operation)}"
            )

    return "\n".join(lines) + "\n"
