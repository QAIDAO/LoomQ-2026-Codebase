#!/usr/bin/env python3
"""L1 通用中间层 · 验收测试

为什么公开自测不够用：Starter Kit 只给了 Bell 和 GHZ-3 两个电路，
它们的结果（`00`/`11`、`000`/`111`）**都是回文串**——比特顺序整个反过来，
输出一模一样。所以位序写错了，公开自测照样满分，隐藏电路上却会全灭。

这里造了五道关卡，每一道都针对一类公开自测查不出来的错：

  A 转译回环   ── spinq 的产物在本机跑不了，改用"解析回来必须一模一样"来验
  B 位序       ── 用非对称电路和错位测量，逼出比特顺序问题
  C 自逆电路   ── 随机造一段电路 U，接上它的逆 U†，答案必然是初态。★ 主力
  D 跨后端对拍 ── 同一个电路在两家独立 SDK 上分布必须一致
  E 结果格式   ── 直接调官方 evaluator 的 Schema 校验

★ C 为什么是主力：任何电路接上自己的逆，结果**确定**（概率 1），不需要参考答案。
  12 个门的逆全都还在 12 门白名单里（s↔sdg、t↔tdg、rz(θ)↔rz(-θ)……），
  所以这条路能把所有门、所有等价分解、所有相位一次性覆盖掉。
  相位错了、分解写反了，末态就回不到初态——而这正是"模长对、相位错"这类
  最阴的 bug 唯一会露馅的地方。

用法：

    python3 starter_kit/tools/verify_l1.py                 # 默认 40 道随机电路
    python3 starter_kit/tools/verify_l1.py --cases 200     # 加大强度
    python3 starter_kit/tools/verify_l1.py --seed 7        # 复现某一次
"""

import argparse
import math
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from starter_kit import adapter  # noqa: E402
from starter_kit.evaluator import calculate_hellinger_fidelity, validate_schema  # noqa: E402
from starter_kit.loomq import qasm_parser  # noqa: E402
from starter_kit.tools.reference_simulator import exact_distribution  # noqa: E402

RUNNABLE_TARGETS = ("braket", "originq")
ALL_TARGETS = ("spinq", "originq", "braket")
PI = math.pi

failures = []


def fail(section, message):
    failures.append("[%s] %s" % (section, message))
    print("  ❌ %s" % message)


def ok(message):
    print("  ✅ %s" % message)


def header(text):
    print("\n" + "=" * 68)
    print(text)
    print("=" * 68)


def build_qasm(n_qubits, body_lines, n_clbits=None, measures=None):
    n_clbits = n_qubits if n_clbits is None else n_clbits
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % n_qubits,
        "creg c[%d];" % n_clbits,
    ]
    lines += body_lines
    if measures is None:
        measures = [(i, i) for i in range(min(n_qubits, n_clbits))]
    lines += ["measure q[%d] -> c[%d];" % (q, c) for q, c in measures]
    return "\n".join(lines) + "\n"


# ==========================================================================
# A · 转译回环
# ==========================================================================


def section_a():
    header("A · 转译回环：三个后端都能出产物；spinq 产物解析回来必须等价")

    source = build_qasm(
        3,
        [
            "h q[0];",
            "sdg q[1];",
            "tdg q[2];",
            "rz(pi/4) q[0];",
            "ry(-pi/3) q[1];",
            "cx q[0], q[1];",
            "cu1(pi/2) q[1], q[2];",
            "swap q[0], q[2];",
            "ccx q[0], q[1], q[2];",
        ],
    )

    for target in ALL_TARGETS:
        try:
            text = adapter.transpile(source, target)
        except Exception as exc:  # noqa: BLE001
            fail("A", "transpile(%s) 抛异常：%s: %s" % (target, type(exc).__name__, exc))
            continue
        if not isinstance(text, str) or not text.strip():
            fail("A", "transpile(%s) 返回空产物" % target)
        else:
            ok("transpile(%s) 产出 %d 行" % (target, len(text.strip().splitlines())))

    # spinq 的产物是 OpenQASM 2.0，可以用我们自己的解析器读回来对比。
    # 这是唯一能验证 spinq 输出正确性的手段（本机跑不了 spinqit）。
    original = qasm_parser.parse(source)
    reparsed = qasm_parser.parse(adapter.transpile(source, "spinq"))
    if original.num_qubits != reparsed.num_qubits or original.num_clbits != reparsed.num_clbits:
        fail("A", "spinq 回环后寄存器规模变了")
    elif len(original.ops) != len(reparsed.ops):
        fail("A", "spinq 回环后操作数变了：%d -> %d" % (len(original.ops), len(reparsed.ops)))
    else:
        mismatched = [
            (a, b)
            for a, b in zip(original.ops, reparsed.ops)
            if type(a) is not type(b)
            or getattr(a, "name", None) != getattr(b, "name", None)
            or getattr(a, "qubits", None) != getattr(b, "qubits", None)
            or any(
                abs(x - y) > 1e-12
                for x, y in zip(getattr(a, "params", ()), getattr(b, "params", ()))
            )
        ]
        if mismatched:
            fail("A", "spinq 回环后有 %d 处操作对不上，例如 %r" % (len(mismatched), mismatched[0]))
        else:
            ok("spinq 产物解析回来与原电路逐条一致（%d 个操作）" % len(original.ops))

    # 再狠一步：把 spinq 的产物当作输入，喂给能跑的后端，结果必须与原电路一致
    for target in RUNNABLE_TARGETS:
        try:
            direct = adapter.run(source, target, 4096)["counts"]
            relayed = adapter.run(adapter.transpile(source, "spinq"), target, 4096)["counts"]
        except Exception as exc:  # noqa: BLE001
            fail("A", "spinq 产物转跑 %s 失败：%s: %s" % (target, type(exc).__name__, exc))
            continue
        fidelity = calculate_hellinger_fidelity(
            {k: v / 4096 for k, v in direct.items()}, {k: v / 4096 for k, v in relayed.items()}
        )
        if fidelity < 0.97:
            fail("A", "spinq 产物在 %s 上与原电路分布不符（保真度 %.4f）" % (target, fidelity))
        else:
            ok("spinq 产物喂给 %s 与原电路分布一致（保真度 %.4f）" % (target, fidelity))


# ==========================================================================
# B · 位序
# ==========================================================================


def section_b():
    header("B · 位序：非对称电路 + 错位测量（公开电路查不出这一类错）")

    cases = [
        ("x q[0] 两比特", build_qasm(2, ["x q[0];"]), "01"),
        ("x q[1] 两比特", build_qasm(2, ["x q[1];"]), "10"),
        ("x q[0] 三比特", build_qasm(3, ["x q[0];"]), "001"),
        ("x q[2] 三比特", build_qasm(3, ["x q[2];"]), "100"),
        ("x q[0]+q[2] 三比特", build_qasm(3, ["x q[0];", "x q[2];"]), "101"),
        ("x q[0..2] 四比特", build_qasm(4, ["x q[0];", "x q[1];", "x q[2];"]), "0111"),
        # 错位测量：q[0] 测进 c[2]，q[2] 测进 c[0]
        (
            "错位测量 q0->c2 / q2->c0",
            build_qasm(3, ["x q[0];"], measures=[(0, 2), (1, 1), (2, 0)]),
            "001"[::-1],
        ),
    ]

    for target in RUNNABLE_TARGETS:
        for label, source, expected in cases:
            try:
                counts = adapter.run(source, target, 256)["counts"]
            except Exception as exc:  # noqa: BLE001
                fail("B", "%s / %s 抛异常：%s: %s" % (target, label, type(exc).__name__, exc))
                continue
            if counts != {expected: 256}:
                fail("B", "%s / %s 应为 {%r: 256}，实际 %r" % (target, label, expected, counts))
            else:
                ok("%s / %-24s -> %s" % (target, label, expected))


# ==========================================================================
# C · 自逆电路（主力）
# ==========================================================================

INVERSE = {
    "h": ("h", lambda p: p),
    "x": ("x", lambda p: p),
    "s": ("sdg", lambda p: p),
    "sdg": ("s", lambda p: p),
    "t": ("tdg", lambda p: p),
    "tdg": ("t", lambda p: p),
    "rz": ("rz", lambda p: (-p[0],)),
    "ry": ("ry", lambda p: (-p[0],)),
    "cx": ("cx", lambda p: p),
    "cu1": ("cu1", lambda p: (-p[0],)),
    "swap": ("swap", lambda p: p),
    "ccx": ("ccx", lambda p: p),
}

ARITY = {
    "h": (0, 1), "x": (0, 1), "s": (0, 1), "sdg": (0, 1), "t": (0, 1), "tdg": (0, 1),
    "rz": (1, 1), "ry": (1, 1), "cx": (0, 2), "cu1": (1, 2), "swap": (0, 2), "ccx": (0, 3),
}


def render_gate(name, params, qubits):
    text = name
    if params:
        text += "(%s)" % ", ".join("%.17g" % p for p in params)
    return "%s %s;" % (text, ", ".join("q[%d]" % index for index in qubits))


def random_gate(rng, n_qubits):
    choices = [g for g, (_, nq) in ARITY.items() if nq <= n_qubits]
    name = rng.choice(choices)
    n_params, n_gate_qubits = ARITY[name]
    params = tuple(rng.uniform(-PI, PI) for _ in range(n_params))
    qubits = tuple(rng.sample(range(n_qubits), n_gate_qubits))
    return name, params, qubits


def section_c(cases, seed, shots):
    header("C · 自逆电路：随机造 U，接上 U†，结果必然回到初态（答案是确定的）")

    rng = random.Random(seed)
    checked = 0
    for number in range(1, cases + 1):
        n_qubits = rng.randint(1, 4)
        # 随机的非对称初态，顺便再考一次位序
        prep = [index for index in range(n_qubits) if rng.random() < 0.5]
        body = ["x q[%d];" % index for index in prep]

        forward = [random_gate(rng, n_qubits) for _ in range(rng.randint(1, 8))]
        body += [render_gate(*gate) for gate in forward]
        for name, params, qubits in reversed(forward):
            inverse_name, transform = INVERSE[name]
            body.append(render_gate(inverse_name, transform(params), qubits))

        expected = "".join("1" if index in prep else "0" for index in range(n_qubits - 1, -1, -1))
        source = build_qasm(n_qubits, body)

        for target in RUNNABLE_TARGETS:
            try:
                counts = adapter.run(source, target, shots)["counts"]
            except Exception as exc:  # noqa: BLE001
                fail("C", "第 %d 道 / %s 抛异常：%s: %s" % (number, target, type(exc).__name__, exc))
                print(source)
                continue
            checked += 1
            if counts != {expected: shots}:
                fail("C", "第 %d 道 / %s 应为 {%r: %d}，实际 %r" % (number, target, expected, shots, counts))
                print(source)

    if not [f for f in failures if f.startswith("[C]")]:
        ok("%d 道随机电路 × %d 次执行，全部精确回到初态" % (cases, checked))


# ==========================================================================
# D · 跨后端对拍
# ==========================================================================


def section_d(cases, seed, shots):
    header("D · 对精确参考：随机电路，两个后端各自与自算的精确分布比对")
    print("   （不用两个后端互比：解析器读错门时两边会一致地错，互比查不出来；")
    print("     而且两份采样噪声叠加，阈值也不再是官方那个 0.97 的含义）")

    rng = random.Random(seed + 1)
    worst = {target: (1.0, "") for target in RUNNABLE_TARGETS}

    for number in range(1, cases + 1):
        n_qubits = rng.randint(2, 4)
        body = ["h q[%d];" % index for index in range(n_qubits)]
        body += [render_gate(*random_gate(rng, n_qubits)) for _ in range(rng.randint(2, 8))]
        source = build_qasm(n_qubits, body)

        try:
            ideal = exact_distribution(qasm_parser.parse(source))
        except Exception as exc:  # noqa: BLE001
            fail("D", "第 %d 道参考模拟器抛异常：%s: %s" % (number, type(exc).__name__, exc))
            print(source)
            continue

        for target in RUNNABLE_TARGETS:
            try:
                counts = adapter.run(source, target, shots)["counts"]
            except Exception as exc:  # noqa: BLE001
                fail("D", "第 %d 道 / %s 抛异常：%s: %s" % (number, target, type(exc).__name__, exc))
                print(source)
                continue
            observed = {k: v / shots for k, v in counts.items()}
            fidelity = calculate_hellinger_fidelity(observed, ideal)
            if fidelity < worst[target][0]:
                worst[target] = (fidelity, source)
            if fidelity < 0.97:
                fail("D", "第 %d 道 / %s 与精确分布不符（保真度 %.4f）" % (number, target, fidelity))
                print(source)
                print("  精确  :", {k: round(v, 4) for k, v in sorted(ideal.items())})
                print("  %-7s:" % target, dict(sorted(counts.items())))

    if not [f for f in failures if f.startswith("[D]")]:
        for target in RUNNABLE_TARGETS:
            ok("%s：%d 道随机电路全部达标，最低保真度 %.5f" % (target, cases, worst[target][0]))


# ==========================================================================
# E · 结果格式 + 公开电路理想分布
# ==========================================================================


def section_e():
    header("E · Schema 合法性 + 手写答案的电路（同时校验参考模拟器本身）")

    base = os.path.join(_REPO_ROOT, "starter_kit", "circuits")
    ideals = {"bell.qasm": {"00": 0.5, "11": 0.5}, "ghz3.qasm": {"000": 0.5, "111": 0.5}}
    ghz5 = build_qasm(5, ["h q[0];"] + ["cx q[%d], q[%d];" % (i, i + 1) for i in range(4)])

    jobs = [(name, open(os.path.join(base, name), encoding="utf-8").read(), ideal)
            for name, ideal in sorted(ideals.items())]
    jobs.append(("ghz5(自造)", ghz5, {"00000": 0.5, "11111": 0.5}))
    # 下面这些答案是人手推的，用来钉住参考模拟器和解析器：
    # 连做两次 H 必然回到 0（量子比特不是骰子的直接证据）；
    # cu1 只在两个比特都是 1 时加相位，所以对基态毫无影响。
    jobs.append(("h;h 回到 0", build_qasm(1, ["h q[0];", "h q[0];"]), {"0": 1.0}))
    jobs.append(("x;h;h 回到 1", build_qasm(1, ["x q[0];", "h q[0];", "h q[0];"]), {"1": 1.0}))
    jobs.append(
        ("cu1 对基态无效", build_qasm(2, ["x q[0];", "cu1(pi/3) q[0], q[1];"]), {"01": 1.0})
    )
    jobs.append(
        ("swap 换位", build_qasm(2, ["x q[0];", "swap q[0], q[1];"]), {"10": 1.0})
    )
    jobs.append(
        ("ccx 双控才翻", build_qasm(3, ["x q[0];", "x q[1];", "ccx q[0], q[1], q[2];"]), {"111": 1.0})
    )
    jobs.append(
        ("ccx 单控不翻", build_qasm(3, ["x q[0];", "ccx q[0], q[1], q[2];"]), {"001": 1.0})
    )

    # 先用这些手写答案校验参考模拟器自己
    for label, source, ideal in jobs:
        computed = exact_distribution(qasm_parser.parse(source))
        fidelity = calculate_hellinger_fidelity(computed, ideal)
        if fidelity < 0.9999:
            fail("E", "参考模拟器在 %s 上与手写答案不符：%r" % (label, computed))
    if not [f for f in failures if f.startswith("[E]")]:
        ok("参考模拟器在 %d 道手写答案上全部精确吻合" % len(jobs))

    for target in RUNNABLE_TARGETS:
        for label, source, ideal in jobs:
            try:
                payload = adapter.run(source, target, 8192)
            except Exception as exc:  # noqa: BLE001
                fail("E", "%s / %s 抛异常：%s: %s" % (target, label, type(exc).__name__, exc))
                continue
            valid, reason = validate_schema(payload)
            if not valid:
                fail("E", "%s / %s Schema 不合法：%s" % (target, label, reason))
                continue
            observed = {k: v / 8192 for k, v in payload["counts"].items()}
            fidelity = calculate_hellinger_fidelity(observed, ideal)
            if fidelity < 0.97:
                fail("E", "%s / %s 保真度 %.4f 未达标" % (target, label, fidelity))
            else:
                ok("%s / %-12s Schema 合法，保真度 %.5f" % (target, label, fidelity))


# ==========================================================================


def main():
    parser = argparse.ArgumentParser(description="L1 通用中间层验收测试")
    parser.add_argument("--cases", type=int, default=40, help="C/D 两节各跑多少道随机电路")
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument("--shots", type=int, default=512)
    args = parser.parse_args()

    section_a()
    section_b()
    section_c(args.cases, args.seed, args.shots)
    # D 节用官方评测同样的 8192 shots，这样看到的保真度余量才是真实余量
    section_d(max(args.cases // 2, 4), args.seed, 8192)
    section_e()

    print("\n" + "=" * 68)
    if failures:
        print("失败 %d 项：" % len(failures))
        for item in failures:
            print("  " + item)
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
