#!/usr/bin/env python3
"""LoomQ Agent 命令行入口 —— 让不懂量子的人也能指挥量子计算机。

两种用法：
    python3 chat_cli.py                 # 交互式对话
    python3 chat_cli.py "生成一个3比特纠缠态"   # 单次提问

需要模型服务配置（正式评测由组委会注入；本地自备 OpenAI-compatible 服务）：
    LOOMQ_LLM_BASE_URL  接口根地址
    LOOMQ_LLM_API_KEY   密钥
    LOOMQ_LLM_MODEL     模型名（如 deepseek-v4-flash）
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapter import agent_chat, run  # noqa: E402

_QASM_RE = re.compile(r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", re.DOTALL | re.MULTILINE)

_BANNER = """================================================================
  LoomQ 量子助手 —— 用自然语言指挥量子计算机
================================================================
直接告诉我你想做什么，例如：
  · "生成一个让 3 个比特纠缠起来的电路"
  · "我想得到贝尔态，但这句代码报错了：H q[0]; CX q[0] q[1]"
  · "我要跑 20 比特还不排队的电路，选哪个平台"
输入 help 查看帮助，输入 quit 退出。
"""

_HELP = """我可以帮你做三件事：
  1. 生成电路：用自然语言描述想要的量子态，我写出 OpenQASM 代码并运行；
  2. 修复电路：把报错的代码发给我，我帮你改好（保持你的本意）；
  3. 选择后端：告诉我比特数、排队、成本等要求，我推荐合适的平台。
输入 quit 退出。
"""


def _extract_qasm(reply: str) -> str:
    match = _QASM_RE.search(reply)
    return match.group(0).strip() if match else ""


def _render_counts(counts: dict, shots: int) -> str:
    if not counts:
        return "  （无测量结果）"
    width = max(len(key) for key in counts)
    max_count = max(counts.values())
    lines = ["  测量结果（共 %d 次采样）：" % shots]
    for key in sorted(counts):
        value = counts[key]
        bar_len = int(value / max_count * 30) if max_count else 0
        pct = value / shots * 100 if shots else 0.0
        lines.append("    %-*s  %s  %d  (%.1f%%)" % (width, key, "█" * bar_len, value, pct))
    return "\n".join(lines)


def _check_env() -> str:
    missing = [
        name
        for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")
        if not os.environ.get(name)
    ]
    return "、".join(missing)


def handle(prompt: str) -> None:
    reply = agent_chat(prompt)
    print(reply)
    qasm = _extract_qasm(reply)
    if qasm:
        print("\n--- 我已在这台机器的无噪声模拟器上跑了一遍 ---")
        try:
            result = run(qasm, "braket", 8192)
            print(_render_counts(result["counts"], result["shots"]))
        except Exception as exc:
            print("运行失败：%s" % exc)
    print()


def main() -> int:
    args = sys.argv[1:]
    if args:
        prompt = " ".join(args).strip()
        try:
            handle(prompt)
        except RuntimeError as exc:
            print("出错了：%s" % exc, file=sys.stderr)
            return 1
        return 0

    print(_BANNER)
    missing = _check_env()
    if missing:
        print("提示：未检测到模型服务配置（%s）。" % missing)
        print("本地自测请先设置上述环境变量；正式评测会由组委会自动注入。\n")

    while True:
        try:
            prompt = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not prompt:
            continue
        if prompt.lower() in ("quit", "exit", "q"):
            print("再见！")
            break
        if prompt.lower() in ("help", "h", "?"):
            print(_HELP)
            continue
        try:
            handle(prompt)
        except RuntimeError as exc:
            print("出错了：%s" % exc)
            if "environment variable" in str(exc):
                print("请先设置 LOOMQ_LLM_BASE_URL / LOOMQ_LLM_API_KEY / LOOMQ_LLM_MODEL。")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
