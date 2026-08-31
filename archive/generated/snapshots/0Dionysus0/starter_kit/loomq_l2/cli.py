"""Zero-foundation LoomQ chat CLI (L2 interaction entry).

Design goals for judges / first-time users:
  - one command to start
  - numbered starter tasks (no quantum jargon required)
  - show QASM in plain language, then a counts bar chart
  - recoverable errors that say what to do next
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence, Tuple

from loomq_l2.tasks import STARTER_TASKS
from loomq_l2.turn import env_ready, plain_error, run_user_turn


def _banner() -> str:
    return "\n".join(
        [
            "=" * 56,
            "  LoomQ 零基础对话入口",
            "  你不用会写量子代码——用中文/英文说话就行。",
            "=" * 56,
            "",
            "直接回车看菜单；输入 1 / 2 / 3 做体验任务；",
            "或随便提问。输入 help 看说明，quit 离开。",
            "",
        ]
    )


def _menu() -> str:
    lines = ["现场体验任务（评委也可直接用编号）：", ""]
    for num, title, prompt in STARTER_TASKS:
        lines.append(f"  [{num}] {title}")
        lines.append(f"      → {prompt}")
        lines.append("")
    lines.append("其他命令：help  |  tasks  |  quit")
    return "\n".join(lines)


def _plain_env_error(exc: BaseException) -> str:
    return plain_error(exc)


def resolve_user_input(raw: str) -> str:
    from loomq_l2.tasks import resolve_task_prompt

    return resolve_task_prompt(raw)


def handle_turn(user_text: str, auto_run: bool = True) -> str:
    """One user utterance → printable CLI text."""
    result = run_user_turn(user_text, auto_run=auto_run)
    chunks: List[str] = []
    if result["prompt"] != result["input"]:
        chunks.append(f"已选择体验任务，完整问题是：\n  {result['prompt']}\n")
    if result["error"] and not result["reply"]:
        return result["error"]
    chunks.append("—— 助手回复 ——")
    chunks.append(result["reply"])
    chunks.append("")
    if result.get("qasm") and auto_run:
        chunks.append("—— 电路草稿 ——")
        chunks.append(
            "下面是助手生成的量子程序草稿。看不懂代码也没关系，重点看后面的条形图。"
        )
        chunks.append(result["qasm"])
        chunks.append("")
        chunks.append("—— 本地试跑 ——")
        if result.get("chart_text"):
            chunks.append(
                f"已在本地模拟器跑完（{result.get('run_backend')}, shots={result.get('shots')}）。"
            )
            chunks.append("读图方法：横条越长，这种结果出现得越频繁。")
            chunks.append("")
            chunks.append(result["chart_text"])
        elif result.get("error"):
            chunks.append(result["error"])
    elif result.get("backend_id"):
        chunks.append("—— 选后端摘要 ——")
        chunks.append(f"助手提到的规范后端 id：{result['backend_id']}")
        chunks.append("（正式评分只认这类英文 id，不认「本地模拟器」这种口头说法。）")
    if result.get("error") and result.get("reply"):
        chunks.append("")
        chunks.append(result["error"])
    return "\n".join(chunks).rstrip() + "\n"


def check_ready() -> Tuple[bool, str]:
    status = env_ready()
    return bool(status["ok"]), str(status["message"])


def repl() -> int:
    print(_banner())
    ready, msg = check_ready()
    if not ready:
        print(msg)
        print("配置好环境变量后重新运行：python chat.py")
        return 2
    print(msg)
    print()
    print(_menu())
    print()
    while True:
        try:
            raw = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            return 0
        if not raw:
            print(_menu())
            continue
        low = raw.lower()
        if low in {"quit", "exit", "q", "再见"}:
            print("再见。")
            return 0
        if low in {"help", "h", "?"}:
            print(_help_text())
            continue
        if low == "tasks":
            print(_menu())
            continue
        print()
        print(handle_turn(raw))
        print()


def _help_text() -> str:
    return "\n".join(
        [
            "怎么用：",
            "  1/2/3     做三个零基础体验任务",
            "  随便打字  用自然语言提要求（生成电路 / 修电路 / 选平台）",
            "  tasks     再看一遍任务菜单",
            "  quit      离开",
            "",
            "小提示：",
            "  · 看不懂 OpenQASM 没关系，看条形图即可",
            "  · 若报错，按提示补环境变量或换任务 1 重试",
            "  · 概念速查见同目录 QUANTUM_101.md",
        ]
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="LoomQ zero-foundation chat CLI (L2 interaction entry)"
    )
    parser.add_argument(
        "--once",
        default="",
        help="non-interactive: run one prompt or task number, then exit",
    )
    parser.add_argument("--tasks", action="store_true", help="print the 3 live tasks and exit")
    parser.add_argument(
        "--check",
        action="store_true",
        help="check LOOMQ_LLM_* env only",
    )
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="do not auto-run generated QASM on the local simulator",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.tasks:
        print(_menu())
        return 0
    if args.check:
        ready, msg = check_ready()
        print(msg)
        return 0 if ready else 2
    if args.once:
        ready, msg = check_ready()
        if not ready:
            print(msg)
            return 2
        # Temporary override of auto_run via closure-friendly call
        text = handle_turn(args.once, auto_run=not args.no_run)
        print(text)
        return 0
    return repl()


if __name__ == "__main__":
    raise SystemExit(main())
