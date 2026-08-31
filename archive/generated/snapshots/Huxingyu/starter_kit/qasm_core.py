"""Small dependency-free OpenQASM 2.0 parser and state-vector simulator.

This is intentionally limited to the LoomQ L1 gate whitelist.  It provides a
deterministic local reference implementation for adapter development; it is
not a replacement for the organizer's private evaluator or real hardware SDKs.
"""

from __future__ import annotations

import ast
import cmath
import hashlib
import math
import random
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


GATE_NAMES = {
    "h", "x", "s", "sdg", "t", "tdg", "rz", "ry",
    "cx", "cnot", "cu1", "cp", "swap", "ccx", "toffoli", "barrier",
}


@dataclass(frozen=True)
class Operation:
    name: str
    qubits: Tuple[int, ...] = ()
    params: Tuple[float, ...] = ()
    cbits: Tuple[int, ...] = ()


@dataclass(frozen=True)
class Circuit:
    qubits: int
    cbits: int
    operations: Tuple[Operation, ...]


def _angle(value: str) -> float:
    """Evaluate the small arithmetic expression subset used by QASM angles."""
    expression = value.strip().replace("^", "**")
    tree = ast.parse(expression, mode="eval").body

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id.lower() in {"pi", "tau"}:
            return math.pi if node.id.lower() == "pi" else math.tau
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            result = visit(node.operand)
            return result if isinstance(node.op, ast.UAdd) else -result
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if right == 0:
                raise ValueError("angle expression divides by zero")
            return left / right
        raise ValueError(f"unsupported angle expression: {value!r}")

    result = visit(tree)
    if not math.isfinite(result):
        raise ValueError("angle must be finite")
    return result


_REF_RE = re.compile(r"^([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$")


def _split_args(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_qasm(qasm: str) -> Circuit:
    if not isinstance(qasm, str) or not qasm.strip():
        raise ValueError("qasm must be a non-empty string")
    text = re.sub(r"/\*.*?\*/", "", qasm, flags=re.DOTALL)
    text = "\n".join(line.split("//", 1)[0] for line in text.splitlines())

    qregs: Dict[str, Tuple[int, int]] = {}
    cregs: Dict[str, Tuple[int, int]] = {}
    qtotal = ctotal = 0
    statements = [item.strip() for item in text.split(";") if item.strip()]
    operations: List[Operation] = []
    for statement in statements:
        lowered = statement.lower().strip()
        if lowered.startswith("openqasm ") or lowered.startswith("include "):
            continue
        qmatch = re.fullmatch(r"qreg\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]", statement, re.I)
        if qmatch:
            name, size = qmatch.group(1), int(qmatch.group(2))
            if size <= 0 or name in qregs:
                raise ValueError(f"invalid or duplicate qreg: {statement}")
            qregs[name] = (qtotal, size)
            qtotal += size
            continue
        cmatch = re.fullmatch(r"creg\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]", statement, re.I)
        if cmatch:
            name, size = cmatch.group(1), int(cmatch.group(2))
            if size <= 0 or name in cregs:
                raise ValueError(f"invalid or duplicate creg: {statement}")
            cregs[name] = (ctotal, size)
            ctotal += size
            continue
        if lowered.startswith("barrier"):
            continue

        if lowered.startswith("measure"):
            match = re.fullmatch(r"measure\s+(.+?)\s*->\s*(.+)", statement, re.I)
            if not match:
                raise ValueError(f"invalid measurement: {statement}")
            left, right = match.group(1).strip(), match.group(2).strip()
            operations.extend(_parse_measure(left, right, qregs, cregs))
            continue

        match = re.fullmatch(r"([A-Za-z_]\w*)\s*(?:\((.*?)\))?\s+(.+)", statement)
        if not match:
            raise ValueError(f"unsupported QASM statement: {statement}")
        name = match.group(1).lower()
        if name not in GATE_NAMES or name == "barrier":
            raise ValueError(f"unsupported gate: {name}")
        args = _split_args(match.group(3))
        raw_params = _split_args(match.group(2) or "")
        params = tuple(_angle(item) for item in raw_params)
        canonical = {"cnot": "cx", "cp": "cu1", "toffoli": "ccx"}.get(name, name)
        expected = {"h": 1, "x": 1, "s": 1, "sdg": 1, "t": 1, "tdg": 1,
                    "rz": 1, "ry": 1, "cx": 2, "cu1": 2, "swap": 2, "ccx": 3}[canonical]
        expected_params = 1 if canonical in {"rz", "ry", "cu1"} else 0
        if len(args) != expected or len(params) != expected_params:
            raise ValueError(f"wrong arity for {name}: {statement}")
        for qubits in _expand_gate_args(args, qregs):
            if len(set(qubits)) != len(qubits):
                raise ValueError(f"gate operands must refer to distinct qubits: {statement}")
            operations.append(Operation(canonical, qubits, params))

    if qtotal <= 0:
        raise ValueError("QASM declares no qreg")
    if ctotal <= 0:
        raise ValueError("QASM declares no creg")
    return Circuit(qtotal, ctotal, tuple(operations))


def _parse_indexed_ref(value: str, regs: Dict[str, Tuple[int, int]]) -> int:
    match = _REF_RE.fullmatch(value.strip())
    if not match or match.group(1) not in regs:
        raise ValueError(f"expected indexed register reference: {value}")
    offset, size = regs[match.group(1)]
    index = int(match.group(2))
    if index >= size:
        raise ValueError(f"register index out of range: {value}")
    return offset + index


def _expand_gate_args(
    values: Sequence[str], regs: Dict[str, Tuple[int, int]]
) -> List[Tuple[int, ...]]:
    """Expand OpenQASM 2 register-wide gate applications element by element."""
    operands: List[Tuple[Tuple[int, ...], bool]] = []
    register_sizes = set()
    for value in values:
        reference = value.strip()
        if reference in regs:
            offset, size = regs[reference]
            operands.append((tuple(range(offset, offset + size)), True))
            register_sizes.add(size)
        else:
            operands.append(((_parse_indexed_ref(reference, regs),), False))

    if not register_sizes:
        return [tuple(indices[0] for indices, _ in operands)]
    if len(register_sizes) != 1:
        raise ValueError("register-wide gate operands must have equal sizes")
    width = register_sizes.pop()
    return [
        tuple(indices[index] if is_register else indices[0] for indices, is_register in operands)
        for index in range(width)
    ]


def _parse_measure(left: str, right: str, qregs, cregs) -> Iterable[Operation]:
    left_match = _REF_RE.fullmatch(left)
    right_match = _REF_RE.fullmatch(right)
    if left_match and right_match:
        return [Operation("measure", (_parse_indexed_ref(left, qregs),), (),
                          (_parse_indexed_ref(right, cregs),))]
    if left not in qregs or right not in cregs:
        raise ValueError(f"invalid whole-register measurement: {left} -> {right}")
    qoffset, qsize = qregs[left]
    coffset, csize = cregs[right]
    if qsize != csize:
        raise ValueError("whole-register measurement requires equal register sizes")
    return [Operation("measure", (qoffset + index,), (), (coffset + index,)) for index in range(qsize)]


def _single_matrix(name: str, theta: float = 0.0):
    if name == "h":
        scale = 1.0 / math.sqrt(2.0)
        return ((scale, scale), (scale, -scale))
    if name == "x":
        return ((0j, 1 + 0j), (1 + 0j, 0j))
    if name == "s":
        return ((1 + 0j, 0j), (0j, 1j))
    if name == "sdg":
        return ((1 + 0j, 0j), (0j, -1j))
    if name == "t":
        return ((1 + 0j, 0j), (0j, cmath.exp(1j * math.pi / 4)))
    if name == "tdg":
        return ((1 + 0j, 0j), (0j, cmath.exp(-1j * math.pi / 4)))
    if name == "rz":
        return ((cmath.exp(-0.5j * theta), 0j), (0j, cmath.exp(0.5j * theta)))
    if name == "ry":
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        return ((c, -s), (s, c))
    raise ValueError(f"not a single-qubit gate: {name}")


def _apply_single(state, qubit, matrix):
    mask = 1 << qubit
    for base in range(len(state)):
        if base & mask:
            continue
        other = base | mask
        a0, a1 = state[base], state[other]
        state[base] = matrix[0][0] * a0 + matrix[0][1] * a1
        state[other] = matrix[1][0] * a0 + matrix[1][1] * a1


def _apply_cx(state, control, target):
    cmask, tmask = 1 << control, 1 << target
    for index in range(len(state)):
        if index & cmask and not index & tmask:
            other = index | tmask
            state[index], state[other] = state[other], state[index]


def _apply_swap(state, first, second):
    if first == second:
        return
    amask, bmask = 1 << first, 1 << second
    for index in range(len(state)):
        if bool(index & amask) != bool(index & bmask):
            other = index ^ amask ^ bmask
            if index < other:
                state[index], state[other] = state[other], state[index]


def _apply_operation(state, operation: Operation):
    name = operation.name
    if name in {"h", "x", "s", "sdg", "t", "tdg", "rz", "ry"}:
        _apply_single(state, operation.qubits[0], _single_matrix(name, operation.params[0] if operation.params else 0.0))
    elif name == "cx":
        _apply_cx(state, *operation.qubits)
    elif name == "cu1":
        phase = cmath.exp(1j * operation.params[0])
        control, target = operation.qubits
        mask = (1 << control) | (1 << target)
        for index in range(len(state)):
            if index & mask == mask:
                state[index] *= phase
    elif name == "swap":
        _apply_swap(state, *operation.qubits)
    elif name == "ccx":
        first, second, target = operation.qubits
        cmask, tmask = (1 << first) | (1 << second), 1 << target
        for index in range(len(state)):
            if index & cmask == cmask and not index & tmask:
                other = index | tmask
                state[index], state[other] = state[other], state[index]
    elif name != "measure":
        raise ValueError(f"unsupported operation: {name}")


def _format_angle(value: float) -> str:
    return f"{value:.12g}"


def render_qasm2(circuit: Circuit) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{circuit.qubits}];", f"creg c[{circuit.cbits}];"]
    for operation in circuit.operations:
        if operation.name == "measure":
            lines.append(f"measure q[{operation.qubits[0]}] -> c[{operation.cbits[0]}];")
            continue
        params = f"({_format_angle(operation.params[0])})" if operation.params else ""
        args = ", ".join(f"q[{index}]" for index in operation.qubits)
        lines.append(f"{operation.name}{params} {args};")
    return "\n".join(lines) + "\n"


def render_braket(circuit: Circuit) -> str:
    lines = ["OPENQASM 3.0;", 'include "stdgates.inc";', f"qubit[{circuit.qubits}] q;", f"bit[{circuit.cbits}] c;"]
    for operation in circuit.operations:
        if operation.name == "measure":
            lines.append(f"c[{operation.cbits[0]}] = measure q[{operation.qubits[0]}];")
            continue
        name = {"cx": "cnot", "cu1": "cp"}.get(operation.name, operation.name)
        params = f"({_format_angle(operation.params[0])})" if operation.params else ""
        args = ", ".join(f"q[{index}]" for index in operation.qubits)
        lines.append(f"{name}{params} {args};")
    return "\n".join(lines) + "\n"


def render_origin(circuit: Circuit) -> str:
    lines = [f"QINIT {circuit.qubits}", f"CREG {circuit.cbits}"]
    names = {"h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T", "tdg": "TDAG",
             "rz": "RZ", "ry": "RY", "cx": "CNOT", "cu1": "CU1", "swap": "SWAP", "ccx": "CCX"}
    for operation in circuit.operations:
        if operation.name == "measure":
            lines.append(f"MEASURE q[{operation.qubits[0]}], c[{operation.cbits[0]}]")
            continue
        name = names[operation.name]
        params = f"({_format_angle(operation.params[0])})" if operation.params else ""
        args = ", ".join(f"q[{index}]" for index in operation.qubits)
        lines.append(f"{name}{params} {args}")
    return "\n".join(lines) + "\n"


def _probabilities(circuit: Circuit) -> Dict[str, float]:
    state = [0j] * (1 << circuit.qubits)
    state[0] = 1 + 0j
    measured: Dict[int, int] = {}
    for operation in circuit.operations:
        if operation.name == "measure":
            measured[operation.cbits[0]] = operation.qubits[0]
        else:
            _apply_operation(state, operation)
    if not measured:
        measured = {index: index for index in range(min(circuit.cbits, circuit.qubits))}
    probabilities: Dict[str, float] = {}
    for basis, amplitude in enumerate(state):
        key_bits = ["0"] * circuit.cbits
        for cbit, qubit in measured.items():
            key_bits[cbit] = "1" if basis & (1 << qubit) else "0"
        key = "".join(reversed(key_bits))
        probabilities[key] = probabilities.get(key, 0.0) + abs(amplitude) ** 2
    total = sum(probabilities.values())
    return {key: value / total for key, value in probabilities.items() if value > 1e-15}


def _sample_shot(circuit: Circuit, rng: random.Random) -> str:
    state = [0j] * (1 << circuit.qubits)
    state[0] = 1 + 0j
    classical = [0] * circuit.cbits
    measured_qubits = set()
    for operation in circuit.operations:
        if operation.name != "measure":
            _apply_operation(state, operation)
            continue
        qubit, cbit = operation.qubits[0], operation.cbits[0]
        mask = 1 << qubit
        probability_one = sum(abs(amplitude) ** 2 for index, amplitude in enumerate(state) if index & mask)
        bit = 1 if rng.random() < probability_one else 0
        norm = math.sqrt(probability_one if bit else max(0.0, 1.0 - probability_one))
        if norm <= 1e-15:
            raise RuntimeError("measurement collapsed onto a zero-probability state")
        for index in range(len(state)):
            if bool(index & mask) != bool(bit):
                state[index] = 0j
            else:
                state[index] /= norm
        classical[cbit] = bit
        measured_qubits.add(qubit)
    if not measured_qubits:
        for qubit in range(min(circuit.qubits, circuit.cbits)):
            mask = 1 << qubit
            probability_one = sum(abs(amplitude) ** 2 for index, amplitude in enumerate(state) if index & mask)
            classical[qubit] = 1 if rng.random() < probability_one else 0
    return "".join(str(bit) for bit in reversed(classical))


def sample_counts(circuit: Circuit, shots: int, seed_material: str) -> Dict[str, int]:
    if shots <= 0:
        raise ValueError("shots must be positive")
    first_measure = next((index for index, operation in enumerate(circuit.operations)
                          if operation.name == "measure"), None)
    rng = random.Random(int(hashlib.sha256(seed_material.encode()).hexdigest(), 16))
    if first_measure is not None and any(operation.name != "measure" for operation in circuit.operations[first_measure + 1:]):
        counts: Dict[str, int] = {}
        for _ in range(shots):
            key = _sample_shot(circuit, rng)
            counts[key] = counts.get(key, 0) + 1
        return counts
    probabilities = _probabilities(circuit)
    items = sorted(probabilities.items())
    cumulative: List[Tuple[float, str]] = []
    running = 0.0
    for key, probability in items:
        running += probability
        cumulative.append((running, key))
    counts = {key: 0 for key in probabilities}
    for _ in range(shots):
        value = rng.random()
        for threshold, key in cumulative:
            if value < threshold:
                counts[key] += 1
                break
    return {key: value for key, value in counts.items() if value}
