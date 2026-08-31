"""Small deterministic state-vector simulator for the LoomQ L1 gate subset."""

from __future__ import annotations

import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import math
import cmath
import random
from typing import Dict, Iterable

from .qasm import GateOperation, MeasureOperation, Program, parse_openqasm2


BACKEND_IDS = {
    "spinq": "spinq_taurus_simulator",
    "originq": "originq_local_simulator",
    "braket": "braket_local_simulator",
}


def run_local(qasm_str: str, target: str, shots: int) -> Dict[str, object]:
    """Execute the L1 subset locally and return the competition result schema."""

    if target not in BACKEND_IDS:
        raise ValueError(f"Unsupported target: {target}")
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    program = parse_openqasm2(qasm_str)
    state = _simulate(program)
    counts = _sample_counts(state, program, shots, qasm_str, target)
    return {
        "backend": BACKEND_IDS[target],
        "job_id": _job_id(qasm_str, target, shots),
        "shots": shots,
        "counts": dict(sorted(counts.items())),
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "meta": {"transpiled_gates": _gate_count(program), "depth": _depth(program)},
    }


def ideal_distribution(qasm_str: str) -> dict[str, float]:
    """Return the exact measured distribution without shot sampling."""

    program = parse_openqasm2(qasm_str)
    state = _simulate(program)
    distribution: dict[str, float] = {}
    for basis_index, amplitude in enumerate(state):
        probability = max(0.0, abs(amplitude) ** 2)
        if probability <= 1e-15:
            continue
        bitstring = _measurement_bitstring(basis_index, program)
        distribution[bitstring] = distribution.get(bitstring, 0.0) + probability
    total = sum(distribution.values())
    if total <= 0:
        raise RuntimeError("simulated circuit has no measurable probability mass")
    return {
        state: probability / total
        for state, probability in sorted(distribution.items())
    }


def _simulate(program: Program) -> list[complex]:
    qubits = program.quantum_register.size
    state = [0j] * (1 << qubits)
    state[0] = 1 + 0j
    for operation in program.operations:
        if isinstance(operation, GateOperation):
            _apply_gate(state, operation)
    return state


def _apply_gate(state: list[complex], operation: GateOperation) -> None:
    qubits = tuple(_operand_index(operand) for operand in operation.operands)
    parameter = _parameter_value(operation.parameter) if operation.parameter is not None else None
    if operation.name == "h":
        scale = 1 / math.sqrt(2)
        _apply_single(state, qubits[0], ((scale, scale), (scale, -scale)))
    elif operation.name == "x":
        _apply_single(state, qubits[0], ((0, 1), (1, 0)))
    elif operation.name == "s":
        _apply_single(state, qubits[0], ((1, 0), (0, 1j)))
    elif operation.name == "sdg":
        _apply_single(state, qubits[0], ((1, 0), (0, -1j)))
    elif operation.name == "t":
        _apply_single(state, qubits[0], ((1, 0), (0, cmath.exp(1j * math.pi / 4))))
    elif operation.name == "tdg":
        _apply_single(state, qubits[0], ((1, 0), (0, cmath.exp(-1j * math.pi / 4))))
    elif operation.name == "rz":
        assert parameter is not None
        _apply_single(
            state,
            qubits[0],
            ((cmath.exp(-0.5j * parameter), 0), (0, cmath.exp(0.5j * parameter))),
        )
    elif operation.name == "ry":
        assert parameter is not None
        cosine, sine = math.cos(parameter / 2), math.sin(parameter / 2)
        _apply_single(state, qubits[0], ((cosine, -sine), (sine, cosine)))
    elif operation.name == "cx":
        _apply_controlled_x(state, qubits[0], qubits[1])
    elif operation.name == "cu1":
        assert parameter is not None
        _apply_controlled_phase(state, qubits[0], qubits[1], parameter)
    elif operation.name == "swap":
        _apply_swap(state, qubits[0], qubits[1])
    elif operation.name == "ccx":
        _apply_toffoli(state, qubits[0], qubits[1], qubits[2])
    else:
        raise ValueError(f"Unsupported gate: {operation.name}")


def _apply_single(
    state: list[complex], qubit: int, matrix: tuple[tuple[complex, complex], tuple[complex, complex]]
) -> None:
    mask = 1 << qubit
    for index in range(len(state)):
        if index & mask:
            continue
        paired = index | mask
        zero, one = state[index], state[paired]
        state[index] = matrix[0][0] * zero + matrix[0][1] * one
        state[paired] = matrix[1][0] * zero + matrix[1][1] * one


def _apply_controlled_x(state: list[complex], control: int, target: int) -> None:
    control_mask, target_mask = 1 << control, 1 << target
    for index in range(len(state)):
        if index & control_mask and not index & target_mask:
            paired = index | target_mask
            state[index], state[paired] = state[paired], state[index]


def _apply_controlled_phase(state: list[complex], control: int, target: int, angle: float) -> None:
    mask = (1 << control) | (1 << target)
    phase = cmath.exp(1j * angle)
    for index in range(len(state)):
        if index & mask == mask:
            state[index] *= phase


def _apply_swap(state: list[complex], first: int, second: int) -> None:
    if first == second:
        return
    first_mask, second_mask = 1 << first, 1 << second
    for index in range(len(state)):
        first_bit, second_bit = bool(index & first_mask), bool(index & second_mask)
        if not first_bit and second_bit:
            paired = index ^ first_mask ^ second_mask
            state[index], state[paired] = state[paired], state[index]


def _apply_toffoli(state: list[complex], first: int, second: int, target: int) -> None:
    controls = (1 << first) | (1 << second)
    target_mask = 1 << target
    for index in range(len(state)):
        if index & controls == controls and not index & target_mask:
            paired = index | target_mask
            state[index], state[paired] = state[paired], state[index]


def _sample_counts(
    state: Iterable[complex], program: Program, shots: int, qasm_str: str, target: str
) -> Counter[str]:
    probabilities = [max(0.0, abs(amplitude) ** 2) for amplitude in state]
    total = sum(probabilities)
    if not math.isclose(total, 1.0, abs_tol=1e-8):
        probabilities = [probability / total for probability in probabilities]
    cumulative: list[float] = []
    running = 0.0
    for probability in probabilities:
        running += probability
        cumulative.append(running)
    cumulative[-1] = 1.0
    # Normalized local execution must not change observable counts by target.
    seed_bytes = hashlib.sha256(f"{qasm_str}\0{shots}".encode("utf-8")).digest()
    generator = random.Random(int.from_bytes(seed_bytes[:8], "big"))
    counts: Counter[str] = Counter()
    for _ in range(shots):
        value = generator.random()
        basis_index = next(index for index, cutoff in enumerate(cumulative) if value <= cutoff)
        counts[_measurement_bitstring(basis_index, program)] += 1
    return counts


def _measurement_bitstring(basis_index: int, program: Program) -> str:
    classical = [0] * program.classical_register.size
    for operation in program.operations:
        if not isinstance(operation, MeasureOperation):
            continue
        if operation.source == program.quantum_register.name:
            for index in range(program.quantum_register.size):
                classical[index] = (basis_index >> index) & 1
        else:
            quantum_index = _operand_index(operation.source)
            classical_index = _operand_index(operation.destination)
            classical[classical_index] = (basis_index >> quantum_index) & 1
    return "".join(str(classical[index]) for index in reversed(range(len(classical))))


def _operand_index(operand: str) -> int:
    return int(operand[operand.index("[") + 1 : operand.index("]")])


def _parameter_value(expression: str) -> float:
    try:
        node = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid parameter expression: {expression}") from exc
    return float(_evaluate_expression(node.body))


def _evaluate_expression(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id == "pi":
        return math.pi
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate_expression(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left, right = _evaluate_expression(node.left), _evaluate_expression(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right
    raise ValueError("Only numeric expressions using pi, +, -, * and / are supported")


def _job_id(qasm_str: str, target: str, shots: int) -> str:
    digest = hashlib.sha256(f"{qasm_str}\0{target}\0{shots}".encode("utf-8")).hexdigest()
    return f"local-{target}-{digest[:16]}"


def _gate_count(program: Program) -> int:
    return sum(isinstance(operation, GateOperation) for operation in program.operations)


def _depth(program: Program) -> int:
    depths = [0] * program.quantum_register.size
    for operation in program.operations:
        if not isinstance(operation, GateOperation):
            continue
        operands = [_operand_index(operand) for operand in operation.operands]
        layer = max(depths[index] for index in operands) + 1
        for index in operands:
            depths[index] = layer
    return max(depths, default=0)
