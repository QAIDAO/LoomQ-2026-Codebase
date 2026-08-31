"""OpenQASM 2.0 parser and noiseless statevector simulator for LoomQ."""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Gate = Tuple[str, List[int], List[float]]


@dataclass
class Circuit:
    num_qubits: int = 0
    num_clbits: int = 0
    gates: List[Gate] = field(default_factory=list)
    measure_all: bool = False


_GATE_ALIAS = {
    "cnot": "cx",
    "toffoli": "ccx",
    "cp": "cu1",
    "p": "u1",
    "u1": "u1",
}


def _strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if "//" in line:
            line = line.split("//", 1)[0]
        lines.append(line)
    return "\n".join(lines)


def _strip_classical_blocks(text: str) -> str:
    out = []
    i = 0
    lower = text.lower()
    while i < len(text):
        idx = lower.find("classical", i)
        if idx < 0:
            out.append(text[i:])
            break
        out.append(text[i:idx])
        brace = text.find("{", idx)
        if brace < 0:
            break
        depth = 0
        j = brace
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        i = j
        lower = text.lower()
    return "".join(out)


def parse_qasm(qasm_str: str) -> Circuit:
    text = _strip_classical_blocks(_strip_comments(qasm_str))
    circuit = Circuit()

    qreg_re = re.compile(r"qreg\s+(\w+)\s*\[(\d+)\]\s*;?", re.I)
    creg_re = re.compile(r"creg\s+(\w+)\s*\[(\d+)\]\s*;?", re.I)
    gate_re = re.compile(
        r"^([a-zA-Z_]\w*)\s*(?:\(([^)]*)\))?\s+(.+?)\s*;?\s*$"
    )
    measure_re = re.compile(
        r"measure\s+(\w+)\s*(?:\[(\d+)\])?\s*->\s*(\w+)\s*(?:\[(\d+)\])?\s*;?\s*$",
        re.I,
    )
    measure_all_re = re.compile(r"measure\s+(\w+)\s*->\s*(\w+)\s*;?\s*$", re.I)

    # Preserve multi-statement lines like "measure q -> c" before splitting on ';'
    normalized = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if measure_all_re.match(line):
            normalized.append(line)
            continue
        normalized.extend(part.strip() for part in line.split(";") if part.strip())
    chunks = normalized

    for line in chunks:
        if not line or line.upper().startswith("OPENQASM") or line.lower().startswith("include"):
            continue

        m = qreg_re.search(line)
        if m:
            circuit.num_qubits = max(circuit.num_qubits, int(m.group(2)))
            continue

        m = creg_re.search(line)
        if m:
            circuit.num_clbits = max(circuit.num_clbits, int(m.group(2)))
            continue

        m = measure_all_re.match(line)
        if m:
            circuit.measure_all = True
            continue

        m = measure_re.match(line)
        if m:
            continue

        m = gate_re.match(line)
        if not m:
            continue
        name = _GATE_ALIAS.get(m.group(1).lower(), m.group(1).lower())
        if name in {"if", "else", "classical", "barrier"}:
            continue
        params = []
        if m.group(2):
            for token in m.group(2).split(","):
                token = token.strip()
                if token.startswith("pi"):
                    token = token.replace("pi", str(math.pi))
                params.append(float(eval(token, {"__builtins__": {}}, {"pi": math.pi})))
        args = [part.strip() for part in m.group(3).split(",")]
        qubits = []
        for arg in args:
            idx = re.search(r"\[(\d+)\]", arg)
            if idx:
                qubits.append(int(idx.group(1)))
        circuit.gates.append((name, qubits, params))

    if circuit.num_clbits == 0:
        circuit.num_clbits = circuit.num_qubits
    return circuit


def _mat_mul(a: List[List[complex]], b: List[List[complex]]) -> List[List[complex]]:
    n, m, p = len(a), len(a[0]), len(b[0])
    out = [[0j] * p for _ in range(n)]
    for i in range(n):
        for k in range(m):
            if a[i][k] == 0:
                continue
            for j in range(p):
                out[i][j] += a[i][k] * b[k][j]
    return out


def _kron(a: List[List[complex]], b: List[List[complex]]) -> List[List[complex]]:
    rows, cols = len(a) * len(b), len(a[0]) * len(b[0])
    out = [[0j] * cols for _ in range(rows)]
    for i in range(len(a)):
        for j in range(len(a[0])):
            if a[i][j] == 0:
                continue
            for p in range(len(b)):
                for q in range(len(b[0])):
                    out[i * len(b) + p][j * len(b[0]) + q] = a[i][j] * b[p][q]
    return out


def _eye(n: int) -> List[List[complex]]:
    return [[1j if i == j else 0j for j in range(n)] for i in range(n)]


def _single(gate: str, theta: float = 0.0) -> List[List[complex]]:
    if gate == "h":
        s = 1 / math.sqrt(2)
        return [[s, s], [s, -s]]
    if gate == "x":
        return [[0, 1], [1, 0]]
    if gate == "s":
        return [[1, 0], [0, 1j]]
    if gate == "sdg":
        return [[1, 0], [0, -1j]]
    if gate == "t":
        return [[1, 0], [0, complex(math.cos(math.pi / 4), math.sin(math.pi / 4))]]
    if gate == "tdg":
        return [[1, 0], [0, complex(math.cos(math.pi / 4), -math.sin(math.pi / 4))]]
    if gate == "rz":
        return [[complex(math.cos(theta / 2), -math.sin(theta / 2)), 0], [0, complex(math.cos(theta / 2), math.sin(theta / 2))]]
    if gate == "ry":
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        return [[c, -s], [s, c]]
    if gate in {"u1", "p"}:
        return [[1, 0], [0, complex(math.cos(theta), math.sin(theta))]]
    raise ValueError(f"unsupported single-qubit gate: {gate}")


def _cx() -> List[List[complex]]:
    return [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 1, 0],
    ]


def _cu1(theta: float) -> List[List[complex]]:
    return [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, complex(math.cos(theta), math.sin(theta))],
    ]


def _ccx() -> List[List[complex]]:
    size = 8
    m = _eye(size)
    m[6][6], m[6][7] = 0, 1
    m[7][6], m[7][7] = 1, 0
    return m


def _expand_gate(num_qubits: int, targets: List[int], matrix: List[List[complex]]) -> List[List[complex]]:
    ops: List[List[List[complex]]] = []
    used = set(targets)
    dim = 1
    for q in range(num_qubits):
        if q in used:
            idx = targets.index(q)
            if idx == 0:
                ops.append(matrix)
                dim *= len(matrix)
            continue
        ops.append(_eye(2))
        dim *= 2
    if not ops:
        return matrix
    result = ops[0]
    for op in ops[1:]:
        result = _kron(result, op)
    return result


def _apply_matrix2(state: List[complex], qubit: int, matrix: List[List[complex]]) -> List[complex]:
    size = len(state)
    out = [0j] * size
    mask = 1 << qubit
    for i in range(size):
        if i & mask:
            continue
        j = i | mask
        a0, a1 = state[i], state[j]
        out[i] = matrix[0][0] * a0 + matrix[0][1] * a1
        out[j] = matrix[1][0] * a0 + matrix[1][1] * a1
    return out


def _apply(state: List[complex], num_qubits: int, gate: str, qubits: List[int], params: List[float]) -> List[complex]:
    del num_qubits
    if gate in {"h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "u1", "p"}:
        theta = params[0] if params else 0.0
        return _apply_matrix2(state, qubits[0], _single(gate, theta))

    size = len(state)
    out = [0j] * size
    if gate == "cx":
        c, t = qubits[0], qubits[1]
        for i in range(size):
            j = i ^ (1 << t) if (i >> c) & 1 else i
            out[j] = state[i]
        return out
    if gate == "cu1":
        c, t = qubits[0], qubits[1]
        phase = complex(math.cos(params[0]), math.sin(params[0]))
        for i in range(size):
            out[i] = state[i] * phase if ((i >> c) & 1) and ((i >> t) & 1) else state[i]
        return out
    if gate == "swap":
        a, b = qubits[0], qubits[1]
        for i in range(size):
            bit_a, bit_b = (i >> a) & 1, (i >> b) & 1
            j = i ^ (1 << a) ^ (1 << b) if bit_a != bit_b else i
            out[j] = state[i]
        return out
    if gate == "ccx":
        c1, c2, t = qubits[0], qubits[1], qubits[2]
        for i in range(size):
            j = i ^ (1 << t) if ((i >> c1) & 1) and ((i >> c2) & 1) else i
            out[j] = state[i]
        return out
    raise ValueError(f"unsupported gate: {gate}")


def simulate_counts(qasm_str: str, shots: int, seed: Optional[int] = None) -> Dict[str, int]:
    circuit = parse_qasm(qasm_str)
    if circuit.num_qubits == 0:
        raise ValueError("circuit has no qubits")
    size = 1 << circuit.num_qubits
    state = [0j] * size
    state[0] = 1.0

    for gate, qubits, params in circuit.gates:
        state = _apply(state, circuit.num_qubits, gate, qubits, params)

    probs = [abs(amp) ** 2 for amp in state]
    rng = random.Random(seed)
    counts: Dict[str, int] = {}
    for _ in range(shots):
        pick = rng.random()
        acc = 0.0
        idx = size - 1
        for i, p in enumerate(probs):
            acc += p
            if pick <= acc:
                idx = i
                break
        bits = format(idx, f"0{circuit.num_qubits}b")
        key = bits[::-1]  # little-endian: c[0] is rightmost
        counts[key] = counts.get(key, 0) + 1
    return counts


def ideal_probabilities(qasm_str: str) -> Dict[str, float]:
    circuit = parse_qasm(qasm_str)
    size = 1 << circuit.num_qubits
    state = [0j] * size
    state[0] = 1.0
    for gate, qubits, params in circuit.gates:
        state = _apply(state, circuit.num_qubits, gate, qubits, params)
    probs: Dict[str, float] = {}
    for idx, amp in enumerate(state):
        p = abs(amp) ** 2
        if p > 1e-12:
            bits = format(idx, f"0{circuit.num_qubits}b")[::-1]
            probs[bits] = p
    return probs
