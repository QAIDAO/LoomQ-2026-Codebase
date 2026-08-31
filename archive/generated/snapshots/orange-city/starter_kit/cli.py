#!/usr/bin/env python3
"""Simple CLI for LoomQ Agent — L2 UX entry point."""

from __future__ import annotations

import sys

try:
    from adapter import agent_chat, run, transpile
except ImportError:
    from starter_kit.adapter import agent_chat, run, transpile


def main() -> None:
    print("LoomQ Agent CLI — 输入自然语言描述，输入 quit 退出\n")
    while True:
        try:
            prompt = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not prompt or prompt.lower() in {"quit", "exit", "q"}:
            print("再见！")
            break
        reply = agent_chat(prompt)
        print(f"\nAgent> {reply}\n")
        qasm_start = reply.find("OPENQASM")
        if qasm_start >= 0:
            qasm = reply[qasm_start:]
            if "```" in qasm:
                qasm = qasm.split("```")[0]
            try:
                result = run(qasm.strip(), "spinq", 1024)
                counts = result["counts"]
                total = max(sum(counts.values()), 1)
                print("[自验] 测量直方图（1024 shots，无需量子背景）")
                for key, value in sorted(counts.items(), key=lambda item: -item[1]):
                    bar = "#" * max(1, int(40 * value / total))
                    print("  |%s>  %4d  %5.1f%%  %s" % (key, value, 100.0 * value / total, bar))
                print()
            except Exception as exc:
                print(f"[自验] 运行失败: {exc}\n请检查 QASM 是否包含 qreg/creg 与小写门名。\n")


if __name__ == "__main__":
    main()
