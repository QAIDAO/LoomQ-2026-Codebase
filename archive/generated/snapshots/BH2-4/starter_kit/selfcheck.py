#!/usr/bin/env python3
"""LoomQ 自建回归：官方 8 电路全集 + 随机电路，双层校验。

Tier A（解析解对拍）：Bell/GHZ/QFT-4/Grover-3 与手推理想分布算 Hellinger
保真度（8192 shots 采样，阈值 0.97，与正式评测同口径）。
Tier B（回环一致）：每个电路 transpile 到三后端；spinq 产物重新解析再模拟，
概率分布须与原电路一致（误差 <1e-9）；braket/originq 产物做结构校验。

用法：python3 starter_kit/selfcheck.py   （退出码 0=全过）
"""

from __future__ import annotations

import math
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from loomq import parse_qasm, probabilities, sample_counts, simulate, transpile_to
    from loomq.ir import WHITELIST
except ImportError:
    from starter_kit.loomq import (parse_qasm, probabilities, sample_counts,
                                   simulate, transpile_to)
    from starter_kit.loomq.ir import WHITELIST

SHOTS = 8192
FIDELITY_THRESHOLD = 0.97
failures = []


def check(case_id: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print("[%s] %s%s" % (status, case_id, (": " + detail) if detail else ""))
    if not ok:
        failures.append(case_id)


def hellinger_fidelity(observed: dict, expected: dict) -> float:
    states = set(observed) | set(expected)
    distance = math.sqrt(
        sum((math.sqrt(observed.get(s, 0.0)) - math.sqrt(expected.get(s, 0.0))) ** 2
            for s in states)) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - distance))


# ---- 官方 8 电路全集（含隐藏档位的自建等价物） ----

def _header(n: int) -> str:
    return "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[%d];\ncreg c[%d];\n" % (n, n)


def _full_measure(n: int) -> str:
    return "measure q -> c;\n"


def qasm_bell() -> str:
    return (_header(2) + "h q[0];\ncx q[0], q[1];\n" + _full_measure(2))


def qasm_ghz(n: int) -> str:
    body = "h q[0];\n" + "".join("cx q[%d], q[%d];\n" % (i, i + 1)
                                 for i in range(n - 1))
    return _header(n) + body + _full_measure(n)


def qasm_qft4() -> str:
    lines = ["h q[3];",
             "cu1(pi/2) q[3], q[2];", "cu1(pi/4) q[3], q[1];", "cu1(pi/8) q[3], q[0];",
             "h q[2];",
             "cu1(pi/2) q[2], q[1];", "cu1(pi/4) q[2], q[0];",
             "h q[1];", "cu1(pi/2) q[1], q[0];",
             "h q[0];",
             "swap q[0], q[3];", "swap q[1], q[2];"]
    return _header(4) + "\n".join(lines) + "\n" + _full_measure(4)


def qasm_grover3() -> str:
    """3 比特 Grover，标记 |111>，1 次迭代：P(111)=sin²(3·asin(1/√8))≈0.781。"""
    lines = ["h q[0];", "h q[1];", "h q[2];",
             "h q[2];", "ccx q[0], q[1], q[2];", "h q[2];",
             "h q[0];", "h q[1];", "h q[2];",
             "x q[0];", "x q[1];", "x q[2];",
             "h q[2];", "ccx q[0], q[1], q[2];", "h q[2];",
             "x q[0];", "x q[1];", "x q[2];",
             "h q[0];", "h q[1];", "h q[2];"]
    return _header(3) + "\n".join(lines) + "\n" + _full_measure(3)


def qasm_random(seed: int, n: int = None, n_ops: int = None) -> str:
    rng = random.Random(seed)
    n = n or rng.randint(2, 5)
    n_ops = n_ops or rng.randint(4, 14)
    lines = []
    one_q = ["h", "x", "s", "sdg", "t", "tdg"]
    for _ in range(n_ops):
        roll = rng.random()
        if roll < 0.45:
            lines.append("%s q[%d];" % (rng.choice(one_q), rng.randrange(n)))
        elif roll < 0.6:
            lines.append("%s(%.6f) q[%d];" % (rng.choice(["rz", "ry"]),
                                              rng.uniform(-3, 3), rng.randrange(n)))
        elif roll < 0.8 and n >= 2:
            a, b = rng.sample(range(n), 2)
            lines.append("%s q[%d], q[%d];" % (rng.choice(["cx", "swap"]), a, b))
        elif roll < 0.9 and n >= 2:
            a, b = rng.sample(range(n), 2)
            lines.append("cu1(%.6f) q[%d], q[%d];" % (rng.uniform(-3, 3), a, b))
        elif n >= 3:
            a, b, c = rng.sample(range(n), 3)
            lines.append("ccx q[%d], q[%d], q[%d];" % (a, b, c))
    return _header(n) + "\n".join(lines) + "\n" + _full_measure(n)


OFFICIAL_SUITE = {
    "bell": qasm_bell(),
    "ghz3": qasm_ghz(3),
    "ghz5": qasm_ghz(5),
    "qft4": qasm_qft4(),
    "grover3": qasm_grover3(),
    "random1": qasm_random(101),
    "random2": qasm_random(202),
    "random3": qasm_random(303),
}

# ---- Tier A：解析解理想分布 ----

def analytic_expectations() -> dict:
    expected = {}
    expected["bell"] = {"00": 0.5, "11": 0.5}
    expected["ghz3"] = {"000": 0.5, "111": 0.5}
    expected["ghz5"] = {"00000": 0.5, "11111": 0.5}
    expected["qft4"] = {"%04x" % 0: 0}  # 占位，下面重算为均匀分布
    expected["qft4"] = {format(i, "04b"): 1 / 16 for i in range(16)}
    theta = math.asin(1 / math.sqrt(8))
    p_marked = math.sin(3 * theta) ** 2
    expected["grover3"] = {format(i, "03b"): (p_marked if i == 7
                                              else (1 - p_marked) / 7)
                           for i in range(8)}
    return expected


def tier_a() -> None:
    analytic = analytic_expectations()
    rng = random.Random(20260815)
    for name, qasm in OFFICIAL_SUITE.items():
        if name.startswith("random"):
            continue
        circuit = parse_qasm(qasm)
        counts = sample_counts(circuit, SHOTS, rng=rng)
        observed = {k: v / SHOTS for k, v in counts.items()}
        fidelity = hellinger_fidelity(observed, analytic[name])
        check("tierA:%s" % name, fidelity >= FIDELITY_THRESHOLD,
              "fidelity=%.4f" % fidelity)


# ---- Tier B：三后端回环/结构校验 ----

_BRAKET_OK = re.compile(r"^OPENQASM 3\.0;", re.M)
_ORIGINQ_OK = re.compile(r"^QINIT \d+\nCREG \d+$", re.M)
_ORIGINQ_GATES = {"H", "X", "S", "SDAG", "T", "TDAG", "RY", "RZ", "CNOT",
                  "CU1", "CR", "SWAP", "TOFFOLI", "CCX", "MEASURE"}


def tier_b_one(name: str, qasm: str) -> None:
    circuit = parse_qasm(qasm)
    probs_ref = probabilities(simulate(circuit))
    # spinq：回环解析必须分布一致
    spinq_out = transpile_to(circuit, "spinq")
    reparsed = parse_qasm(spinq_out)
    probs_rt = probabilities(simulate(reparsed))
    if len(probs_rt) != len(probs_ref):
        check("tierB:%s:spinq" % name, False, "维度不一致")
    else:
        diff = max(abs(a - b) for a, b in zip(probs_ref, probs_rt))
        check("tierB:%s:spinq" % name, diff < 1e-9, "max_prob_diff=%.2e" % diff)
    # braket：结构 + 门名合法
    braket_out = transpile_to(circuit, "braket")
    gates = set(re.findall(r"^(\w+)[\s(]", braket_out, re.M)) - {
        "OPENQASM", "include", "qubit", "bit", "measure"}
    check("tierB:%s:braket" % name,
          bool(_BRAKET_OK.search(braket_out))
          and all(g in {"h", "x", "s", "sdg", "t", "tdg", "ry", "rz", "cx",
                        "cnot", "cu1", "cp", "swap", "ccx"} for g in gates),
          "gates=%s" % sorted(gates))
    # originq：结构 + 门名合法
    originq_out = transpile_to(circuit, "originq")
    ogates = set(re.findall(r"^([A-Z][A-Z0-9]*)[\s(]", originq_out, re.M)) - {
        "QINIT", "CREG"}
    check("tierB:%s:originq" % name,
          bool(_ORIGINQ_OK.search(originq_out))
          and ogates <= _ORIGINQ_GATES,
          "gates=%s" % sorted(ogates))


def tier_b() -> None:
    for name, qasm in OFFICIAL_SUITE.items():
        tier_b_one(name, qasm)
    # 随机电路扩展回归
    for seed in range(1, 31):
        tier_b_one("rand%02d" % seed, qasm_random(seed * 7919))


def main() -> int:
    tier_a()
    tier_b()
    total_a = 5
    print("---")
    print("自建回归：%d 项失败" % len(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
