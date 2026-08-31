#!/usr/bin/env python3
"""中立电路表示（整个中间层的枢纽）

这是"通用中间层"里的那个"通用"落在什么地方：

    OpenQASM 2.0 文本 ──解析──> Circuit ──┬──> OpenQASM 2.0  (spinq)
                                          ├──> OpenQASM 3    (braket)
                                          └──> OriginIR      (originq)

只有一个解析器，只有一份电路表示。三个后端各自只负责"把这份表示写成自己的方言"。
如果为每个后端各写一条从文本到文本的通路，那就是三套硬编码——赛题明写会被判不合格。

Circuit 里存的东西刻意最小：
- 用了几个量子比特、几个经典比特
- 一串操作，按顺序排好

比特一律用**全局整数下标**。源码里写 `qreg a[2]; qreg b[3];` 时，
a[0..1] 就是 0..1，b[0..2] 就是 2..4。这样后面所有人都只跟数字打交道，
不用再关心寄存器叫什么名字。
"""

from collections import namedtuple

# name   : 小写门名，取自赛题 12 门白名单
# params : 已经算成浮点数的参数（源码里的 pi/2 在解析阶段就算完了）
# qubits : 全局比特下标列表
Gate = namedtuple("Gate", "name params qubits")

# 把 qubit 号比特的测量结果写进 clbit 号经典比特
Measure = namedtuple("Measure", "qubit clbit")


class Circuit:
    def __init__(self, num_qubits=0, num_clbits=0, ops=None):
        self.num_qubits = num_qubits
        self.num_clbits = num_clbits
        self.ops = list(ops or [])

    def add(self, op):
        self.ops.append(op)
        return self

    @property
    def gates(self):
        return [op for op in self.ops if isinstance(op, Gate)]

    @property
    def measurements(self):
        return [op for op in self.ops if isinstance(op, Measure)]

    def measure_map(self):
        """经典比特 -> 量子比特 的映射。

        后端返回的结果通常是按"量子比特下标"排的，而赛题要求的 counts
        是按"经典比特"排的。测量语句允许任意错位（比如 q[0] 测进 c[1]），
        所以必须留着这张映射表，不能想当然地按顺序对号入座。
        """
        mapping = {}
        for op in self.ops:
            if isinstance(op, Measure):
                mapping[op.clbit] = op.qubit
        return mapping

    def depth_estimate(self):
        """粗略深度：只用于 meta 字段展示，不参与任何判定。"""
        last_used = {}
        depth = 0
        for op in self.ops:
            qubits = op.qubits if isinstance(op, Gate) else [op.qubit]
            level = max((last_used.get(q, 0) for q in qubits), default=0) + 1
            for q in qubits:
                last_used[q] = level
            depth = max(depth, level)
        return depth

    def __repr__(self):
        return "Circuit(qubits=%d, clbits=%d, ops=%d)" % (
            self.num_qubits,
            self.num_clbits,
            len(self.ops),
        )
