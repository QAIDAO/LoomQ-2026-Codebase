"""电路模板库：确定性生成白名单 QASM + 解析理想分布。

设计原则：LLM 只负责把自然语言映射到 (template, params)，
QASM 全文一律由这里确定性生成——这是隐藏变体下正确率的天花板保障。
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

WHITELIST_GATES = ("h", "x", "s", "sdg", "t", "tdg", "rz", "ry",
                   "cx", "cu1", "swap", "ccx")

Template = Tuple[str, Dict[str, float]]  # (qasm, 理想分布)


def _header(n: int) -> str:
    return 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[%d];\ncreg c[%d];\n' % (n, n)


def _measure_all(n: int) -> str:
    return "measure q -> c;\n"


def bell(params: Dict) -> Template:
    qasm = _header(2) + "h q[0];\ncx q[0], q[1];\n" + _measure_all(2)
    return qasm, {"00": 0.5, "11": 0.5}


def ghz(params: Dict) -> Template:
    n = max(2, int(params.get("n_qubits", 3)))
    body = ["h q[0];"]
    body += ["cx q[%d], q[%d];" % (i, i + 1) for i in range(n - 1)]
    qasm = _header(n) + "\n".join(body) + "\n" + _measure_all(n)
    return qasm, {"0" * n: 0.5, "1" * n: 0.5}


def uniform(params: Dict) -> Template:
    n = max(1, int(params.get("n_qubits", 3)))
    body = ["h q[%d];" % i for i in range(n)]
    qasm = _header(n) + "\n".join(body) + "\n" + _measure_all(n)
    return qasm, {format(i, "0%db" % n): 1.0 / (1 << n) for i in range(1 << n)}


def basis(params: Dict) -> Template:
    """任意计算基矢态：ones 为需要翻成 |1⟩ 的下标列表。"""
    n = max(1, int(params.get("n_qubits", 2)))
    ones = sorted({int(i) for i in params.get("ones", []) if 0 <= int(i) < n})
    bits = ["0"] * n
    for i in ones:
        bits[n - 1 - i] = "1"  # little 位序：c[0] 在最右
    key = "".join(bits)
    body = ["x q[%d];" % i for i in ones]
    qasm = _header(n) + "".join(line + "\n" for line in body) + _measure_all(n)
    return qasm, {key: 1.0}


def w_state(params: Dict) -> Template:
    """W 态旋转级联：x q0 起步，cry(θ_k) + cx 逐位传递激发。

    θ_k = 2·arccos(1/√(n-k))，cry(θ) 用 ry/cx 分解（精确，无相位误差）：
      cry(θ) c,t ≡ ry(θ/2) t; cx c,t; ry(-θ/2) t; cx c,t
    """
    n = max(2, int(params.get("n_qubits", 3)))
    lines = ["x q[0];"]
    for k in range(n - 1):
        theta = 2 * math.acos(1 / math.sqrt(n - k))
        half = theta / 2
        c, t = k, k + 1
        lines.append("ry(%.17g) q[%d];" % (half, t))
        lines.append("cx q[%d], q[%d];" % (c, t))
        lines.append("ry(%.17g) q[%d];" % (-half, t))
        lines.append("cx q[%d], q[%d];" % (c, t))
        # 激发转移：新比特为控制、旧比特为目标（|1,1> → |0,1>）
        lines.append("cx q[%d], q[%d];" % (t, c))
    qasm = _header(n) + "\n".join(lines) + "\n" + _measure_all(n)
    expect = {}
    for i in range(n):
        bits = ["0"] * n
        bits[n - 1 - i] = "1"
        expect["".join(bits)] = 1.0 / n
    return qasm, expect


TEMPLATES = {
    "bell": bell,
    "ghz": ghz,
    "uniform": uniform,
    "basis": basis,
    "w": w_state,
}

TEMPLATE_NAMES = tuple(sorted(TEMPLATES))


def build(template: str, params: Dict) -> Template:
    if template not in TEMPLATES:
        raise ValueError("未知模板 %r，可用：%s" % (template, ", ".join(TEMPLATE_NAMES)))
    return TEMPLATES[template](params or {})
