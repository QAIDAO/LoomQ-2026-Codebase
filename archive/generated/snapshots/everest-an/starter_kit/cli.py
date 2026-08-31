#!/usr/bin/env python3
"""LoomQ interactive CLI: talk to a quantum computer in plain language.

A zero-dependency, novice-first command-line entry for the L2 agent:
every reply from the agent is verified locally through the L1 pipeline
and the resulting measurement distribution is visualized, so a user
with no quantum background gets immediate, honest feedback.

Run (from the repo root, with LOOMQ_LLM_* configured):

    python starter_kit/cli.py
    python starter_kit/cli.py --backend braket --shots 8192

Commands inside the REPL:
    help        show this guide
    circuit     print the last generated QASM
    native      print the transpiled target IR (spinq/originq/braket)
    quits/exit  leave
"""

import argparse
import os
import sys
import time

try:
    from . import adapter
    from .qasm_parser import parse_qasm2
    from .simulator import simulate
except ImportError:  # standalone-module fallback
    import adapter
    from qasm_parser import parse_qasm2
    from simulator import simulate

WELCOME = """
╭──────────────────────────────────────────────────────────────╮
│  LoomQ · 量子接入平权计划                                      │
│  用自然语言指挥量子计算机 —— 不需要任何量子背景                   │
│                                                              │
│  试试：                                                       │
│    · 生成一个 3 比特 GHZ 纠缠态                                 │
│    · 制备贝尔态 |Φ+>                                           │
│    · 运行一个 15 比特电路选哪个后端？                            │
│  输入 help 查看更多，quit 退出。                                │
╰──────────────────────────────────────────────────────────────╯
"""

HELP_TEXT = """
命令：
  help      显示本帮助
  tutorial  量子计算 101 速览（3 分钟看懂结果图）
  circuit   显示最近一次生成的 QASM
  native    显示最近电路转译到目标平台的原生代码
  quit      退出

后端：spinq / originq / braket（默认 braket，本地模拟器免费无需账号）
"""

TUTORIAL_TEXT = """
量子计算 101 · 3 分钟速览
────────────────────────────────────────
1. 比特 vs 量子比特（qubit）
   经典比特只有 0 或 1；量子比特可以处于「叠加态」——
   同时是 0 和 1 的某种组合，测量时才"落地"成 0 或 1。

2. 叠加与概率
   一个 qubit 有概率 p0 测到 0，p1 测到 1（p0 + p1 = 1）。
   我们 CLI 里画的分布图（# 条）就是多次测量的统计结果。

3. 纠缠（最反直觉的部分）
   两个 qubit 纠缠后，它们的状态"绑定"在一起：
   测第一个必得第二个——比如贝尔态，要么都是 0、要么都是 1，
   绝不出现 01 或 10。你在结果图里看到 00/11 各半就是它。

4. 门 = 对状态的旋转操作
   H（Hadamard）制造叠加；X 翻转；CX 制造纠缠；
   RZ/RY 旋转角度。电路就是这些门的序列。

5. 怎么读懂 CLI 的输出
   - 结果几乎全落在少数几个态上 → 确定性/制备成功
   - 结果均匀分散 → 叠加态或纠缠态的特征
   - 出现意料外的态 → 换句话问，或检查电路

6. 这跟你的生活有什么关系
   量子计算机擅长模拟自然、组合优化、密码学等。
   本工具让"不懂黑话的你"也能指挥它——这就是平权。
────────────────────────────────────────
输入 help 返回命令菜单。
"""

_BAR_WIDTH = 40


def render_counts(counts: dict, shots: int) -> str:
    """ASCII bar visualization of the measurement distribution."""
    total = max(1, shots)
    rows = []
    for state, count in sorted(counts.items(), key=lambda kv: -kv[1])[:8]:
        fraction = count / total
        bar = "#" * max(1, int(round(fraction * _BAR_WIDTH)))
        rows.append("  %s |%s| %5.1f%%  (%d/%d)" % (state, bar.ljust(_BAR_WIDTH), fraction * 100, count, shots))
    return "\n".join(rows)


def verify_and_explain(qasm: str, backend: str, shots: int) -> None:
    """Run the circuit locally and explain the outcome in plain terms."""
    try:
        circuit = parse_qasm2(qasm)
    except Exception as exc:
        print("  [!] 生成的电路无法解析：%s: %s" % (type(exc).__name__, exc))
        print("  提示：可以换种说法重试，例如「生成 2 比特贝尔态」；"
              "或输入 circuit 查看已生成的代码，把问题告诉模型让它修复。")
        return
    counts = simulate(circuit, shots)
    top = max(counts, key=counts.get)
    print("\n  [OK] 本地验证通过（%d qubits, %d 门, 深度 %d）" % (
        circuit.num_qubits, len(circuit.ops), max((len(circuit.ops), 0))))
    print("  测量分布（%d shots）：" % shots)
    print(render_counts(counts, shots))
    if len(counts) <= 4:
        dominant = [s for s, c in counts.items() if c > shots * 0.8]
        if dominant:
            print("  解读：电路几乎确定性地输出 %s" % dominant[0])
        else:
            print("  解读：结果分散在多个态上（纠缠/叠加态的特征）")
    print("  目标后端：%s" % backend)


def main() -> int:
    parser = argparse.ArgumentParser(description="LoomQ interactive quantum CLI")
    parser.add_argument("--backend", choices=("spinq", "originq", "braket"), default="braket")
    parser.add_argument("--shots", type=int, default=8192)
    parser.add_argument("--prompt", help="single-shot mode: answer one prompt and exit")
    args = parser.parse_args()

    missing = [v for v in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL") if not os.environ.get(v)]
    if missing:
        print("缺少 L2 模型配置环境变量：%s" % ", ".join(missing), file=sys.stderr)
        print("请设置 LOOMQ_LLM_BASE_URL / LOOMQ_LLM_API_KEY / LOOMQ_LLM_MODEL 后重试。", file=sys.stderr)
        return 2

    last_qasm = ""
    last_native = ""
    if args.prompt:
        return answer_once(args.prompt, args.backend, args.shots)

    print(WELCOME)
    while True:
        try:
            prompt = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            return 0
        if not prompt:
            continue
        if prompt.lower() in ("quit", "exit", "退出"):
            print("再见！")
            return 0
        if prompt.lower() in ("help", "帮助"):
            print(HELP_TEXT)
            continue
        if prompt.lower() in ("tutorial", "教程", "新手", "101"):
            print(TUTORIAL_TEXT)
            continue
        if prompt.lower() in ("circuit", "qasm"):
            print(last_qasm if last_qasm else "还没有生成过电路。")
            continue
        if prompt.lower() in ("native", "转译"):
            print(last_native if last_native else "还没有生成过电路。")
            continue

        started = time.monotonic()
        print("  思考中…")
        try:
            reply = adapter.agent_chat(prompt)
        except Exception as exc:
            print("  [!] 模型调用失败：%s: %s" % (type(exc).__name__, exc))
            print("  排查建议：检查 LOOMQ_LLM_BASE_URL / LOOMQ_LLM_API_KEY / LOOMQ_LLM_MODEL"
                  " 是否正确，以及网络是否可达；也可以输入 tutorial 学习基础概念后重试。")
            continue
        elapsed = time.monotonic() - started

        qasm = None
        import re as _re
        match = _re.search(r"OPENQASM\s+2\.0;.*?(?=```|\Z)", reply, _re.DOTALL | _re.IGNORECASE)
        if match:
            qasm = match.group(0).strip()
        print("  [AI] (%d 秒)" % elapsed)
        if qasm:
            last_qasm = qasm
            try:
                last_native = adapter.transpile(qasm, args.backend)
            except Exception:
                last_native = ""
            print("  已生成电路：")
            print("\n".join("    " + line for line in qasm.splitlines()[:14]))
            verify_and_explain(qasm, args.backend, args.shots)
        else:
            print("  %s" % reply)


def answer_once(prompt: str, backend: str, shots: int) -> int:
    print("> %s" % prompt)
    reply = adapter.agent_chat(prompt)
    import re as _re
    match = _re.search(r"OPENQASM\s+2\.0;.*?(?=```|\Z)", reply, _re.DOTALL | _re.IGNORECASE)
    if match:
        qasm = match.group(0).strip()
        print("电路：")
        print(qasm)
        verify_and_explain(qasm, backend, shots)
    else:
        print(reply)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n再见！")
        sys.exit(0)
