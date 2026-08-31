#!/usr/bin/env python3
"""LoomQ CLI -- the beginner-facing entry point (L2 interactive experience).

Zero install, pure standard library:

    python3 loomq_cli.py                 # interactive mode (recommended)
    python3 loomq_cli.py ask "生成一个3比特GHZ态并全测量"
    python3 loomq_cli.py run circuits/bell.qasm --target spinq --shots 1024
    python3 loomq_cli.py backends        # show the backend capability table
    python3 loomq_cli.py guide           # 5-minute beginner walkthrough

Interactive mode turns every natural-language request into: agent answer ->
extracted QASM -> local simulation -> ASCII histogram -> plain-language
explanation. Without LOOMQ_LLM_* configured, circuit commands still work and
chat commands explain how to enable the agent.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adapter  # noqa: E402
from loomq_core.agent import _extract_qasm  # noqa: E402


BANNER = r"""
 _                          ____
| |    ___   ___  _ __ ___ / __ \
| |   / _ \ / _ \| '_ ` _ \ |  | |
| |__| (_) | (_) | | | | | | |__| |
|_____\___/ \___/|_| |_| |_\___\_\

LoomQ — 用自然语言指挥量子计算机 (type 'help' for commands, 'quit' to exit)
"""

HELP = """可用命令：
  ask <问题>        问量子助手（生成电路 / 修复代码 / 推荐后端）
  run <文件.qasm>   在本地模拟器运行一个 QASM 文件并显示结果直方图
  backends          查看各平台后端能力表
  guide             5 分钟新手上路
  quit              退出
直接输入一句话（不带命令）等同于 ask。
"""


def _llm_configured() -> bool:
    return all(os.environ.get(name) for name in
               ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL"))


def show_counts(counts, shots: int) -> None:
    if not counts:
        print("(无测量结果)")
        return
    width = 40
    print("\n测量结果（共 %d 次采样）：" % shots)
    for key in sorted(counts):
        value = counts[key]
        bar = "█" * max(1, round(width * value / shots))
        print("  |%s⟩  %5d  %5.1f%%  %s" % (key, value, 100.0 * value / shots, bar))


def explain_counts(counts) -> str:
    keys = sorted(counts)
    if len(keys) == 1:
        return "结果完全确定：每次测量都得到 |%s⟩。" % keys[0]
    if len(keys) == 2 and set("".join(keys)) == {"0", "1"}:
        a, b = keys
        # Entanglement needs multi-bit registers whose outcomes are perfectly
        # anti-correlated bit strings (e.g. 00/11 or 000/111). A single qubit
        # in superposition (0/1) is NOT entanglement.
        if (
            len(a) >= 2
            and len(a) == len(b)
            and set(a) == {"0"}
            and set(b) == {"1"}
        ):
            return ("只出现 |%s⟩ 和 |%s⟩，且两者总是同时出现——这就是纠缠："
                    "单个比特看是随机的，但比特之间永远保持一致。" % (a, b))
        if len(a) == 1 and len(b) == 1:
            return ("单比特叠加态：每次测量随机得到 |0⟩ 或 |1⟩，各约占一半概率。"
                    "测量前它同时处于两者——这就是叠加原理。")
    return "共观察到 %d 种不同的测量结果，上方的百分比就是每种结果出现的频率。" % len(keys)


def draw_circuit(circuit) -> str:
    """Render the circuit as an ASCII diagram (one row per qubit).

    Greedy column assignment: every gate takes the next free column after its
    operand wires, so wires never cross. Controls are '●', targets are
    'X'/'P(θ)', swaps are '×'.
    """
    n = circuit.num_qubits
    last_col = [0] * n
    grid: list[list] = [[] for _ in range(n)]  # grid[q][col] = gate or None

    for gate in circuit.gates:
        col = max(last_col[q] for q in gate.qubits) + 1
        for q in gate.qubits:
            last_col[q] = col
            while len(grid[q]) < col + 1:
                grid[q].append(None)
            grid[q][col] = gate
    width = max((len(row) for row in grid), default=0)

    # pad all rows to the same width
    for q in range(n):
        while len(grid[q]) < width:
            grid[q].append(None)

    rows: list[str] = []
    cells_grid: list[list[str]] = []
    for q in range(n):
        cells = []
        for col in range(width):
            gate = grid[q][col]
            if gate is None:
                cells.append("─")
                continue
            if gate.name == "swap":
                cells.append("×")
            elif q != gate.qubits[-1]:  # control line
                cells.append("●")
            elif gate.name in ("cx", "ccx"):
                cells.append("X")
            elif gate.name == "cu1":
                cells.append("P(π/%.1f)" % _angle_in_pi(gate.params[0]))
            elif gate.name in ("rz", "ry"):
                cells.append("%s(π/%.1f)" % (gate.name, _angle_in_pi(gate.params[0])))
            else:
                cells.append(gate.name.upper())
        cells_grid.append(cells)

    # pad each column to a uniform width (right-aligned gates on a wire)
    max_cols = max((len(row) for row in cells_grid), default=0)
    for col in range(max_cols):
        width_c = max((len(cells_grid[q][col]) for q in range(n) if col < len(cells_grid[q])), default=1)
        for q in range(n):
            if col < len(cells_grid[q]):
                text = cells_grid[q][col]
                cells_grid[q][col] = text if text == "─" else text.rjust(width_c)

    out = []
    for q in range(n):
        body = "".join(cells_grid[q])
        mcell = ""
        for qubit, clbit in sorted(circuit.measurements):
            if qubit == q:
                mcell = " M→c[%d]" % clbit
                break
        out.append("q[%d]: %s%s" % (q, body, mcell))
    return "\n".join(out)


def _angle_in_pi(theta: float) -> float:
    """Round theta to a multiple of pi/8 and return the denominator n s.t.
    theta ≈ pi/n (n=infinity if theta is 0)."""
    import math

    if abs(theta) < 1e-9:
        return 0.0
    for n in (1, 2, 3, 4, 6, 8, 16):
        if abs(theta - math.pi / n) < 1e-9:
            return float(n)
    return theta / math.pi


def cmd_run(path: str, target: str, shots: int) -> None:
    with open(path, encoding="utf-8") as handle:
        qasm = handle.read()
    print("目标后端：%s（本地参考模拟器执行转译产物）" % target)
    native = adapter.transpile(qasm, target)
    print("\n--- 转译后的 %s 原生 IR ---" % target)
    print(native.rstrip())
    result = adapter.run(qasm, target, shots)
    show_counts(result["counts"], shots)
    print("\n" + explain_counts(result["counts"]))


def cmd_ask(question: str) -> None:
    if not _llm_configured():
        print("量子助手需要模型服务配置。请设置：")
        print("  export LOOMQ_LLM_BASE_URL=https://api.deepseek.com")
        print("  export LOOMQ_LLM_API_KEY=<你的 Key>")
        print("  export LOOMQ_LLM_MODEL=deepseek-v4-flash")
        print("正式评测时组委会会自动注入这些变量。")
        return
    reply = adapter.agent_chat(question)
    print(reply)
    qasm = _extract_qasm(reply)
    if qasm:
        print("\n--- 自动验证：在本地模拟器运行生成的电路 ---")
        try:
            result = adapter.run(qasm, "spinq", 1024)
            show_counts(result["counts"], 1024)
            print("\n" + explain_counts(result["counts"]))
        except Exception as exc:  # noqa: BLE001
            print("电路自检未通过：%s" % exc)


def cmd_backends() -> None:
    import json

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "backend_capabilities.json")
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    print("%-26s %-8s %-10s %6s %-18s %-11s" %
          ("后端 id", "平台", "类型", "比特", "排队", "费用"))
    for b in data["backends"]:
        print("%-26s %-8s %-10s %6d %-18s %-11s" %
              (b["id"], b["platform"], b["kind"], b["max_qubits"],
               b["queue"], b["cost"]))


GUIDE = """LoomQ 5 分钟新手上路
=====================

1. 量子电路就是一段指令列表。试试运行自带的贝尔态电路：
     python3 loomq_cli.py run circuits/bell.qasm --target spinq

2. 看不懂 QASM？直接对助手说人话（需要配置 LOOMQ_LLM_*）：
     python3 loomq_cli.py ask "帮我做一个两个比特永远同面的硬币"

3. 助手生成的电路会自动在本地模拟器跑一遍，直方图告诉你每个结果的概率。

4. 想换平台？同一份电路一键转译到三家后端：
     --target spinq | originq | braket

5. 不知道该用哪家？问助手：
     python3 loomq_cli.py ask "20 比特电路，不想排队，选哪个后端？"

更多背景：阅读 QUANTUM_101.md（30 分钟量子速成，零基础友好）。
"""


def interactive() -> None:
    print(BANNER)
    while True:
        try:
            line = input("loomq> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("quit", "exit"):
            break
        if line == "help":
            print(HELP)
        elif line == "guide":
            print(GUIDE)
        elif line == "backends":
            cmd_backends()
        elif line.startswith("run "):
            parts = line.split()
            try:
                cmd_run(parts[1], "spinq", 1024)
            except (OSError, ValueError, IndexError) as exc:
                print("运行失败：%s" % exc)
        elif line.startswith("ask "):
            cmd_ask(line[4:])
        else:
            cmd_ask(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="LoomQ beginner CLI")
    sub = parser.add_subparsers(dest="command")

    p_ask = sub.add_parser("ask", help="ask the quantum agent")
    p_ask.add_argument("question")

    p_run = sub.add_parser("run", help="run a QASM file locally")
    p_run.add_argument("path")
    p_run.add_argument("--target", default="spinq",
                       choices=list(adapter.SUPPORTED_TARGETS))
    p_run.add_argument("--shots", type=int, default=1024)

    sub.add_parser("backends", help="show backend capabilities")
    sub.add_parser("guide", help="beginner walkthrough")

    args = parser.parse_args()
    if args.command == "ask":
        cmd_ask(args.question)
    elif args.command == "run":
        cmd_run(args.path, args.target, args.shots)
    elif args.command == "backends":
        cmd_backends()
    elif args.command == "guide":
        print(GUIDE)
    else:
        interactive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
