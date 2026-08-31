"""Independent standard-library statevector reference for LoomQ L1 tests.

This module is independent of vendor execution paths. It uses the validated L1
circuit model, but no target emitter, runner, or vendor SDK. L2 may reuse it for
bounded local validation of targets that can be recovered from user text.
Qubit zero is the least-significant statevector bit and returned classical keys
are rendered as c[n-1]...c[0], matching the LoomQ ``bit_order == "little"``
contract.
"""

from __future__ import annotations

import cmath
import math
from typing import Dict, List, Sequence, Tuple, Union

try:
    from .loomq_l1 import BitRef, Circuit, Gate, parse_qasm
except ImportError:
    from loomq_l1 import BitRef, Circuit, Gate, parse_qasm


Number = complex
CircuitSource = Union[Circuit, str]
_TOLERANCE = 1e-12


def _as_circuit(source: CircuitSource) -> Circuit:
    if isinstance(source, Circuit):
        return source
    if isinstance(source, str):
        return parse_qasm(source)
    raise TypeError("reference input must be a Circuit or OpenQASM string")


def _qubit_offsets(circuit: Circuit) -> Dict[str, int]:
    offsets: Dict[str, int] = {}
    offset = 0
    for name, size in circuit.qregs:
        offsets[name] = offset
        offset += size
    return offsets


def _classical_offsets(circuit: Circuit) -> Dict[str, int]:
    offsets: Dict[str, int] = {}
    offset = 0
    for name, size in circuit.cregs:
        offsets[name] = offset
        offset += size
    return offsets


def _absolute(bit: BitRef, offsets: Dict[str, int]) -> int:
    return offsets[bit.register] + bit.index


def _apply_single(
    state: List[Number], qubit: int, matrix: Tuple[Tuple[Number, Number], Tuple[Number, Number]]
) -> None:
    mask = 1 << qubit
    for zero in range(len(state)):
        if zero & mask:
            continue
        one = zero | mask
        a0, a1 = state[zero], state[one]
        state[zero] = matrix[0][0] * a0 + matrix[0][1] * a1
        state[one] = matrix[1][0] * a0 + matrix[1][1] * a1


def _apply_gate(state: List[Number], gate: Gate, offsets: Dict[str, int]) -> None:
    qubits = tuple(_absolute(bit, offsets) for bit in gate.qubits)
    name = gate.name

    if name == "h":
        scale = 1.0 / math.sqrt(2.0)
        _apply_single(state, qubits[0], ((scale, scale), (scale, -scale)))
    elif name == "x":
        _apply_single(state, qubits[0], ((0.0, 1.0), (1.0, 0.0)))
    elif name == "s":
        _apply_single(state, qubits[0], ((1.0, 0.0), (0.0, 1.0j)))
    elif name == "sdg":
        _apply_single(state, qubits[0], ((1.0, 0.0), (0.0, -1.0j)))
    elif name == "t":
        phase = cmath.exp(1.0j * math.pi / 4.0)
        _apply_single(state, qubits[0], ((1.0, 0.0), (0.0, phase)))
    elif name == "tdg":
        phase = cmath.exp(-1.0j * math.pi / 4.0)
        _apply_single(state, qubits[0], ((1.0, 0.0), (0.0, phase)))
    elif name == "rz":
        half = gate.params[0] / 2.0
        _apply_single(
            state,
            qubits[0],
            ((cmath.exp(-1.0j * half), 0.0), (0.0, cmath.exp(1.0j * half))),
        )
    elif name == "ry":
        half = gate.params[0] / 2.0
        cosine, sine = math.cos(half), math.sin(half)
        _apply_single(state, qubits[0], ((cosine, -sine), (sine, cosine)))
    elif name == "cx":
        control, target = qubits
        control_mask, target_mask = 1 << control, 1 << target
        for basis in range(len(state)):
            if basis & control_mask and not basis & target_mask:
                flipped = basis | target_mask
                state[basis], state[flipped] = state[flipped], state[basis]
    elif name == "cu1":
        control, target = qubits
        mask = (1 << control) | (1 << target)
        phase = cmath.exp(1.0j * gate.params[0])
        for basis in range(len(state)):
            if basis & mask == mask:
                state[basis] *= phase
    elif name == "swap":
        first, second = qubits
        first_mask, second_mask = 1 << first, 1 << second
        for basis in range(len(state)):
            first_set = bool(basis & first_mask)
            second_set = bool(basis & second_mask)
            if first_set and not second_set:
                swapped = basis ^ first_mask ^ second_mask
                state[basis], state[swapped] = state[swapped], state[basis]
    elif name == "ccx":
        first, second, target = qubits
        controls = (1 << first) | (1 << second)
        target_mask = 1 << target
        for basis in range(len(state)):
            if basis & controls == controls and not basis & target_mask:
                flipped = basis | target_mask
                state[basis], state[flipped] = state[flipped], state[basis]
    else:  # pragma: no cover - parse_qasm rejects this before simulation.
        raise ValueError("unsupported reference gate: %s" % name)


def statevector(source: CircuitSource) -> Tuple[Number, ...]:
    """Return the exact final statevector before terminal measurements."""

    circuit = _as_circuit(source)
    state: List[Number] = [0.0j] * (1 << circuit.qubit_count)
    state[0] = 1.0 + 0.0j
    offsets = _qubit_offsets(circuit)
    for gate in circuit.gates:
        _apply_gate(state, gate, offsets)
    norm = sum(abs(amplitude) ** 2 for amplitude in state)
    if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1e-10):
        raise ArithmeticError("reference statevector lost normalization: %.17g" % norm)
    return tuple(state)


def distribution(source: CircuitSource) -> Dict[str, float]:
    """Return the terminal classical distribution for a supported L1 circuit."""

    circuit = _as_circuit(source)
    if circuit.classical_count <= 0:
        raise ValueError("reference distribution requires a classical register")
    qoffsets = _qubit_offsets(circuit)
    coffsets = _classical_offsets(circuit)
    # A later terminal assignment to the same classical bit replaces the
    # earlier one, as it does in OpenQASM's imperative measurement semantics.
    assigned = {
        _absolute(item.classical, coffsets): _absolute(item.qubit, qoffsets)
        for item in circuit.measurements
    }
    mapping = [(qubit, classical) for classical, qubit in assigned.items()]
    probabilities: Dict[str, float] = {}
    for basis, amplitude in enumerate(statevector(circuit)):
        probability = abs(amplitude) ** 2
        if probability <= _TOLERANCE:
            continue
        classical = 0
        for qubit, bit in mapping:
            if basis & (1 << qubit):
                classical |= 1 << bit
        key = format(classical, "0%db" % circuit.classical_count)
        probabilities[key] = probabilities.get(key, 0.0) + probability
    total = sum(probabilities.values())
    if total <= 0.0:
        raise ArithmeticError("reference distribution is empty")
    return {key: value / total for key, value in sorted(probabilities.items())}


def hellinger_fidelity(observed: Dict[str, float], expected: Dict[str, float]) -> float:
    """Use the evaluator's Hellinger-derived fidelity definition."""

    states = set(observed) | set(expected)
    distance = math.sqrt(
        sum(
            (math.sqrt(observed.get(key, 0.0)) - math.sqrt(expected.get(key, 0.0)))
            ** 2
            for key in states
        )
    ) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - distance))


def equivalent_up_to_global_phase(
    first: Sequence[Number], second: Sequence[Number], tolerance: float = 1e-10
) -> bool:
    """Compare statevectors while ignoring a physically irrelevant global phase."""

    if len(first) != len(second) or tolerance <= 0.0:
        return False
    pivot = None
    for left, right in zip(first, second):
        if abs(left) > tolerance or abs(right) > tolerance:
            if abs(left) <= tolerance or abs(right) <= tolerance:
                return False
            pivot = left / right
            pivot /= abs(pivot)
            break
    if pivot is None:
        return True
    return all(abs(left - pivot * right) <= tolerance for left, right in zip(first, second))
