#!/usr/bin/env python3
"""LoomQ L1 隐藏电路预演验证（本地开发用，不参与评测契约）。

用独立的 numpy 态矢参考模拟器，对 12 门白名单的全部组合电路
（QFT-4 / Grover-3 / Random-Circuit 变体）在三个后端上逐一验证
Hellinger 保真度 >= 0.97。

运行：python3 starter_kit/verify_hidden_circuits.py
"""

from __future__ import annotations

import cmath
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import adapter  # noqa: E402

PASSED = 0
FAILED = 0


def hellinger(observed: dict, expected: dict) -> float:
    states = set(observed) | set(expected)
    dist = math.sqrt(
        sum(
            (math.sqrt(observed.get(s, 0.0)) - math.sqrt(expected.get(s, 0.0))) ** 2
            for s in states
        )
    ) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - dist))


# --- 独立 numpy 态矢参考模拟器（小端，key 最右为 q[0]） ---------------------

def reference_simulate(qasm: str, shots: int = 8192) -> dict:
    """解析 QASM2 白名单电路并在 numpy 态矢上模拟，返回**精确**归一化分布。

    期望分布直接用态矢概率（|psi|^2），不做二次采样——与官方评测
    「对比精确理想分布」一致，避免双侧采样噪声把验证结果搞抖。
    """
    lines = []
    for raw in qasm.splitlines():
        line = raw.split("//", 1)[0].strip()
        if line:
            lines.append(line.rstrip(";").strip())
    n = 0
    ops = []
    for line in lines:
        if line.startswith("OPENQASM") or line.startswith("include"):
            continue
        import re
        m = re.match(r"qreg\s+\w+\s*\[\s*(\d+)\s*\]", line)
        if m:
            n = int(m.group(1))
            continue
        if line.startswith("creg") or line.startswith("measure"):
            continue
        m = re.match(r"([a-z][a-z0-9]*)\s*(?:\((.*?)\))?\s*(.+)$", line)
        if m and m.group(1) in adapter._GATE_ARITY:
            params = [float(p) for p in m.group(2).split(",")] if m.group(2) else []
            qubits = re.findall(r"(\w+)\s*\[\s*(\d+)\s*\]", m.group(3))
            ops.append((m.group(1), params, [int(q[1]) for q in qubits]))
    if n == 0:
        raise ValueError("no qubits")

    dim = 1 << n
    psi = np.zeros(dim, dtype=complex)
    psi[0] = 1.0

    def apply_1q(mat, qubit):
        nonlocal psi
        bit = 1 << qubit
        for idx in range(dim):
            if idx & bit:
                continue
            partner = idx | bit
            a, b = psi[idx], psi[partner]
            psi[idx] = mat[0, 0] * a + mat[0, 1] * b
            psi[partner] = mat[1, 0] * a + mat[1, 1] * b

    h = np.array([[1, 1], [1, -1]]) / math.sqrt(2)
    x = np.array([[0, 1], [1, 0]])
    s = np.array([[1, 0], [0, 1j]])
    sdg = np.array([[1, 0], [0, -1j]])
    t = np.array([[1, 0], [0, cmath.exp(1j * math.pi / 4)]])
    tdg = np.array([[1, 0], [0, cmath.exp(-1j * math.pi / 4)]])

    def rz(th):
        return np.array([[cmath.exp(-1j * th / 2), 0], [0, cmath.exp(1j * th / 2)]])

    def ry(th):
        c, s_ = math.cos(th / 2), math.sin(th / 2)
        return np.array([[c, -s_], [s_, c]])

    for name, params, qs in ops:
        if name == "h":
            apply_1q(h, qs[0])
        elif name == "x":
            apply_1q(x, qs[0])
        elif name == "s":
            apply_1q(s, qs[0])
        elif name == "sdg":
            apply_1q(sdg, qs[0])
        elif name == "t":
            apply_1q(t, qs[0])
        elif name == "tdg":
            apply_1q(tdg, qs[0])
        elif name == "rz":
            apply_1q(rz(params[0]), qs[0])
        elif name == "ry":
            apply_1q(ry(params[0]), qs[0])
        elif name == "cx":
            ctrl, tgt = 1 << qs[0], 1 << qs[1]
            for idx in range(dim):
                if (idx & ctrl) and not (idx & tgt):
                    partner = idx | tgt
                    psi[idx], psi[partner] = psi[partner], psi[idx]
        elif name == "cu1":
            ctrl, tgt = 1 << qs[0], 1 << qs[1]
            phase = cmath.exp(1j * params[0])
            for idx in range(dim):
                if idx & ctrl & tgt == ctrl & tgt:
                    psi[idx] *= phase
        elif name == "swap":
            fbit, sbit = 1 << qs[0], 1 << qs[1]
            for idx in range(dim):
                if bool(idx & fbit) and not (idx & sbit):
                    partner = (idx & ~fbit) | sbit
                    psi[idx], psi[partner] = psi[partner], psi[idx]
        elif name == "ccx":
            cmask = (1 << qs[0]) | (1 << qs[1])
            tbit = 1 << qs[2]
            for idx in range(dim):
                if idx & cmask == cmask and not (idx & tbit):
                    partner = idx | tbit
                    psi[idx], psi[partner] = psi[partner], psi[idx]

    probs = np.abs(psi) ** 2
    return {format(idx, "0%db" % n): float(p) for idx, p in enumerate(probs) if p > 1e-12}


# --- 电路生成 ----------------------------------------------------------------

def bell() -> str:
    return """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""


def ghz(k: int) -> str:
    lines = [f"OPENQASM 2.0;", 'include "qelib1.inc";',
             f"qreg q[{k}];", f"creg c[{k}];", "h q[0];"]
    for i in range(1, k):
        lines.append(f"cx q[0], q[{i}];")
    lines.append("measure q -> c;")
    return "\n".join(lines)


def qft4() -> str:
    """QFT-4：h + cu1 + swap，全部在 12 门白名单内。"""
    n = 4
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";',
             "qreg q[4];", "creg c[4];"]
    for j in range(n):
        lines.append(f"h q[{j}];")
        for k in range(j + 1, n):
            theta = math.pi / (2 ** (k - j))
            lines.append(f"cu1({theta:.12f}) q[{j}], q[{k}];")
    for i in range(n // 2):
        lines.append(f"swap q[{i}], q[{n - 1 - i}];")
    lines.append("measure q -> c;")
    return "\n".join(lines)


def grover3() -> str:
    """Grover-3 一轮迭代：H 层 + 相位翻转(ccx+x) + H 层。"""
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";',
             "qreg q[3];", "creg c[3];"]
    for i in range(3):
        lines.append(f"h q[{i}];")
    # oracle：标记 |111>
    lines.append("x q[0];")
    lines.append("x q[1];")
    lines.append("h q[2];")
    lines.append("ccx q[0], q[1], q[2];")
    lines.append("h q[2];")
    lines.append("x q[0];")
    lines.append("x q[1];")
    # diffusion
    for i in range(3):
        lines.append(f"h q[{i}];")
    lines.append("x q[0];")
    lines.append("x q[1];")
    lines.append("x q[2];")
    lines.append("h q[2];")
    lines.append("ccx q[0], q[1], q[2];")
    lines.append("h q[2];")
    lines.append("x q[0];")
    lines.append("x q[1];")
    lines.append("x q[2];")
    for i in range(3):
        lines.append(f"h q[{i}];")
    lines.append("measure q -> c;")
    return "\n".join(lines)


def random_circuit(seed: int, n: int = 5, depth: int = 14) -> str:
    """白名单 12 门随机电路（含全部门类型），带固定种子可复现。"""
    rng = random.Random(seed)
    singles = ["h", "x", "s", "sdg", "t", "tdg"]
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";',
             f"qreg q[{n}];", f"creg c[{n}];"]
    for _ in range(depth):
        kind = rng.random()
        if kind < 0.45:
            g = rng.choice(singles + ["rz", "ry"])
            q = rng.randrange(n)
            if g in ("rz", "ry"):
                lines.append(f"{g}({rng.uniform(-math.pi, math.pi):.8f}) q[{q}];")
            else:
                lines.append(f"{g} q[{q}];")
        elif kind < 0.75:
            a, b = rng.sample(range(n), 2)
            g = rng.choice(["cx", "swap", "cu1"])
            if g == "cu1":
                lines.append(f"cu1({rng.uniform(-math.pi, math.pi):.8f}) q[{a}], q[{b}];")
            else:
                lines.append(f"{g} q[{a}], q[{b}];")
        else:
            a, b, c = rng.sample(range(n), 3)
            lines.append(f"ccx q[{a}], q[{b}], q[{c}];")
    lines.append("measure q -> c;")
    return "\n".join(lines)


# --- 验证 --------------------------------------------------------------------

def check(label: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  [PASS] {label}")
    else:
        FAILED += 1
        print(f"  [FAIL] {label} — {detail}")


def verify_circuit(name: str, qasm: str, targets=("spinq", "originq", "braket"),
                   shots: int = 8192) -> None:
    expected = reference_simulate(qasm, shots)
    for target in targets:
        try:
            result = adapter.run(qasm, target, shots)
            observed = {k: v / shots for k, v in result["counts"].items()}
            fid = hellinger(observed, expected)
            check(f"{name}:{target}", fid >= 0.97,
                  f"fidelity={fid:.4f} observed={observed}")
        except Exception as exc:
            check(f"{name}:{target}", False, f"{type(exc).__name__}: {exc}")


def main() -> int:
    print("=" * 66)
    print("LoomQ L1 隐藏电路预演（numpy 参考模拟器交叉验证）")
    print("=" * 66)

    print("\n[1] 公开电路（回归）")
    verify_circuit("bell", bell())
    verify_circuit("ghz3", ghz(3))

    print("\n[2] GHZ-5（隐藏集 GHZ-5）")
    verify_circuit("ghz5", ghz(5))

    print("\n[3] QFT-4（隐藏集：h/cu1/swap）")
    verify_circuit("qft4", qft4())

    print("\n[4] Grover-3（隐藏集：h/x/ccx 相位翻转）")
    verify_circuit("grover3", grover3())

    print("\n[5] 随机电路 ×3（隐藏集 Random-Circuit，含全部 12 门）")
    for seed in (1, 2, 3):
        verify_circuit(f"random{seed}", random_circuit(seed))

    print("\n" + "=" * 66)
    print(f"结果：{PASSED} passed, {FAILED} failed")
    print("=" * 66)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
