#!/usr/bin/env python3
"""Zero-dependency contestant-facing CLI for LoomQ."""

from __future__ import annotations

import argparse
import sys
from typing import Dict

try:
    from .adapter import agent_chat, run
    from .agent_engine import extract_qasm
except ImportError:
    from adapter import agent_chat, run
    from agent_engine import extract_qasm


DEMOS = {
    "bell": '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
''',
    "ghz3": '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0], q[1];
cx q[1], q[2];
measure q -> c;
''',
}


WELCOME = """\
LoomQ 量子实验助手 / quantum experiment assistant

你不需要量子物理背景。说出想生成、修复或运行的电路即可。
No quantum-physics background is required.

可直接尝试 / Try one of these:
  1. 生成一个 4 比特 GHZ 态并进行全测量。
  2. 我想制备 Bell 态，请修复：H q[0]; CX q[0] q[1]
  3. 我要运行 25 qubit 电路，要求本地、免费、无需账号且不排队。

命令 / Commands: /demo bell, /demo ghz3, /clear, /help, /quit
"""


INTERACTIVE_HELP = """\
自然语言请求会调用 LOOMQ_LLM_* 配置的模型，然后由 LoomQ 解析并验证结果。
Natural-language requests use the configured model and are validated locally.

  /demo bell  - 离线 Bell 演示（无需 API Key）
  /demo ghz3  - 离线三比特 GHZ 演示
  /clear      - 清除上一轮上下文
  /help       - 显示本帮助
  /quit       - 退出
"""


FOLLOW_UP_PREFIXES = (
    "改成", "换成", "那", "如果", "继续", "再", "这个", "它", "不要", "还要", "也要",
    "then", "instead", "what about", "how about", "make it", "change it", "also",
)


def histogram(counts: Dict[str, int], shots: int, width: int = 36) -> str:
    if shots <= 0:
        raise ValueError("shots must be positive")
    lines = []
    maximum = max(counts.values(), default=1)
    for state, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        bar_length = 0 if count == 0 else max(1, round(width * count / maximum))
        bar = "#" * bar_length
        lines.append(f"  |{state}>  {bar:<{width}} {count:>6}  {100 * count / shots:6.2f}%")
    return "\n".join(lines)


def explain(counts: Dict[str, int]) -> str:
    states = {state for state, count in counts.items() if count > 0}
    if states and all(set(state) <= {"0"} or set(state) <= {"1"} for state in states):
        return (
            "只有全 0 和全 1 结果占主导：单次测量是随机的，但量子比特始终保持关联。\n"
            "  Only the all-zero and all-one outcomes dominate. Each shot is random, "
            "while the qubits remain correlated."
        )
    dominant = max(counts, key=counts.get)
    return (
        f"最常见的测量结果是 |{dominant}>。counts 是多次实验的观测次数，不是振幅。\n"
        f"  The most frequent measured state is |{dominant}>. Counts are repeated-shot "
        "observations, not amplitudes."
    )


def show_result(qasm: str, target: str, shots: int) -> None:
    payload = run(qasm, target, shots)
    print("\n测量结果 / Measurement results")
    print(f"Backend: {payload['backend']}  Shots: {payload['shots']}  Bit order: {payload['bit_order']}")
    print(histogram(payload["counts"], payload["shots"]))
    print("\n如何理解 / What this means:")
    print("  " + explain(payload["counts"]))
    print("  位序提示：位串最右侧是 c[0]；精确次数和百分比与直方图同时给出。")


def run_demo(name: str, target: str, shots: int) -> None:
    qasm = DEMOS[name]
    label = "Bell pair" if name == "bell" else "three-qubit GHZ state"
    print(f"LoomQ offline demo: {label}\n")
    print("这是无需账号、API Key 或第三方依赖的完整量子实验。")
    print("This complete quantum experiment runs without an account, API key, or third-party dependency.\n")
    print(qasm.rstrip())
    show_result(qasm, target, shots)


def is_follow_up(prompt: str) -> bool:
    normalized = prompt.strip().lower()
    return any(normalized.startswith(prefix) for prefix in FOLLOW_UP_PREFIXES)


def contextual_prompt(prompt: str, previous_prompt: str, previous_reply: str) -> str:
    """Put the current request first so local validators prefer its updated constraints."""
    return (
        "Current follow-up request:\n"
        + prompt.strip()
        + "\n\nContext from the immediately previous turn:\nUser: "
        + previous_prompt.strip()[-1000:]
        + "\nLoomQ: "
        + previous_reply.strip()[-6000:]
    )


def handle_prompt(prompt: str, target: str, shots: int) -> str:
    reply = agent_chat(prompt)
    print("\nLoomQ 回答 / response:\n")
    print(reply)
    qasm = extract_qasm(reply)
    if qasm:
        print("\n✓ 已提取完整 QASM，现在用本地引擎运行预览。")
        show_result(qasm, target, shots)
    return reply


def interactive(target: str, shots: int) -> None:
    print(WELCOME)
    previous_prompt = ""
    previous_reply = ""
    while True:
        try:
            prompt = input("你 / You > ").strip()
        except EOFError:
            print()
            return
        command = prompt.lower()
        if command in {"quit", "exit", "/quit", "/exit", "退出"}:
            return
        if not prompt:
            continue
        if command in {"help", "/help", "帮助", "/帮助"}:
            print("\n" + INTERACTIVE_HELP)
            continue
        if command in {"clear", "/clear", "清除", "清空"}:
            previous_prompt = ""
            previous_reply = ""
            print("✓ 已清除对话上下文 / Conversation context cleared.")
            continue
        if command in {"/demo bell", "demo bell", "演示 bell"}:
            run_demo("bell", target, shots)
            continue
        if command in {"/demo ghz3", "demo ghz3", "演示 ghz3"}:
            run_demo("ghz3", target, shots)
            continue
        try:
            effective_prompt = prompt
            if previous_reply and is_follow_up(prompt):
                effective_prompt = contextual_prompt(prompt, previous_prompt, previous_reply)
                print("↪ 已引用上一轮上下文；输入 /clear 可重置。")
            reply = handle_prompt(effective_prompt, target, shots)
            previous_prompt = prompt
            previous_reply = reply
        except Exception as exc:
            print(f"本次请求未完成 / Could not complete that request: {exc}", file=sys.stderr)
            print(
                "请检查 LOOMQ_LLM_BASE_URL、LOOMQ_LLM_API_KEY 和 LOOMQ_LLM_MODEL 后重试；"
                "也可输入 /demo bell 继续离线体验。",
                file=sys.stderr,
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LoomQ 自然语言量子电路助手 / natural-language quantum circuit runner",
        epilog=(
            "fork-root examples:\n"
            "  python3 starter_kit/loomq_cli.py --demo bell\n"
            "  python3 starter_kit/loomq_cli.py --prompt '生成一个 3 比特 GHZ 态并进行全测量'\n"
            "evaluation-root equivalent:\n"
            "  python3 loomq_cli.py --demo bell\n"
            "  python3 loomq_cli.py --demo ghz3 --target originq --shots 2048"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--demo", choices=sorted(DEMOS), help="run an offline guided circuit")
    parser.add_argument("--prompt", help="send one request to the configured LoomQ model")
    parser.add_argument("--target", choices=("spinq", "originq", "braket"), default="braket")
    parser.add_argument("--shots", type=int, default=1024)
    args = parser.parse_args()
    if args.shots <= 0:
        parser.error("--shots must be positive")
    try:
        if args.demo:
            run_demo(args.demo, args.target, args.shots)
        elif args.prompt:
            handle_prompt(args.prompt, args.target, args.shots)
        else:
            interactive(args.target, args.shots)
        return 0
    except Exception as exc:
        print(f"LoomQ 运行失败 / failed: {exc}", file=sys.stderr)
        print(
            "先运行 --demo bell 验证离线引擎；Agent 请求请检查 "
            "LOOMQ_LLM_BASE_URL、LOOMQ_LLM_API_KEY 和 LOOMQ_LLM_MODEL。",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
