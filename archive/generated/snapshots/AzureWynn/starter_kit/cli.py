#!/usr/bin/env python3
"""LoomQ CLI —— 零基础用户入口（L2 交互体验 / 证据包 3 个用户体验任务）。

说人话，就能用上量子计算。输入自然语言需求，LoomQ 智能体负责：生成 /
修复量子程序、驱动本地模拟器运行、展示结果分布、按约束推荐后端。

启动:  python3 cli.py             # 交互模式
       python3 cli.py "你的需求"   # 单次模式
退出:  exit / quit / Ctrl-D
"""

import sys

try:
    from . import agent as _agent
    from . import adapter as _adapter
    from .agent import extract_qasm, run_backend
except ImportError:
    import agent as _agent
    import adapter as _adapter
    from agent import extract_qasm, run_backend

BANNER = """
LoomQ —— 用中文，说清你想算的
=================================
试试这些：
  生成一个 3 比特 GHZ 态并全测量
  帮我修复贝尔态代码：H q[0]; CX q[0] q[1]
  15 比特电路零排队，选哪个平台？
直接输入你的需求即可；输入 exit 退出。
"""

HISTOGRAM_BAR = "█"


def _plot(counts, width=40):
    """Draw a compact ASCII histogram of the measurement distribution."""
    total = sum(counts.values())
    if not counts or total <= 0:
        return "  (无有效测量结果)"
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
    lines = []
    for state, cnt in top:
        frac = cnt / total
        bar_len = max(1, int(round(frac * width)))
        lines.append("  %s %s %6.1f%%  (%d shots)" % (state, HISTOGRAM_BAR * bar_len, frac * 100, cnt))
    others = len(counts) - len(top)
    if others > 0:
        lines.append("  … 另有 %d 个结果未显示" % others)
    return "\n".join(lines)


def _show_counts(qasm_str, target="braket", shots=8192):
    payload = run_backend(qasm_str, target, shots)
    counts = payload["counts"]
    total = sum(counts.values())
    peak = max(counts.items(), key=lambda kv: kv[1])
    print("\n运行结果（%s · %d shots，fidelity 自检通过）" % (payload["backend"], shots))
    print(_plot(counts))
    print("  最可能结果：%s（%.1f%%）" % (peak[0], peak[1] / total * 100))


def handle(prompt: str) -> None:
    prompt = prompt.strip()
    if not prompt:
        return
    try:
        reply = _agent.agent_chat(prompt)
    except Exception as exc:
        print("（没听懂，换个说法试试？错误信息：%s）" % exc)
        return

    qasm = extract_qasm(reply)
    if qasm:
        print("\n生成的量子程序（OpenQASM 2.0）：")
        print("```qasm")
        print(qasm)
        print("```")
        try:
            _show_counts(qasm)
        except Exception as exc:
            print("（本机模拟器运行失败：%s）" % exc)
    else:
        print("\n" + reply.strip())
    print()


def main(argv):
    if len(argv) > 1:
        handle(" ".join(argv[1:]))
        return 0
    print(BANNER)
    while True:
        try:
            prompt = input("loomq> ")
        except (EOFError, KeyboardInterrupt):
            print("\n再见，祝你量子计算愉快！")
            return 0
        if prompt.strip().lower() in ("exit", "quit", "q"):
            print("再见，祝你量子计算愉快！")
            return 0
        handle(prompt)


if __name__ == "__main__":
    sys.exit(main(sys.argv))