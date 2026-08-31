"""12 门 qelib1 白名单的酉矩阵定义，外加 decompose.py 用的内部
辅助门 `u1`（见 gate_identities.md）。"""

import cmath
import math
from typing import Sequence

import numpy as np

_SQRT2_INV = 1 / math.sqrt(2)

_FIXED_SINGLE_QUBIT = {
    "h": np.array([[_SQRT2_INV, _SQRT2_INV], [_SQRT2_INV, -_SQRT2_INV]], dtype=complex),
    "x": np.array([[0, 1], [1, 0]], dtype=complex),
    "s": np.array([[1, 0], [0, 1j]], dtype=complex),
    "sdg": np.array([[1, 0], [0, -1j]], dtype=complex),
    "t": np.array([[1, 0], [0, cmath.exp(1j * math.pi / 4)]], dtype=complex),
    "tdg": np.array([[1, 0], [0, cmath.exp(-1j * math.pi / 4)]], dtype=complex),
}


def rz_matrix(theta: float) -> np.ndarray:
    return np.array(
        [[cmath.exp(-1j * theta / 2), 0], [0, cmath.exp(1j * theta / 2)]], dtype=complex
    )


def ry_matrix(theta: float) -> np.ndarray:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array([[c, -s], [s, c]], dtype=complex)


def u1_matrix(theta: float) -> np.ndarray:
    """仅供内部使用的辅助门（diag(1, e^{i theta})）；不属于对外输出的
    12 门白名单，只被 decompose.py 用到。"""
    return np.array([[1, 0], [0, cmath.exp(1j * theta)]], dtype=complex)


def _constant(matrix: np.ndarray):
    """把一个无参数矩阵包装成 `params -> matrix` 的构造函数，让
    _SINGLE_QUBIT_BUILDERS 里每一项的调用方式保持一致。"""
    return lambda params: matrix


_SINGLE_QUBIT_BUILDERS = {
    **{name: _constant(matrix) for name, matrix in _FIXED_SINGLE_QUBIT.items()},
    "rz": lambda params: rz_matrix(params[0]),
    "ry": lambda params: ry_matrix(params[0]),
    "u1": lambda params: u1_matrix(params[0]),
}


def single_qubit_matrix(name: str, params: Sequence[float]) -> np.ndarray:
    try:
        build = _SINGLE_QUBIT_BUILDERS[name]
    except KeyError:
        raise ValueError(f"'{name}' is not a single-qubit gate") from None
    return build(params)
