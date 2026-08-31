"""三个后端共用的参考无噪声态矢量模拟器。

这是 L1"统一中间层"真正执行电路的唯一入口：每个后端适配器
（loomq/targets/*.py）都是调用这同一个模块来产出 run() 的结果。它直接
实现了 qelib1 白名单（外加内部辅助门 `u1`），所以正确性上不需要任何
门分解——decompose.py 是另一个可选的工具，供以后接厂商 SDK、且那个
SDK 的导入器只认更小的原生门集合时使用。

qubit `q` 绑定到态矢量下标的第 `q` 位（低位在前，从 0 开始编号）——这
只是一个内部约定；对外契约要求的比特序，只在把 counts 转换成比特串
字符串的那一步（见 sample_counts）单独强制保证，跟这里的内部选择无关。
"""

from functools import partial
from typing import Dict, Optional

import numpy as np

from .gates import single_qubit_matrix
from .ir import Circuit, GateOp, MeasureOp


def _apply_single(state: np.ndarray, qubit: int, mat: np.ndarray) -> np.ndarray:
    bit = 1 << qubit
    idx = np.arange(state.shape[0])
    idx0 = idx[(idx & bit) == 0]
    idx1 = idx0 | bit
    a, b = state[idx0], state[idx1]
    new_state = state.copy()
    new_state[idx0] = mat[0, 0] * a + mat[0, 1] * b
    new_state[idx1] = mat[1, 0] * a + mat[1, 1] * b
    return new_state


def _apply_cx(state: np.ndarray, control: int, target: int) -> np.ndarray:
    cbit, tbit = 1 << control, 1 << target
    idx = np.arange(state.shape[0])
    idx0 = idx[((idx & cbit) != 0) & ((idx & tbit) == 0)]
    idx1 = idx0 | tbit
    new_state = state.copy()
    new_state[idx0], new_state[idx1] = state[idx1], state[idx0]
    return new_state


def _apply_swap(state: np.ndarray, a: int, b: int) -> np.ndarray:
    abit, bbit = 1 << a, 1 << b
    idx = np.arange(state.shape[0])
    idx_10 = idx[((idx & abit) != 0) & ((idx & bbit) == 0)]
    idx_01 = (idx_10 & ~abit) | bbit
    new_state = state.copy()
    new_state[idx_10], new_state[idx_01] = state[idx_01], state[idx_10]
    return new_state


def _apply_cu1(state: np.ndarray, control: int, target: int, theta: float) -> np.ndarray:
    cbit, tbit = 1 << control, 1 << target
    idx = np.arange(state.shape[0])
    mask = ((idx & cbit) != 0) & ((idx & tbit) != 0)
    new_state = state.copy()
    new_state[mask] = state[mask] * np.exp(1j * theta)
    return new_state


def _apply_ccx(state: np.ndarray, c1: int, c2: int, target: int) -> np.ndarray:
    c1bit, c2bit, tbit = 1 << c1, 1 << c2, 1 << target
    idx = np.arange(state.shape[0])
    idx0 = idx[((idx & c1bit) != 0) & ((idx & c2bit) != 0) & ((idx & tbit) == 0)]
    idx1 = idx0 | tbit
    new_state = state.copy()
    new_state[idx0], new_state[idx1] = state[idx1], state[idx0]
    return new_state


def _dispatch_single(name, state, qubits, params):
    return _apply_single(state, qubits[0], single_qubit_matrix(name, params))


def _dispatch_cx(state, qubits, params):
    return _apply_cx(state, qubits[0], qubits[1])


def _dispatch_swap(state, qubits, params):
    return _apply_swap(state, qubits[0], qubits[1])


def _dispatch_cu1(state, qubits, params):
    return _apply_cu1(state, qubits[0], qubits[1], params[0])


def _dispatch_ccx(state, qubits, params):
    return _apply_ccx(state, qubits[0], qubits[1], qubits[2])


# 每个 handler 都共用 (state, qubits, params) -> new_state 这一个签名，
# 所以以后加第 13 个门只需要在这里多加一行，不用再加一条 elif。
_GATE_HANDLERS = {
    name: partial(_dispatch_single, name)
    for name in ("h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "u1")
}
_GATE_HANDLERS.update(cx=_dispatch_cx, swap=_dispatch_swap, cu1=_dispatch_cu1, ccx=_dispatch_ccx)


def statevector(circuit: Circuit) -> np.ndarray:
    """按顺序应用每一个 GateOp（中间穿插的 MeasureOp 会被忽略——LoomQ
    的每个测试电路都是只在最后统一测量一次），返回末态振幅向量。"""
    n = circuit.n_qubits
    state = np.zeros(1 << n, dtype=complex)
    state[0] = 1.0
    for op in circuit.ops:
        if not isinstance(op, GateOp):
            continue
        try:
            handler = _GATE_HANDLERS[op.name]
        except KeyError:
            raise ValueError(f"simulator has no rule for gate '{op.name}'") from None
        state = handler(state, op.qubits, op.params)
    return state


def sample_counts(circuit: Circuit, shots: int, seed: Optional[int] = None) -> Dict[str, int]:
    """采样 `shots` 次测量结果，按赛制要求的比特串规范返回 counts：
    `bit_order: "little"`，`c[0]` 是最右边那个字符（key =
    c[n-1]...c[1]c[0]，即 Qiskit 的约定）。"""
    state = statevector(circuit)
    probs = np.abs(state) ** 2
    total = probs.sum()
    if total <= 0:
        raise ValueError("circuit produced a zero-norm state")
    probs = probs / total  # 防止浮点误差导致概率和不精确等于 1

    measures = circuit.measure_ops()
    if not measures:
        raise ValueError("circuit has no measure statements")

    rng = np.random.default_rng(seed)
    outcome_counts = rng.multinomial(shots, probs)

    n_clbits = circuit.n_clbits
    counts: Dict[str, int] = {}
    for basis_index, n_hits in enumerate(outcome_counts):
        if n_hits == 0:
            continue
        clbit_values = [0] * n_clbits
        for m in measures:
            clbit_values[m.clbit] = (basis_index >> m.qubit) & 1
        bitstring = "".join(str(v) for v in reversed(clbit_values))
        counts[bitstring] = counts.get(bitstring, 0) + int(n_hits)
    return counts
