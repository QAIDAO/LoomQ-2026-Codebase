#!/usr/bin/env python3
"""LoomQ interactive CLI for L2 human experience scoring."""

from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="LoomQ — talk to a quantum computer in plain language"
    )
    parser.add_argument("prompt", nargs="?", help="one-shot prompt; omit for REPL")
    parser.add_argument("--target", default="spinq", choices=("spinq", "originq", "braket"))
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--run", action="store_true", help="after agent reply, run extracted QASM")
    args = parser.parse_args(argv)

    # Import from package root when executed inside starter_kit/.
    try:
        import adapter
    except ImportError:
        from starter_kit import adapter  # type: ignore

    def handle(prompt: str) -> None:
        print("\nLoomQ 思考中…\n")
        reply = adapter.agent_chat(prompt)
        print(reply)
        if not args.run:
            return
        from loomq_agent import extract_qasm

        qasm = extract_qasm(reply)
        if not qasm:
            print("\n[未检测到可运行 QASM，跳过执行]")
            return
        print("\n—— 使用 L1 中间层执行 (%s, shots=%d) ——" % (args.target, args.shots))
        result = adapter.run(qasm, args.target, args.shots)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("\n通俗解读：出现次数最多的结果是主导测量态；贝尔/GHZ 通常看到全 0 与全 1 各约一半。")

    missing = [
        name
        for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")
        if not os.environ.get(name)
    ]
    if missing:
        print("缺少环境变量: " + ", ".join(missing), file=sys.stderr)
        print(
            "示例:\n  set LOOMQ_LLM_BASE_URL=https://api.deepseek.com\n"
            "  set LOOMQ_LLM_API_KEY=...\n"
            "  set LOOMQ_LLM_MODEL=deepseek-v4-flash",
            file=sys.stderr,
        )
        return 2

    if args.prompt:
        handle(args.prompt)
        return 0

    print("LoomQ CLI — 输入自然语言（exit 退出）")
    print("示例：生成一个 3 比特 GHZ 态并测量")
    while True:
        try:
            line = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line.lower() in {"exit", "quit", "q"}:
            return 0
        try:
            handle(line)
        except Exception as exc:
            print("出错了：%s\n可以换种说法，或检查 API 配置。" % exc, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
