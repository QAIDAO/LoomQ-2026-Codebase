#!/usr/bin/env python3
"""参考模拟器：自己精确算一遍答案（仅供验收测试使用，不在提交路径上）

**为什么必须有它。**

验收 L1 时有两个看起来很强、其实有同一个盲区的办法：

- 跨后端对拍：同一电路在两家 SDK 上分布一致
- 自逆电路：U 接上 U†，必须回到初态

如果**解析器**把某个门读错了（比如把 `cu1` 的参数取错、把 `cx` 的控制位和
目标位搞反），这两个办法**都查不出来**——两个后端会一致地按错电路去跑，
而错电路接上它自己的逆，照样精确回到初态。

所以必须有一个东西，回答的是另一个问题：**我们建出来的电路，真的就是
QASM 文本写的那个电路吗？** 这个文件就是那个东西：直接按门的数学定义算末态，
给出精确概率（不是采样，没有统计涨落），再拿它当标准答案去卡两个后端。

只依赖 numpy（braket 已经带了）。
"""

import itertools
import math

import numpy as np

PI = math.pi

_H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
_X = np.array([[0, 1], [1, 0]], dtype=complex)
_S = np.array([[1, 0], [0, 1j]], dtype=complex)
_SDG = np.array([[1, 0], [0, -1j]], dtype=complex)
_T = np.array([[1, 0], [0, np.exp(1j * PI / 4)]], dtype=complex)
_TDG = np.array([[1, 0], [0, np.exp(-1j * PI / 4)]], dtype=complex)

# 两比特门的基底顺序是 |q0 q1>，其中 q0 是门参数里写在前面的那个比特（高位）
_CX = np.array(
    [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex
)
_SWAP = np.array(
    [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=complex
)


def _rz(theta):
    return np.array(
        [[np.exp(-1j * theta / 2), 0], [0, np.exp(1j * theta / 2)]], dtype=complex
    )


def _ry(theta):
    half = theta / 2
    return np.array(
        [[math.cos(half), -math.sin(half)], [math.sin(half), math.cos(half)]], dtype=complex
    )


def _cu1(theta):
    return np.diag([1, 1, 1, np.exp(1j * theta)]).astype(complex)


def _ccx():
    matrix = np.eye(8, dtype=complex)
    matrix[[6, 7]] = matrix[[7, 6]]  # |110> <-> |111>
    return matrix


def matrix_for(name, params):
    if name == "h":
        return _H
    if name == "x":
        return _X
    if name == "s":
        return _S
    if name == "sdg":
        return _SDG
    if name == "t":
        return _T
    if name == "tdg":
        return _TDG
    if name == "rz":
        return _rz(params[0])
    if name == "ry":
        return _ry(params[0])
    if name == "cx":
        return _CX
    if name == "swap":
        return _SWAP
    if name == "cu1":
        return _cu1(params[0])
    if name == "ccx":
        return _ccx()
    raise ValueError("参考模拟器不认识的门：%r" % name)


def _apply(state, matrix, qubits):
    """把一个 m 比特门作用到指定比特上。

    state 的形状是 (2,) * n，第 j 根轴对应第 j 个量子比特。
    """
    m = len(qubits)
    tensor = matrix.reshape((2,) * (2 * m))
    # 用门矩阵的"输入"那一半，去和 state 里对应的那几根轴做缩并
    state = np.tensordot(tensor, state, axes=(list(range(m, 2 * m)), list(qubits)))
    # 缩并后新轴跑到最前面，按原来的位置放回去
    return np.moveaxis(state, list(range(m)), list(qubits))


def exact_distribution(circuit, tolerance=1e-12):
    """算出电路的精确测量分布：{规范 key: 概率}。

    key 的排法与赛题规范一致：最右边是 c[0]。没被测量的经典比特按 0 处理。
    """
    n = circuit.num_qubits
    state = np.zeros((2,) * n, dtype=complex)
    state[(0,) * n] = 1.0

    for op in circuit.ops:
        if hasattr(op, "name"):  # Gate
            state = _apply(state, matrix_for(op.name, op.params), op.qubits)

    probabilities = np.abs(state) ** 2
    mapping = circuit.measure_map()  # 经典比特 -> 量子比特
    width = max(circuit.num_clbits, 1)

    distribution = {}
    for values in itertools.product((0, 1), repeat=n):
        probability = float(probabilities[values])
        if probability <= tolerance:
            continue
        key = "".join(
            str(values[mapping[clbit]]) if clbit in mapping else "0"
            for clbit in range(width - 1, -1, -1)
        )
        distribution[key] = distribution.get(key, 0.0) + probability
    return distribution
