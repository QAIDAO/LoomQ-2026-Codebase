"""Dependency-free state-vector reference simulator for the published gate set."""

from __future__ import annotations

import cmath
import hashlib
import math
from datetime import datetime, timezone
from typing import Iterable

from .ir import Circuit, Gate, Measure


MAX_QUBITS = 20
BACKEND_IDS = {
    "spinq": "spinq_taurus_simulator",
    "originq": "originq_local_simulator",
    "braket": "braket_local_simulator",
}


def _single(state: list[complex], qubit: int, matrix: tuple[tuple[complex, complex], tuple[complex, complex]]) -> None:
    mask = 1 << qubit
    for base in range(len(state)):
        if base & mask:
            continue
        other = base | mask
        low, high = state[base], state[other]
        state[base] = matrix[0][0] * low + matrix[0][1] * high
        state[other] = matrix[1][0] * low + matrix[1][1] * high


def _apply_gate(state: list[complex], gate: Gate, circuit: Circuit) -> None:
    indices = tuple(circuit.qubit_index(ref) for ref in gate.qubits)
    if gate.name == "h":
        scale = 1 / math.sqrt(2)
        _single(state, indices[0], ((scale, scale), (scale, -scale)))
    elif gate.name == "x":
        _single(state, indices[0], ((0, 1), (1, 0)))
    elif gate.name == "s":
        _single(state, indices[0], ((1, 0), (0, 1j)))
    elif gate.name == "sdg":
        _single(state, indices[0], ((1, 0), (0, -1j)))
    elif gate.name == "t":
        _single(state, indices[0], ((1, 0), (0, cmath.exp(1j * math.pi / 4))))
    elif gate.name == "tdg":
        _single(state, indices[0], ((1, 0), (0, cmath.exp(-1j * math.pi / 4))))
    elif gate.name == "rz":
        theta = gate.parameters[0]
        _single(state, indices[0], ((cmath.exp(-0.5j * theta), 0), (0, cmath.exp(0.5j * theta))))
    elif gate.name == "ry":
        theta = gate.parameters[0]
        cosine, sine = math.cos(theta / 2), math.sin(theta / 2)
        _single(state, indices[0], ((cosine, -sine), (sine, cosine)))
    elif gate.name == "cx":
        control, target = indices
        target_mask = 1 << target
        for basis in range(len(state)):
            if (basis >> control) & 1 and not basis & target_mask:
                other = basis | target_mask
                state[basis], state[other] = state[other], state[basis]
    elif gate.name == "cu1":
        control, target = indices
        phase = cmath.exp(1j * gate.parameters[0])
        for basis in range(len(state)):
            if (basis >> control) & 1 and (basis >> target) & 1:
                state[basis] *= phase
    elif gate.name == "swap":
        left, right = indices
        left_mask, right_mask = 1 << left, 1 << right
        for basis in range(len(state)):
            if not basis & left_mask and basis & right_mask:
                other = (basis | left_mask) & ~right_mask
                state[basis], state[other] = state[other], state[basis]
    elif gate.name == "ccx":
        first, second, target = indices
        target_mask = 1 << target
        for basis in range(len(state)):
            if (basis >> first) & 1 and (basis >> second) & 1 and not basis & target_mask:
                other = basis | target_mask
                state[basis], state[other] = state[other], state[basis]
    else:  # pragma: no cover - the parser prevents this path
        raise ValueError(f"unsupported gate: {gate.name}")


def statevector(circuit: Circuit) -> list[complex]:
    if circuit.total_qubits > MAX_QUBITS:
        raise ValueError(f"local reference simulator supports at most {MAX_QUBITS} qubits")
    state = [0j] * (1 << circuit.total_qubits)
    state[0] = 1 + 0j
    measurement_seen = False
    for operation in circuit.operations:
        if isinstance(operation, Measure):
            measurement_seen = True
        else:
            if measurement_seen:
                raise ValueError("local L1 simulator requires measurements to be terminal")
            _apply_gate(state, operation, circuit)
    norm = sum(abs(amplitude) ** 2 for amplitude in state)
    if not math.isclose(norm, 1.0, rel_tol=1e-10, abs_tol=1e-10):
        raise ArithmeticError(f"state normalization invariant failed: {norm}")
    return state


def exact_probabilities(circuit: Circuit) -> dict[str, float]:
    measurements = [operation for operation in circuit.operations if isinstance(operation, Measure)]
    if not measurements or circuit.total_cbits <= 0:
        raise ValueError("circuit must measure at least one qubit into a declared creg")
    state = statevector(circuit)
    probabilities: dict[str, float] = {}
    for basis, amplitude in enumerate(state):
        probability = abs(amplitude) ** 2
        if probability < 1e-15:
            continue
        cbits = [0] * circuit.total_cbits
        for measurement in measurements:
            qindex = circuit.qubit_index(measurement.qubit)
            cindex = circuit.cbit_index(measurement.cbit)
            cbits[cindex] = (basis >> qindex) & 1
        key = "".join(str(bit) for bit in reversed(cbits))
        probabilities[key] = probabilities.get(key, 0.0) + probability
    total = sum(probabilities.values())
    return {key: value / total for key, value in sorted(probabilities.items())}


def _apportion(probabilities: dict[str, float], shots: int) -> dict[str, int]:
    raw = {key: value * shots for key, value in probabilities.items()}
    counts = {key: int(math.floor(value)) for key, value in raw.items()}
    remaining = shots - sum(counts.values())
    ranking: Iterable[str] = sorted(raw, key=lambda key: (-(raw[key] - counts[key]), key))
    for key in list(ranking)[:remaining]:
        counts[key] += 1
    return {key: value for key, value in counts.items() if value}


def circuit_depth(circuit: Circuit) -> int:
    layers = [0] * circuit.total_qubits
    for operation in circuit.operations:
        if not isinstance(operation, Gate):
            continue
        indices = [circuit.qubit_index(ref) for ref in operation.qubits]
        layer = max(layers[index] for index in indices) + 1
        for index in indices:
            layers[index] = layer
    return max(layers, default=0)


def execute(circuit: Circuit, target: str, shots: int, target_ir: str) -> dict:
    if isinstance(shots, bool) or not isinstance(shots, int) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    if target not in BACKEND_IDS:
        raise ValueError(f"unsupported target: {target!r}")
    probabilities = exact_probabilities(circuit)
    digest = hashlib.sha256((target_ir + f"\0{shots}").encode("utf-8")).hexdigest()[:20]
    gate_count = sum(isinstance(operation, Gate) for operation in circuit.operations)
    return {
        "backend": BACKEND_IDS[target],
        "job_id": f"loomq-local-{digest}",
        "shots": shots,
        "counts": _apportion(probabilities, shots),
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "meta": {
            "transpiled_gates": gate_count,
            "depth": circuit_depth(circuit),
            "engine": "loomq-statevector-v1",
            "deterministic_apportionment": True,
            "target_ir_sha256": hashlib.sha256(target_ir.encode("utf-8")).hexdigest(),
        },
    }
