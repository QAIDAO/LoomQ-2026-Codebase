"""可选的门分解工具（见 starter_kit/gate_identities.md）。

今天用不到这个模块来保证正确性：simulate.py 已经原生实现了完整的
12 门白名单。这个模块存在的目的有两个：

1. 供以后接厂商 SDK 用——如果那个 SDK 的导入器只认更小的原生门集合，
   可以先分解到 {h, x, rz, ry, u1, cx} 再交给它。
2. gate_identities.md 自己建议的自测方法——把原电路和分解后的电路都
   丢进 simulate.sample_counts() 跑一遍，确认两者分布一致（见
   gate_identities.md，"自验方法"）。
"""

import math
from typing import List, Tuple

from .ir import Circuit, GateOp, MeasureOp, Op

_Elementary = Tuple[str, Tuple[int, ...], Tuple[float, ...]]


def _decompose_one(name: str, qubits: Tuple[int, ...], params: Tuple[float, ...]) -> List[_Elementary]:
    if name == "s":
        return [("u1", qubits, (math.pi / 2,))]
    if name == "sdg":
        return [("u1", qubits, (-math.pi / 2,))]
    if name == "t":
        return [("u1", qubits, (math.pi / 4,))]
    if name == "tdg":
        return [("u1", qubits, (-math.pi / 4,))]
    if name == "swap":
        a, b = qubits
        return [("cx", (a, b), ()), ("cx", (b, a), ()), ("cx", (a, b), ())]
    if name == "cu1":
        a, b = qubits
        theta = params[0]
        return [
            ("u1", (a,), (theta / 2,)),
            ("cx", (a, b), ()),
            ("u1", (b,), (-theta / 2,)),
            ("cx", (a, b), ()),
            ("u1", (b,), (theta / 2,)),
        ]
    if name == "ccx":
        a, b, c = qubits
        return [
            ("h", (c,), ()),
            ("cx", (b, c), ()),
            ("u1", (c,), (-math.pi / 4,)),
            ("cx", (a, c), ()),
            ("u1", (c,), (math.pi / 4,)),
            ("cx", (b, c), ()),
            ("u1", (c,), (-math.pi / 4,)),
            ("cx", (a, c), ()),
            ("u1", (b,), (math.pi / 4,)),
            ("u1", (c,), (math.pi / 4,)),
            ("h", (c,), ()),
            ("cx", (a, b), ()),
            ("u1", (a,), (math.pi / 4,)),
            ("u1", (b,), (-math.pi / 4,)),
            ("cx", (a, b), ()),
        ]
    # h、x、rz、ry、cx 本身已经是基础门，原样返回。
    return [(name, qubits, params)]


def decompose_to_basis(circuit: Circuit) -> Circuit:
    """把每个门都改写成 {h, x, rz, ry, u1, cx} 这个基础门集合。"""
    ops: List[Op] = []
    for op in circuit.ops:
        if isinstance(op, MeasureOp):
            ops.append(op)
            continue
        for name, qubits, params in _decompose_one(op.name, op.qubits, op.params):
            ops.append(GateOp(name=name, qubits=qubits, params=params))
    return Circuit(n_qubits=circuit.n_qubits, n_clbits=circuit.n_clbits, ops=ops)
