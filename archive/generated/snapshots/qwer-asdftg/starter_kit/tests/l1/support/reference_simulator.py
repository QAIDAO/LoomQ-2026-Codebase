"""Small NumPy statevector reference for the LoomQ L1 OpenQASM subset."""

import math

import numpy as np

from starter_kit.loomq_l1.parser import parse_qasm


_SINGLE_QUBIT_MATRICES = {
    "h": np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2),
    "x": np.array([[0, 1], [1, 0]], dtype=complex),
    "s": np.array([[1, 0], [0, 1j]], dtype=complex),
    "sdg": np.array([[1, 0], [0, -1j]], dtype=complex),
    "t": np.array([[1, 0], [0, np.exp(1j * math.pi / 4)]], dtype=complex),
    "tdg": np.array([[1, 0], [0, np.exp(-1j * math.pi / 4)]], dtype=complex),
}


def _apply_matrix(state, matrix, qubit):
    """Apply a 2x2 matrix where q0 is the least-significant basis bit."""
    bit = 1 << qubit
    for base in range(state.size):
        if base & bit:
            continue
        paired = base | bit
        zero, one = state[base], state[paired]
        state[base] = matrix[0, 0] * zero + matrix[0, 1] * one
        state[paired] = matrix[1, 0] * zero + matrix[1, 1] * one


def _apply_cx(state, control, target):
    control_bit, target_bit = 1 << control, 1 << target
    for base in range(state.size):
        if base & control_bit and not base & target_bit:
            paired = base | target_bit
            state[base], state[paired] = state[paired], state[base]


def _apply_cu1(state, control, target, angle):
    mask = (1 << control) | (1 << target)
    state[np.arange(state.size) & mask == mask] *= np.exp(1j * angle)


def _apply_ccx(state, control_a, control_b, target):
    controls, target_bit = (1 << control_a) | (1 << control_b), 1 << target
    for base in range(state.size):
        if base & controls == controls and not base & target_bit:
            paired = base | target_bit
            state[base], state[paired] = state[paired], state[base]


def _apply_swap(state, qubit_a, qubit_b):
    bit_a, bit_b = 1 << qubit_a, 1 << qubit_b
    for base in range(state.size):
        if not base & bit_a and base & bit_b:
            paired = base ^ bit_a ^ bit_b
            state[base], state[paired] = state[paired], state[base]


def _apply_named_operation(state, name, qubits, angle):
    if name in _SINGLE_QUBIT_MATRICES:
        _apply_matrix(state, _SINGLE_QUBIT_MATRICES[name], qubits[0])
    elif name == "rz":
        _apply_matrix(
            state,
            np.array(
                [[np.exp(-1j * angle / 2), 0], [0, np.exp(1j * angle / 2)]], dtype=complex
            ),
            qubits[0],
        )
    elif name == "ry":
        _apply_matrix(
            state,
            np.array(
                [[math.cos(angle / 2), -math.sin(angle / 2)], [math.sin(angle / 2), math.cos(angle / 2)]],
                dtype=complex,
            ),
            qubits[0],
        )
    elif name == "u1":
        _apply_matrix(
            state,
            np.array([[1, 0], [0, np.exp(1j * angle)]], dtype=complex),
            qubits[0],
        )
    elif name == "cx":
        _apply_cx(state, *qubits)
    elif name == "cu1":
        _apply_cu1(state, *qubits, angle)
    elif name == "ccx":
        _apply_ccx(state, *qubits)
    elif name == "swap":
        _apply_swap(state, *qubits)
    else:  # pragma: no cover - the production parser admits only the L1 whitelist.
        raise ValueError(f"unsupported reference gate: {name}")


def _apply_operation(state, operation):
    _apply_named_operation(state, operation.name, operation.qubits, operation.parameter)


def simulate_operation_probabilities(num_qubits, operations):
    """Return basis probabilities for a test-only sequence including documented ``u1``."""
    state = np.zeros(1 << num_qubits, dtype=complex)
    state[0] = 1.0
    for name, qubits, angle in operations:
        _apply_named_operation(state, name, qubits, angle)
    return {
        format(basis, f"0{num_qubits}b"): round(float(abs(amplitude) ** 2), 15)
        for basis, amplitude in enumerate(state)
        if abs(amplitude) ** 2 >= 1e-15
    }


def simulate_probabilities(qasm):
    """Return canonical c[n-1]...c[0] probabilities for a strict L1 QASM circuit."""
    circuit = parse_qasm(qasm)
    state = np.zeros(1 << circuit.num_qubits, dtype=complex)
    state[0] = 1.0
    for operation in circuit.operations:
        _apply_operation(state, operation)

    probabilities = {}
    for basis, amplitude in enumerate(state):
        probability = float(abs(amplitude) ** 2)
        if probability < 1e-15:
            continue
        cbits = [0] * circuit.num_clbits
        for measurement in circuit.measurements:
            cbits[measurement.cbit] = (basis >> measurement.qubit) & 1
        key = "".join(str(cbits[index]) for index in range(circuit.num_clbits - 1, -1, -1))
        probabilities[key] = probabilities.get(key, 0.0) + probability
    return {key: round(probability, 15) for key, probability in probabilities.items()}


__all__ = ["simulate_operation_probabilities", "simulate_probabilities"]
