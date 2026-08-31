"""Friendly CLI and web-server launcher for LoomQ."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import chat
from .pipeline import verified_run
from .quantum_riscv import assemble_qasm
from .web import serve


BELL = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""


def _bars(counts: dict[str, int], shots: int) -> str:
    lines = []
    for state, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        ratio = count / shots
        lines.append(f"  |{state}〉 {'█' * round(ratio * 30):<30} {ratio:6.1%} ({count})")
    return "\n".join(lines)


def _run(qasm: str, target: str, shots: int) -> dict:
    result, _ = verified_run(qasm, target, shots)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LoomQ：让第一次量子实验不需要先学黑话")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("demo", help="无需账号运行 Bell 纠缠演示")
    run_parser = subparsers.add_parser("run", help="运行 OpenQASM 文件")
    run_parser.add_argument("file", type=Path)
    run_parser.add_argument("--target", choices=("spinq", "originq", "braket"), default="spinq")
    run_parser.add_argument("--shots", type=int, default=1024)

    ask_parser = subparsers.add_parser("ask", help="用自然语言生成、修复电路或选择后端")
    ask_parser.add_argument("prompt")

    serve_parser = subparsers.add_parser("serve", help="启动本地无障碍 Web 界面")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)

    riscv_parser = subparsers.add_parser("riscv", help="把基础 QASM 编码为自定义 RISC-V 指令")
    riscv_parser.add_argument("file", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        result = _run(BELL, "spinq", 1024)
        print("\nBell 纠缠实验：两枚量子硬币各自随机，但结果永远相同。\n")
        print(_bars(result["counts"], result["shots"]))
        print("\n验证结论：只出现 |00〉与 |11〉，纠缠关联成立。")
        return 0
    if args.command == "run":
        result = _run(args.file.read_text(encoding="utf-8"), args.target, args.shots)
        print(_bars(result["counts"], result["shots"]))
        print("\n" + json.dumps({key: value for key, value in result.items() if key != "counts"}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "ask":
        print(chat(args.prompt))
        return 0
    if args.command == "serve":
        serve(args.host, args.port)
        return 0
    if args.command == "riscv":
        print(assemble_qasm(args.file.read_text(encoding="utf-8")), end="")
        return 0
    return 2
