#!/usr/bin/env python3
"""L3 混合编译器 · 随机对拍测试（自己给自己出考题）

为什么需要它：赛题写明 L3 是"随机生成用例 + 穷举注入所有测量值组合 +
完全确定性判分"。公开自测只给了一个用例，过了不说明任何问题。
所以我们自己造一个同样的考场，先把自己考到全对。

怎么保证"考官"是可信的：
每道随机题目会被同时写成两种文本——

    Hybrid-QASM 版本  ->  交给我们的编译器  ->  汇编  ->  官方模拟器执行  ->  结果 A
    等价的 Python 版本 ->  交给 CPython 直接执行                       ->  结果 B

A 和 B 必须完全一致。用 Python 当参考答案，是因为这个迷你文法的写法
（赋值、if/else、+ - == !=、括号、优先级、左结合）和 Python 恰好完全一致，
而 CPython 显然不会跟我们犯同一个错误——这是一个独立的对照组，
连"我们的语法分析器读错了结构"这类 bug 也能抓出来。

用法：

    python3 starter_kit/tools/fuzz_l3.py                 # 默认 2000 道随机题
    python3 starter_kit/tools/fuzz_l3.py --cases 20000   # 加大强度
    python3 starter_kit/tools/fuzz_l3.py --seed 7        # 复现某一次
"""

import argparse
import itertools
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from starter_kit import adapter  # noqa: E402
from starter_kit.riscv_emulator import TinyRISCVEmulator  # noqa: E402

MEASURE_BASE = 10
MAX_REG = 9
MAX_BITS = 4  # 穷举注入是 2^n，控制在合理规模
LITERALS = [0, 1, 2, 3, 5, 7, 10, 42, 100, 255, -1, -3, -17, 1000, 65536]


# ==========================================================================
# 随机题目生成：先造一棵结构树，再用两套渲染器写成两种语言
# ==========================================================================
#
# 节点形状（这是 fuzzer 自己的表示，故意不复用编译器的语法树，
# 否则"生成"和"解析"共用同一份代码，解析的 bug 就测不出来了）：
#
#   ("num",  值)
#   ("reg",  1..9)
#   ("bit",  0..n-1)
#   ("neg",  子表达式)
#   ("chain", [首项, (运算符, 项), (运算符, 项), ...])   # 平铺，考左结合
#   ("cmp",  运算符, 左, 右)
#   ("assign", 目标寄存器, 表达式)
#   ("if", 条件, then 语句表, else 语句表 or None)


def random_expr(rng, n_bits, depth=0):
    choices = ["num", "reg"]
    if n_bits:
        choices.append("bit")
    if depth < 2:
        choices += ["chain", "chain", "neg"]

    kind = rng.choice(choices)
    if kind == "num":
        return ("num", rng.choice(LITERALS))
    if kind == "reg":
        return ("reg", rng.randint(1, MAX_REG))
    if kind == "bit":
        return ("bit", rng.randrange(n_bits))
    if kind == "neg":
        return ("neg", random_expr(rng, n_bits, depth + 1))

    terms = [random_expr(rng, n_bits, depth + 1)]
    for _ in range(rng.randint(1, 3)):
        terms.append((rng.choice(["+", "-"]), random_expr(rng, n_bits, depth + 1)))
    return ("chain", terms)


def random_condition(rng, n_bits):
    return ("cmp", rng.choice(["==", "!="]), random_expr(rng, n_bits), random_expr(rng, n_bits))


def random_statements(rng, n_bits, depth=0):
    statements = []
    for _ in range(rng.randint(1, 3 if depth else 4)):
        if depth < 3 and rng.random() < (0.45 if depth < 2 else 0.2):
            then_body = random_statements(rng, n_bits, depth + 1)
            else_body = random_statements(rng, n_bits, depth + 1) if rng.random() < 0.6 else None
            statements.append(("if", random_condition(rng, n_bits), then_body, else_body))
        else:
            statements.append(("assign", rng.randint(1, MAX_REG), random_expr(rng, n_bits)))
    return statements


# ---- 渲染器一：Hybrid-QASM 经典块 ----------------------------------------


def render_hybrid(statements, indent=1):
    pad = "  " * indent
    lines = []
    for statement in statements:
        if statement[0] == "assign":
            lines.append("%sr%d = %s;" % (pad, statement[1], render_expr(statement[2], "hybrid")))
        else:
            _, cond, then_body, else_body = statement
            lines.append("%sif (%s) {" % (pad, render_expr(cond, "hybrid")))
            lines.extend(render_hybrid(then_body, indent + 1))
            if else_body:
                lines.append("%s} else {" % pad)
                lines.extend(render_hybrid(else_body, indent + 1))
            lines.append("%s}" % pad)
    return lines


# ---- 渲染器二：等价的 Python 程序（参考答案）------------------------------


def render_python(statements, indent=0):
    pad = "    " * indent
    lines = []
    for statement in statements:
        if statement[0] == "assign":
            lines.append("%sr%d = %s" % (pad, statement[1], render_expr(statement[2], "python")))
        else:
            _, cond, then_body, else_body = statement
            lines.append("%sif %s:" % (pad, render_expr(cond, "python")))
            lines.extend(render_python(then_body, indent + 1))
            if else_body:
                lines.append("%selse:" % pad)
                lines.extend(render_python(else_body, indent + 1))
    return lines


def render_expr(node, dialect, need_parens=False):
    kind = node[0]

    if kind == "num":
        text = str(node[1])
        return "(%s)" % text if node[1] < 0 and (need_parens or dialect == "python") else text

    if kind == "reg":
        return "r%d" % node[1]

    if kind == "bit":
        return ("c[%d]" if dialect == "hybrid" else "c%d") % node[1]

    if kind == "neg":
        text = "-" + render_expr(node[1], dialect, need_parens=True)
        return "(%s)" % text if need_parens else text

    if kind == "chain":
        # 平铺不加括号，两种语言的 + - 都是左结合、优先级相同
        parts = [render_expr(node[1][0], dialect, need_parens=True)]
        for operator, term in node[1][1:]:
            parts.append(operator)
            parts.append(render_expr(term, dialect, need_parens=True))
        text = " ".join(parts)
        return "(%s)" % text if need_parens else text

    if kind == "cmp":
        return "%s %s %s" % (
            render_expr(node[2], dialect, need_parens=True),
            node[1],
            render_expr(node[3], dialect, need_parens=True),
        )

    raise TypeError("未知节点：%r" % (node,))


# ---- 把经典块包成一份完整的 Hybrid-QASM 文档 -------------------------------


def build_document(rng, statements, n_bits):
    """随机在量子语句之间插入经典块，顺便随机加注释、随机用不用花括号缩进。"""
    n_qubits = max(1, n_bits)
    quantum_head = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % n_qubits,
        "creg c[%d];" % max(1, n_bits),
    ]
    gates = ["h q[0];"]
    for bit in range(n_bits):
        gates.append("measure q[%d] -> c[%d];" % (bit % n_qubits, bit))
    tail_gates = ["cx q[0], q[%d];" % (n_qubits - 1)] if n_qubits > 1 else ["x q[0];"]

    classical_lines = ["classical {"] + render_hybrid(statements) + ["}"]
    if rng.random() < 0.3:
        classical_lines[0] = "classical {   // 经典控制块"
    if rng.random() < 0.2:
        classical_lines[-1] = "}  ;"

    body = quantum_head + gates + classical_lines + tail_gates
    if rng.random() < 0.25:
        body.insert(rng.randrange(len(quantum_head), len(body)), "// 随便一句注释")

    expected_ops = gates + tail_gates
    return "\n".join(body) + "\n", expected_ops


# ==========================================================================
# 判卷
# ==========================================================================


def python_reference(statements, bits):
    """用 CPython 执行等价程序，返回 r1..r9 的终态。"""
    namespace = {"r%d" % index: 0 for index in range(1, MAX_REG + 1)}
    namespace.update({"c%d" % index: value for index, value in bits.items()})
    source = "\n".join(render_python(statements)) or "pass"
    exec(compile(source, "<reference>", "exec"), {"__builtins__": {}}, namespace)
    return {index: namespace["r%d" % index] for index in range(1, MAX_REG + 1)}


def check_one(document, statements, n_bits, expected_ops):
    """编译一道题并穷举所有测量值组合，返回错误描述；全对时返回 None。"""
    quantum_ops, assembly = adapter.compile_hybrid(document)

    if not isinstance(quantum_ops, list) or not isinstance(assembly, str) or not assembly.strip():
        return "compile_hybrid 返回值形状不对"
    if quantum_ops != expected_ops:
        return "量子操作序列不符\n  期望 %r\n  实际 %r" % (expected_ops, quantum_ops)

    allowed = {"x%d" % index for index in range(1, MAX_REG + 1)}
    allowed |= {"x%d" % (MEASURE_BASE + bit) for bit in range(max(1, n_bits))}

    for combination in itertools.product((0, 1), repeat=n_bits):
        bits = dict(enumerate(combination))
        expected = python_reference(statements, bits)

        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        for bit, value in bits.items():
            emulator.set_register("x%d" % (MEASURE_BASE + bit), value)
        state = emulator.execute()

        for index in range(1, MAX_REG + 1):
            actual = state.get("x%d" % index, 0)
            if actual != expected[index]:
                return "测量值 %r 下 r%d 应为 %d，实际 %d" % (
                    combination,
                    index,
                    expected[index],
                    actual,
                )

        stray = sorted(set(state) - allowed)
        if stray:
            return "测量值 %r 下残留了不该有的寄存器：%s" % (combination, ", ".join(stray))

    return None


# ==========================================================================
# 固定回归用例：每次都跑，防止改代码把已经修好的坑又踩回去
# ==========================================================================

REGRESSION_CASES = [
    # 公开自测那一道
    (
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
classical { if (c[0] == 1) { r1 = 7; } else { r1 = 3; } }
""",
        {(0,): {1: 3}, (1,): {1: 7}},
    ),
    # 赛题第三节的语法示例（经典块夹在量子语句中间，带 // 注释）
    (
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q[0] -> c[0];
classical {                 // 经典控制块
  if (c[0] == 1) {
    r1 = 100;               // r1..r9 映射到 x1..x9
  } else {
    r1 = 10;
  }
  r1 = r1 + 5;
}
cx q[0], q[1];
""",
        {(0,): {1: 15}, (1,): {1: 105}},
    ),
    # 嵌套 if/else + else if 链
    (
        """OPENQASM 2.0;
qreg q[2];
creg c[2];
classical {
  if (c[0] == 1) {
    if (c[1] == 1) { r2 = 3; } else { r2 = 4; }
  } else if (c[1] != 0) {
    r2 = 5;
  } else {
    r2 = 6;
  }
}
""",
        {(0, 0): {2: 6}, (0, 1): {2: 5}, (1, 0): {2: 4}, (1, 1): {2: 3}},
    ),
    # 左结合：1 - 2 + 3 必须是 (1-2)+3 = 2，不是 1-(2+3) = -4
    (
        """OPENQASM 2.0;
qreg q[1];
creg c[1];
classical { r3 = 1 - 2 + 3; }
""",
        {(0,): {3: 2}, (1,): {3: 2}},
    ),
    # 没有 else 的分支 + 用测量位参与算术 + 一元负号 + 省略分号
    (
        """OPENQASM 2.0;
qreg q[1];
creg c[1];
classical {
  r4 = -5;
  if (c[0] != 0) { r4 = r4 + c[0] - -10 }
}
""",
        {(0,): {4: -5}, (1,): {4: 6}},
    ),
    # 多个经典块：寄存器状态要跨块延续
    (
        """OPENQASM 2.0;
qreg q[1];
creg c[1];
classical { r5 = 8; }
h q[0];
classical { r5 = r5 + c[0]; }
""",
        {(0,): {5: 8}, (1,): {5: 9}},
    ),
    # 空经典块也必须编译出可执行的产物
    (
        """OPENQASM 2.0;
qreg q[1];
creg c[1];
classical { }
""",
        {(0,): {}, (1,): {}},
    ),
]


def run_regressions():
    failures = []
    for number, (document, expectations) in enumerate(REGRESSION_CASES, start=1):
        try:
            _, assembly = adapter.compile_hybrid(document)
        except Exception as exc:  # noqa: BLE001
            failures.append("回归用例 %d 编译失败：%s: %s" % (number, type(exc).__name__, exc))
            continue
        for combination, expected in expectations.items():
            emulator = TinyRISCVEmulator()
            emulator.load_program(assembly)
            for bit, value in enumerate(combination):
                emulator.set_register("x%d" % (MEASURE_BASE + bit), value)
            state = emulator.execute()
            for index in range(1, MAX_REG + 1):
                want = expected.get(index, 0)
                got = state.get("x%d" % index, 0)
                if want != got:
                    failures.append(
                        "回归用例 %d 在测量值 %r 下 r%d 应为 %d，实际 %d"
                        % (number, combination, index, want, got)
                    )
    return failures


# ==========================================================================


def main():
    parser = argparse.ArgumentParser(description="L3 混合编译器随机对拍测试")
    parser.add_argument("--cases", type=int, default=2000, help="随机题目数量")
    parser.add_argument("--seed", type=int, default=20260802, help="随机种子，用于复现")
    parser.add_argument("--stop-after", type=int, default=3, help="报告多少个失败后停下")
    args = parser.parse_args()

    print("== 固定回归用例 ==")
    failures = run_regressions()
    for message in failures:
        print("  [FAIL] %s" % message)
    if not failures:
        print("  [PASS] %d 道全部通过" % len(REGRESSION_CASES))

    print("== 随机对拍（种子 %d，%d 道题）==" % (args.seed, args.cases))
    rng = random.Random(args.seed)
    bad = 0
    injections = 0

    for number in range(1, args.cases + 1):
        n_bits = rng.randint(1, MAX_BITS)
        statements = random_statements(rng, n_bits)
        document, expected_ops = build_document(rng, statements, n_bits)
        injections += 2**n_bits

        try:
            problem = check_one(document, statements, n_bits, expected_ops)
        except Exception as exc:  # noqa: BLE001
            problem = "抛出异常 %s: %s" % (type(exc).__name__, exc)

        if problem:
            bad += 1
            print("\n  [FAIL] 第 %d 道：%s" % (number, problem))
            print("  ---- 源码 ----\n%s" % document)
            print("  ---- 参考 Python ----\n%s" % "\n".join(render_python(statements)))
            _, assembly = adapter.compile_hybrid(document)
            print("  ---- 生成的汇编 ----\n%s" % assembly)
            if bad >= args.stop_after:
                print("  失败数已达 %d，提前停止" % bad)
                break

    total_failures = len(failures) + bad
    print(
        "\n结果：随机题 %d 道 / 注入组合 %d 次 / 失败 %d"
        % (min(number, args.cases), injections, total_failures)
    )
    return 1 if total_failures else 0


if __name__ == "__main__":
    sys.exit(main())
