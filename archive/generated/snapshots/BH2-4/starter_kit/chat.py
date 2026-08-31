#!/usr/bin/env python3
"""LoomQ 对话入口：用大白话指挥量子算力。

用法：
  python3 starter_kit/chat.py                       # 交互模式
  python3 starter_kit/chat.py --prompt "生成3比特GHZ态"   # 单发模式
  python3 starter_kit/chat.py --doctor              # 环境自检
  python3 starter_kit/chat.py --demo                # 无模型离线演示（本地模拟+可视化）

回复里若包含量子电路，会自动在本地模拟器上运行 4096 次，
并给出直方图与通俗解读。模型配置从 LOOMQ_LLM_* 环境变量读取。
"""

from __future__ import annotations

import argparse
import os
import random
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))

from loomq import parse_qasm, sample_counts  # noqa: E402

QASM_RE = re.compile(r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", re.DOTALL | re.MULTILINE)

BANNER = r"""
  _                       __  __    _
 | |    __ _ _____   _   |  \/  |  / \
 | |   / _` |_  / | | |  | |\/| | / _ \
 | |__| (_| |/ /| |_| |  | |  | |/ ___ \
 |_____\__,_/___|\__, |  |_|  |_/_/   \_\
                 |___/
 用大白话使用量子计算 —— 试试：
   · 生成一个 3 比特 GHZ 态并测量
   · 我想跑贝尔态，但这段代码报错了：H q[0]; CX q[0] q[1]
   · 15 比特、零排队、免费，选哪个平台？
 输入 退出 / exit 结束。
"""

WELCOME_NO_ENV = (
    "提示：未检测到 LOOMQ_LLM_* 环境变量，对话功能不可用。\n"
    "请先配置（参见 starter_kit/GETTING_STARTED.md 第 2 步），"
    "或先用 --demo 离线体验量子计算。"
)


def bar_chart(counts: dict, width: int = 24) -> str:
    """纯 ASCII 直方图，零依赖。"""
    top = max(counts.values()) or 1
    total = sum(counts.values())
    lines = []
    for key in sorted(counts, key=lambda k: -counts[k]):
        n = counts[key]
        filled = round(width * n / top)
        lines.append("%s |%s%s %5d  (%.1f%%)"
                     % (key, "█" * filled, "·" * (width - filled), n, 100 * n / total))
    return "\n".join(lines)


def explain_result(counts: dict, shots: int) -> str:
    """给完全没学过量子的用户的通俗解读。"""
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    top_keys = [k for k, v in ranked if v >= 0.4 * ranked[0][1]]
    if len(top_keys) == len(counts) and len(counts) > 3:
        return ("结果几乎是均匀的：所有可能性出现的次数都差不多——"
                "这是『均匀叠加态』的典型表现，量子比特同时探索了每条路。")
    if len(top_keys) == 2:
        return ("只有 %s 这两种结果频繁出现（其余几乎不出现）——"
                "比特们被『纠缠』在了一起，要么全 0 要么全 1，"
                "像一对总是给出相同答案的骰子。" % " 和 ".join(top_keys))
    best = ranked[0][0]
    return ("结果高度集中在 %s 上（%.1f%%）——电路把概率 amplitude 集中到了"
            "这一个答案，这正是量子算法『放大正确答案』的方式。"
            % (best, 100 * ranked[0][1] / shots))


def run_circuit(qasm: str, shots: int = 4096, seed: int = 7) -> str:
    circuit = parse_qasm(qasm)
    counts = sample_counts(circuit, shots, rng=random.Random(seed))
    n = circuit.n_qubits
    quirk = {k: v for k, v in counts.items() if v}
    out = ["", "▶ 已在本地无噪声模拟器运行 %d 次，测量结果：" % shots, ""]
    out.append(bar_chart(quirk))
    out.append("")
    out.append("通俗解读：" + explain_result(quirk, shots))
    out.append("（量子比特数 %d；想换随机性可设置不同种子）" % n)
    return "\n".join(out)


def ask(prompt: str) -> str:
    import adapter  # noqa: F401  (确保契约可用)
    from loomq_l2 import agent_chat
    reply = agent_chat(prompt)
    print("\nLoomQ：" + reply)
    match = QASM_RE.search(reply)
    if match:
        try:
            print(run_circuit(match.group(0).strip()))
        except Exception as exc:
            print("（电路自动运行失败：%s；电路本身仍可直接复制使用）" % exc)
    return reply


def doctor() -> int:
    print("环境自检")
    ok = True
    for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL"):
        present = bool(os.environ.get(name))
        print("  [%s] %s%s" % ("√" if present else "×", name,
                               "" if present else " —— 未设置（仅影响对话，不影响模拟）"))
        ok = ok and present
    try:
        from loomq import parse_qasm, sample_counts  # noqa: F401
        print("  [√] 本地量子模拟器可用（纯标准库，离线可跑）")
    except Exception as exc:
        print("  [×] 模拟器异常：%s" % exc)
        ok = False
        import adapter  # noqa: F401
    print("结论：%s" % ("对话 + 模拟全部就绪" if ok else "至少可离线模拟；对话需补上环境变量（见 GETTING_STARTED.md）"))
    return 0


def demo() -> int:
    print("离线演示：不依赖任何模型与网络，直接感受量子计算\n")
    demo_qasm = ('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[3];\ncreg c[3];\n'
                 "h q[0];\ncx q[0], q[1];\ncx q[1], q[2];\nmeasure q -> c;\n")
    print("电路（3 比特 GHZ 纠缠态）：")
    print(demo_qasm)
    print(run_circuit(demo_qasm))
    print("\n下一步：配置 LOOMQ_LLM_* 后用自然语言对话，让助手替你写电路。")
    return 0


def repl() -> int:
    print(BANNER)
    if not os.environ.get("LOOMQ_LLM_API_KEY"):
        print(WELCOME_NO_ENV)
    while True:
        try:
            prompt = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            return 0
        if not prompt:
            continue
        if prompt.lower() in ("exit", "quit", "退出", "q"):
            print("再见！")
            return 0
        try:
            ask(prompt)
        except RuntimeError as exc:
            message = str(exc)
            if "LOOMQ_LLM" in message or "unreachable" in message or "HTTP" in message:
                print("\nLoomQ：模型服务暂时不可用（%s）。\n"
                      "自救三步：① 检查环境变量是否过期 ② 见 GETTING_STARTED.md"
                      "『常见问题』③ 先用 --demo 离线体验。" % message.split(":")[-1].strip())
            else:
                print("\nLoomQ：出错了（%s）。换个说法再试一次，或输入『退出』结束。" % message)
        except Exception as exc:
            print("\nLoomQ：出错了（%s: %s）。换个说法再试一次。" % (type(exc).__name__, exc))


def main() -> int:
    parser = argparse.ArgumentParser(description="LoomQ 大白话量子助手")
    parser.add_argument("--prompt", default=None, help="单发提问（非交互）")
    parser.add_argument("--doctor", action="store_true", help="环境自检")
    parser.add_argument("--demo", action="store_true", help="离线演示（无需模型）")
    args = parser.parse_args()
    if args.doctor:
        return doctor()
    if args.demo:
        return demo()
    if args.prompt:
        ask(args.prompt)
        return 0
    return repl()


if __name__ == "__main__":
    sys.exit(main())
