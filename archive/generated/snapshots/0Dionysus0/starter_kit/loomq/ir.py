"""LoomQ 电路的后端无关中间表示（IR）。"""

from dataclasses import dataclass, field
from typing import List, Tuple, Union

# problem_statement.md 第三节里的 12 门 qelib1 白名单。这是
# transpile()/run() *输入* QASM 里唯一允许出现的门集合。
WHITELIST_GATES = frozenset({
    "h", "x", "s", "sdg", "t", "tdg",
    "rz", "ry",
    "cx", "cu1", "swap",
    "ccx",
})

# u1 不属于比赛的白名单，它只是 loomq/decompose.py 内部用来搭桥的辅助门
# （见 gate_identities.md #1-#2）。
_KNOWN_GATES = WHITELIST_GATES | {"u1"}

GATE_ARITY = {
    "h": 1, "x": 1, "s": 1, "sdg": 1, "t": 1, "tdg": 1,
    "rz": 1, "ry": 1, "u1": 1,
    "cx": 2, "cu1": 2, "swap": 2,
    "ccx": 3,
}

GATE_PARAM_COUNT = {
    name: (1 if name in ("rz", "ry", "cu1", "u1") else 0) for name in _KNOWN_GATES
}


@dataclass(frozen=True)
class GateOp:
    name: str
    qubits: Tuple[int, ...]
    params: Tuple[float, ...] = ()

    def __post_init__(self):
        if self.name not in GATE_ARITY:
            raise ValueError(f"unknown gate '{self.name}'")
        if len(self.qubits) != GATE_ARITY[self.name]:
            raise ValueError(
                f"gate '{self.name}' expects {GATE_ARITY[self.name]} qubit(s), "
                f"got {len(self.qubits)}"
            )
        if len(self.params) != GATE_PARAM_COUNT[self.name]:
            raise ValueError(
                f"gate '{self.name}' expects {GATE_PARAM_COUNT[self.name]} parameter(s), "
                f"got {len(self.params)}"
            )


@dataclass(frozen=True)
class MeasureOp:
    qubit: int
    clbit: int


Op = Union[GateOp, MeasureOp]


@dataclass
class Circuit:
    n_qubits: int
    n_clbits: int
    ops: List[Op] = field(default_factory=list)

    def gate_ops(self) -> List[GateOp]:
        return [op for op in self.ops if isinstance(op, GateOp)]

    def measure_ops(self) -> List[MeasureOp]:
        return [op for op in self.ops if isinstance(op, MeasureOp)]

    def depth(self) -> int:
        """只统计门操作的分层深度（简单贪心调度）。"""
        last_layer = [-1] * self.n_qubits
        max_layer = -1
        for op in self.gate_ops():
            layer = max(last_layer[q] for q in op.qubits) + 1
            for q in op.qubits:
                last_layer[q] = layer
            max_layer = max(max_layer, layer)
        return max_layer + 1
