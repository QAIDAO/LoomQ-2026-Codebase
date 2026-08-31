"""与后端无关的平坦电路中间表示。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

# 题面 L1 门白名单（12 门）；transpile 输出只使用这些门
WHITELIST: Tuple[str, ...] = (
    "h", "x", "s", "sdg", "t", "tdg",
    "rz", "ry",
    "cx", "cu1", "swap", "ccx",
)


@dataclass(frozen=True)
class Op:
    """一条门操作。params 为弧度参数，qubits 为全局量子比特下标。"""

    name: str
    params: Tuple[float, ...] = ()
    qubits: Tuple[int, ...] = ()


@dataclass
class Circuit:
    n_qubits: int = 0
    n_clbits: int = 0
    ops: List[Op] = field(default_factory=list)
    # 每项 (量子比特下标, 经典比特下标)，顺序即测量顺序
    measures: List[Tuple[int, int]] = field(default_factory=list)

    def op_count(self) -> int:
        return len(self.ops)
