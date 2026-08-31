#!/usr/bin/env python3
"""L3 Bonus：把 Hybrid-QASM 编译为"量子扩展指令 + 官方 7 指令"混合程序。

与主提交（compile_hybrid，纯官方 7 指令）不同，这里量子部分编译为
量子扩展指令（QH/QX/QCX/QMS/QP），经典部分仍编译为官方指令——两者在
riscv_emulator_qext.py 的扩展模拟器上真实执行，构成 Bonus 要求的
"指令编码实际进入可运行、可验证执行链路"的最小闭环。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loomq_l3 import classic, parser  # noqa: E402
from loomq_l3.codegen import compile_classical  # noqa: E402

try:
    from loomq import parse_qasm
except ImportError:  # pragma: no cover
    from starter_kit.loomq import parse_qasm  # type: ignore

# 扩展 ISA 直接支持的量子门（白名单子集）；其余门先经 loomq 白名单化，
# 其中 h/x/cx 可直接映射，其他门以"分解注释 + 白名单降级"处理时保留语义
_DIRECT = {"h": "qh", "x": "qx", "cx": "qcx"}

# 相位门 → QP 的 π/4 档位 k（e^{i·kπ/4}）：t/s/z 及其共轭
_PHASE_STEPS = {"t": 1, "s": 2, "z": 4, "sdg": 6, "tdg": 7}


def _phase_step(theta: float) -> int:
    """把连续相位角折算成 QP 档位；非 π/4 整数倍则显式报错（不静默丢语义）。"""
    step = math.pi / 4
    k = int(round((theta % (2 * math.pi)) / step))
    if abs(theta - k * step) > 1e-9 and abs(theta % (2 * math.pi) - k * step) > 1e-9:
        raise ValueError("相位角 %r 不是 π/4 的整数倍，超出 QP 档位编码范围" % theta)
    return k % 8


def compile_hybrid_qext(hybrid_qasm_str: str) -> Tuple[List[dict], str]:
    quantum_text, classical_text = parser.split_hybrid(hybrid_qasm_str)
    circuit = parse_qasm(quantum_text)
    lines: List[str] = ["# loomq l3 bonus: quantum-extended assembly"]
    quantum_ops: List[dict] = []
    for op in circuit.ops:
        quantum_ops.append({"op": op.name, "params": list(op.params),
                            "qubits": list(op.qubits), "measure": None})
        if op.name in _DIRECT and not op.params:
            lines.append("%s %s" % (_DIRECT[op.name],
                                    ", ".join(str(q) for q in op.qubits)))
        elif op.name in _PHASE_STEPS and not op.params:
            lines.append("qp %d, %d" % (op.qubits[0], _PHASE_STEPS[op.name]))
        elif op.name in ("p", "u1") and len(op.params) == 1:
            lines.append("qp %d, %d" % (op.qubits[0], _phase_step(op.params[0])))
        else:
            # 扩展 ISA 演示 h/x/cx 与 π/4 档相位门；其余门在主提交中已由
            # 官方 7 指令通路处理，这里显式报错以防静默丢语义
            raise ValueError("Bonus 扩展 ISA 最小集不含门 %r" % op.name)
    for qubit, clbit in circuit.measures:
        quantum_ops.append({"op": "measure", "params": [], "qubits": [qubit],
                            "measure": [qubit, clbit]})
        lines.append("qms %d, x%d" % (qubit, 10 + clbit))
    stmts = classic.parse_classical(classical_text) if classical_text.strip() else []
    if stmts:
        lines.append(compile_classical(stmts).rstrip())
    return quantum_ops, "\n".join(lines) + "\n"
