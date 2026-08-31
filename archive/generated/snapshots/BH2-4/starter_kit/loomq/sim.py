"""无噪声状态向量模拟器：Circuit → 终态振幅 / 采样 counts。

约定：量子比特 0 是基态下标的最低位（LSB）。counts 键按 little 位序
（最右字符 = c[0]）输出，与评测契约一致。
"""

from __future__ import annotations

import cmath
import math
import random
from typing import Dict, List, Optional, Tuple

from .ir import Circuit, Op

_cos = math.cos
_sin = math.sin
_exp = cmath.exp
_pi = math.pi
_SQRT2_INV = 1.0 / math.sqrt(2.0)


def _rx(theta: float) -> List[List[complex]]:
    c, s = _cos(theta / 2), _sin(theta / 2)
    return [[c, -1j * s], [-1j * s, c]]


def _ry(theta: float) -> List[List[complex]]:
    c, s = _cos(theta / 2), _sin(theta / 2)
    return [[c, -s], [s, c]]


def _rz(theta: float) -> List[List[complex]]:
    return [[_exp(-1j * theta / 2), 0], [0, _exp(1j * theta / 2)]]


def _u2(phi: float, lam: float) -> List[List[complex]]:
    return [
        [ _SQRT2_INV, -_exp(1j * lam) * _SQRT2_INV],
        [_exp(1j * phi) * _SQRT2_INV, _exp(1j * (phi + lam)) * _SQRT2_INV],
    ]


def _u3(theta: float, phi: float, lam: float) -> List[List[complex]]:
    c, s = _cos(theta / 2), _sin(theta / 2)
    return [
        [c, -s * _exp(1j * lam)],
        [s * _exp(1j * phi), c * _exp(1j * (phi + lam))],
    ]


def _one_qubit_matrix(name: str, params: Tuple[float, ...]) -> List[List[complex]]:
    if name == "h":
        return [[_SQRT2_INV, _SQRT2_INV], [_SQRT2_INV, -_SQRT2_INV]]
    if name == "x":
        return [[0, 1], [1, 0]]
    if name == "y":
        return [[0, -1j], [1j, 0]]
    if name == "z":
        return [[1, 0], [0, -1]]
    if name == "s":
        return [[1, 0], [0, 1j]]
    if name == "sdg":
        return [[1, 0], [0, -1j]]
    if name == "t":
        return [[1, 0], [0, _exp(1j * _pi / 4)]]
    if name == "tdg":
        return [[1, 0], [0, _exp(-1j * _pi / 4)]]
    if name == "id":
        return [[1, 0], [0, 1]]
    if name == "sx":
        return [[0.5 + 0.5j, 0.5 - 0.5j], [0.5 - 0.5j, 0.5 + 0.5j]]
    if name == "rx":
        return _rx(params[0])
    if name == "ry":
        return _ry(params[0])
    if name == "rz":
        return _rz(params[0])
    if name in ("p", "u1"):
        return [[1, 0], [0, _exp(1j * params[0])]]
    if name == "u2":
        return _u2(params[0], params[1])
    if name in ("u3", "u"):
        return _u3(params[0], params[1], params[2])
    raise ValueError("模拟器不支持单比特门 %r" % name)


def _controlled(matrix: List[List[complex]], n_controls: int) -> List[List[complex]]:
    """受控门矩阵：qubits[0..k-1] 为控制位（低比特），U 作用于其余高位。"""
    dim_u = len(matrix)
    k = n_controls
    dim = dim_u << k
    out = [[0] * dim for _ in range(dim)]
    for j in range(dim):
        out[j][j] = 1
    ctrl_mask = (1 << k) - 1
    for ui in range(dim_u):
        for uj in range(dim_u):
            i = (ui << k) | ctrl_mask
            j = (uj << k) | ctrl_mask
            out[i][j] = matrix[ui][uj]
    return out


def _swap_matrix() -> List[List[complex]]:
    return [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]]


def _crz(theta: float) -> List[List[complex]]:
    return [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, _exp(-1j * theta / 2), 0],
        [0, 0, 0, _exp(1j * theta / 2)],
    ]


_ONE_QUBIT_NAMES = {
    "h", "x", "y", "z", "s", "sdg", "t", "tdg", "id", "sx",
    "rx", "ry", "rz", "p", "u1", "u2", "u3", "u",
}


def _op_matrix(op: Op) -> Tuple[List[int], List[List[complex]]]:
    """返回 (参与比特列表, 矩阵)。比特列表低位在前，与矩阵下标位对应。"""
    name, params, qubits = op.name, op.params, op.qubits
    if name in _ONE_QUBIT_NAMES:
        return list(qubits), _one_qubit_matrix(name, params)
    if name == "cx":
        return list(qubits), _controlled([[0, 1], [1, 0]], 1)
    if name == "cy":
        return list(qubits), _controlled([[0, -1j], [1j, 0]], 1)
    if name == "cz":
        return list(qubits), _controlled([[1, 0], [0, -1]], 1)
    if name == "ch":
        return list(qubits), _controlled(
            [[_SQRT2_INV, _SQRT2_INV], [_SQRT2_INV, -_SQRT2_INV]], 1)
    if name == "ccx":
        return list(qubits), _controlled([[0, 1], [1, 0]], 2)
    if name == "cswap":
        return list(qubits), _controlled(_swap_matrix(), 1)
    if name in ("cu1", "cp", "cphase"):
        return list(qubits), _controlled([[1, 0], [0, _exp(1j * params[0])]], 1)
    if name == "crz":
        return list(qubits), _crz(params[0])
    if name == "cu3":
        return list(qubits), _controlled(_u3(params[0], params[1], params[2]), 1)
    if name == "cu":
        # 相位 gamma 只作用于控制=1 的块
        base = _controlled(_u3(params[0], params[1], params[2]), 1)
        phase = _exp(1j * params[3])
        for i in range(2, 4):
            for j in range(2, 4):
                base[i][j] *= phase
        return list(qubits), base
    if name == "swap":
        return list(qubits), _swap_matrix()
    raise ValueError("模拟器不支持门 %r" % name)


def simulate(circuit: Circuit) -> List[complex]:
    """返回终态振幅列表：下标 i 的比特 b 即量子比特 b（LSB 约定）。"""
    n = circuit.n_qubits
    if n > 24:
        raise ValueError("量子比特数 %d 超出状态向量模拟能力" % n)
    state: List[complex] = [0j] * (1 << n)
    state[0] = 1 + 0j
    for op in circuit.ops:
        qubits, matrix = _op_matrix(op)
        state = _apply(state, n, qubits, matrix)
    return state


def _apply(state: List[complex], n: int, qubits: List[int],
           matrix: List[List[complex]]) -> List[complex]:
    k = len(qubits)
    dim = 1 << k
    qubit_set = set(qubits)
    others = [q for q in range(n) if q not in qubit_set]
    new_state = list(state)
    for mask in range(1 << len(others)):
        base = 0
        for b, q in enumerate(others):
            if (mask >> b) & 1:
                base |= 1 << q
        indices = []
        for local in range(dim):
            idx = base
            for b, q in enumerate(qubits):
                if (local >> b) & 1:
                    idx |= 1 << q
            indices.append(idx)
        old = [state[i] for i in indices]
        for row, idx in enumerate(indices):
            acc = 0j
            row_values = matrix[row]
            for col in range(dim):
                acc += row_values[col] * old[col]
            new_state[idx] = acc
    return new_state


def probabilities(state: List[complex]) -> List[float]:
    return [abs(a) ** 2 for a in state]


def sample_counts(circuit: Circuit, shots: int,
                  rng: Optional[random.Random] = None) -> Dict[str, int]:
    """按 |振幅|² 采样 shots 次，返回 little 位序 counts（最右字符 = c[0]）。"""
    if shots <= 0:
        raise ValueError("shots 必须为正整数")
    if rng is None:
        rng = random.Random()
    state = simulate(circuit)
    probs = probabilities(state)
    dim = len(state)
    if circuit.n_clbits == 0 and not circuit.measures:
        # 无经典位：退化为对全部量子比特全测量
        key_len = circuit.n_qubits
        measures = [(q, q) for q in range(circuit.n_qubits)]
    else:
        key_len = circuit.n_clbits
        measures = circuit.measures
    clbit_of_qubit = {q: c for q, c in measures}
    draws = rng.choices(range(dim), weights=probs, k=shots)
    counts: Dict[str, int] = {}
    for draw in draws:
        bits = ["0"] * key_len
        for qubit, clbit in clbit_of_qubit.items():
            if (draw >> qubit) & 1:
                bits[key_len - 1 - clbit] = "1"
        key = "".join(bits)
        counts[key] = counts.get(key, 0) + 1
    return counts
