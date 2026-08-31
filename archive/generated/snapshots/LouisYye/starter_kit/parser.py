from qiskit import qasm2

try:
    from .ir import Circuit, Gate, Measurement
except ImportError:
    from ir import Circuit, Gate, Measurement


ALLOWED_GATES = {
    "h",
    "x",
    "s",
    "sdg",
    "t",
    "tdg",
    "ry",
    "rz",
    "cx",
    "cu1",
    "swap",
    "ccx",
}


def parse_qasm(qasm_str: str) -> Circuit:
    """Parse the LoomQ OpenQASM 2 subset into the shared Circuit IR."""

    if not isinstance(qasm_str, str):
        raise TypeError("qasm_str must be a string")

    if not qasm_str.strip():
        raise ValueError("qasm_str must not be empty")

    quantum_circuit = qasm2.loads(
        qasm_str,
        custom_instructions=(
            qasm2.LEGACY_CUSTOM_INSTRUCTIONS
        ),
    )

    circuit = Circuit(
        num_qubits=quantum_circuit.num_qubits,
        num_bits=quantum_circuit.num_clbits,
    )

    for item in quantum_circuit.data:
        instruction = item.operation
        qargs = item.qubits
        cargs = item.clbits

        name = instruction.name

        # Barriers do not change circuit semantics.
        if name == "barrier":
            continue

        qubits = [
            quantum_circuit.find_bit(qubit).index
            for qubit in qargs
        ]

        if name == "measure":
            if len(qubits) != 1 or len(cargs) != 1:
                raise ValueError(
                    "Each measurement must map one "
                    "qubit to one classical bit"
                )

            classical_bit = (
                quantum_circuit.find_bit(cargs[0]).index
            )

            circuit.measurements.append(
                Measurement(
                    qubit=qubits[0],
                    bit=classical_bit,
                )
            )

            continue

        if name not in ALLOWED_GATES:
            raise ValueError(
                f"Unsupported gate: {name}"
            )

        params = [
            float(param)
            for param in instruction.params
        ]

        circuit.gates.append(
            Gate(
                name=name,
                qubits=qubits,
                params=params,
            )
        )

    return circuit