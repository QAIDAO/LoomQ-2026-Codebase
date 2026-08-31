#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LoomQ-Agent 交互 CLI — L2 交互体验入口（零第三方依赖，Python 3.10+）

三种用法：
  1. 自然语言对话：输入中文/英文意图，L2 agent 生成电路 -> 自验 -> 运行 -> 可视化
  2. 直接粘贴 QASM：贴入 OPENQASM 2.0 程序，跳过 LLM 直接运行
  3. 内置命令：/help /run /backends /exit   （离线可用）

L2 依赖 LOOMQ_LLM_* 环境变量（正式评测由组委会注入）；本地调试时
l2_agent 会读取同目录 .env.local。LLM 不可用时自然语言模式给出提示，
但直接贴 QASM 与 /run 两条路径完全离线可用。

示例：
  python cli.py                      # 进入交互式对话
  python cli.py --once "生成一个3比特GHZ态"   # 单轮演示（脚本/评分友好）
  python cli.py --run bell.qasm braket 8192  # 直接跑本地文件
"""

import json
import os
import sys

# Windows 控制台默认 GBK，强制 UTF-8 输出（Windows Terminal / VS Code / Git Bash
# 均按 UTF-8 显示；评测环境为 Linux 无此问题）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from starter_kit import adapter  # fork 根目录运行（正式评测）
except ImportError:
    import adapter  # 在 starter_kit/ 目录内运行（本地开发）

SUPPORTED_TARGETS = ("spinq", "braket", "originq")
DEFAULT_SHOTS = 8192

BANNER = r"""
  _                            ____        _
 | |    ___   __ _  ___ _ __  / ___| __ _ (_)
 | |   / _ \ / _` |/ _ \ '__|| |  _ / _` || |
 | |__| (_) | (_| |  __/ |   | |_| | (_| || |
 |_____\___/ \__, |\___|_|    \____|\__,_|/ |
             |___/                      |__/
LoomQ-Agent — 量子电路自然语言助手
输入自然语言描述电路意图，或 /help 查看用法。输入 /exit 退出。
"""


# ---------------------------------------------------------------------------
# 结果可视化（纯 ASCII，终端编码无关）
# ---------------------------------------------------------------------------

def _sorted_counts(counts: dict) -> list:
    """counts -> [(位串, 次数, 占比)]，按次数降序。"""
    total = sum(counts.values()) or 1
    items = sorted(counts.items(), key=lambda kv: -kv[1])
    return [(k, v, v / total) for k, v in items]


def print_histogram(counts: dict, shots: int, title: str = "运行结果") -> None:
    """ASCII 条形图输出：主态直观可见，适合零基础用户。"""
    items = _sorted_counts(counts)
    print("=== %s（总采样 %d 次）===" % (title, shots))
    if not items:
        print("（无测量结果）")
        return
    max_cnt = items[0][1]
    for state, cnt, frac in items[:6]:  # 最多展示 6 个主态
        bar = "#" * int(round(cnt / max_cnt * 20))
        print('  "%s" %-20s %5d  %5.1f%%' % (state, bar, cnt, frac * 100))
    if len(items) > 6:
        print("  ... 其余 %d 个位串略过" % (len(items) - 6))
    print()


def _is_qasm(text: str) -> bool:
    return text.lstrip().upper().startswith("OPENQASM")


def _read_qasm_block(first_line: str) -> str:
    """粘贴模式：首行 OPENQASM 之后继续逐行读，直到空行或 EOF。

    input() 每次只返回一行，多行电路必须收集完整块再运行，
    否则电路被截断且其余行会被误当成自然语言。
    """
    lines = [first_line]
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break  # 空行 = 用户提交结束
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 电路执行（统一 Schema 消费端）
# ---------------------------------------------------------------------------

def run_circuit(qasm: str, target: str, shots: int = DEFAULT_SHOTS) -> dict:
    """执行电路并打印统一 Schema 结果；后端异常时兜底返回错误信息。"""
    if target not in SUPPORTED_TARGETS:
        raise ValueError("未知后端 %r，可选：%s" % (target, ", ".join(SUPPORTED_TARGETS)))
    return adapter.run(qasm, target, shots)


def show_result(result: dict, note: str = "") -> None:
    """把统一 Schema 渲染成人话。"""
    backend = result.get("backend", "?")
    shots = result.get("shots", 0)
    counts = result.get("counts", {})
    if note:
        print(note)
    print_histogram(counts, shots, "后端 %s" % backend)


# ---------------------------------------------------------------------------
# 自然语言路径：agent 生成 -> 自验（在 l2_agent 内部）-> 执行
# ---------------------------------------------------------------------------

def handle_natural_language(prompt: str) -> str:
    """调 L2 agent。返回文本：QASM 或后端推荐或错误信息。"""
    return adapter.agent_chat(prompt)


def process_agent_reply(text: str, target_hint: str = "") -> None:
    """解析 agent 返回：QASM 就跑，后端 id 就展示推荐。"""
    stripped = text.strip()
    if _is_qasm(stripped):
        target = target_hint if target_hint in SUPPORTED_TARGETS else "braket"
        print(">> Agent 生成电路，目标后端：%s（可用 /run 指定其他后端）" % target)
        result = adapter.run(stripped, target, DEFAULT_SHOTS)
        show_result(result, ">> 电路运行结果：")
    elif any(bid in stripped for bid in ("local_simulator", "spinq", "braket", "originq")):
        print(">> 后端推荐：%s" % stripped)
    else:
        print(">> %s" % stripped)


# ---------------------------------------------------------------------------
# 内置命令
# ---------------------------------------------------------------------------

HELP_TEXT = """可用命令与用法：
  直接输入自然语言  —— 描述电路意图，例如：
      "生成一个贝尔态电路并运行"
      "帮我修复这个报错的电路：OPENQASM 2.0; ..."
      "3比特的GHZ纠缠态应该用哪个后端？"
  直接粘贴 QASM     —— 贴入 OPENQASM 2.0 程序后回车，跳过 LLM 直接运行
  /help            —— 显示本帮助
  /backends        —— 显示三平台后端能力表
  /run <文件> <后端> [shots]  —— 直接运行本地 .qasm 文件（离线）
      示例：/run circuits/bell.qasm braket 8192
  /exit            —— 退出

推荐的后端 id：braket / spinq / originq（详细能力见 /backends）
"""


def cmd_backends() -> None:
    """打印 backend_capabilities.json 能力表。"""
    cap_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend_capabilities.json")
    if not os.path.exists(cap_file):
        print("（找不到 backend_capabilities.json）")
        return
    with open(cap_file, encoding="utf-8") as fh:
        caps = json.load(fh).get("backends", [])
    print("三平台后端能力表：")
    for b in caps:
        print("  id=%s | 类型=%s | 最大比特=%d | 排队=%s | 费用=%s | 需账号=%s"
              % (b["id"], b["kind"], b["max_qubits"], b["queue"], b["cost"],
                 "是" if b.get("requires_account") else "否"))
    print()


def cmd_run(args: list) -> None:
    """/run <file> <backend> [shots] —— 离线跑本地电路文件。"""
    if len(args) < 2:
        print("用法：/run <文件.qasm> <后端> [shots]")
        return
    path, target = args[0], args[1]
    shots = int(args[2]) if len(args) > 2 else DEFAULT_SHOTS
    if target not in SUPPORTED_TARGETS:
        print("未知后端 %r，可选：%s" % (target, ", ".join(SUPPORTED_TARGETS)))
        return
    if not os.path.exists(path):
        # 允许相对 starter_kit/ 的路径
        alt = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        if os.path.exists(alt):
            path = alt
        else:
            print("找不到文件：%s" % path)
            return
    with open(path, encoding="utf-8") as fh:
        qasm = fh.read()
    try:
        result = run_circuit(qasm, target, shots)
        show_result(result, ">> 本地电路 %s 运行于 %s：" % (os.path.basename(path), target))
    except Exception as exc:
        print("运行失败：%s" % exc)


def cmd_run_once(args: list) -> None:
    """--once 模式：单轮自然语言 -> 运行 -> 退出（脚本/评分友好）。"""
    prompt = " ".join(args)
    print(">> 你：%s" % prompt)
    reply = handle_natural_language(prompt)
    process_agent_reply(reply)
    if not _is_qasm(reply.strip()):
        # 如果 agent 没能给出电路，fallback：提示用户可粘贴 QASM
        print("提示：如果上面没有出现电路，你也可以直接粘贴一段 OPENQASM 2.0 程序。")


# ---------------------------------------------------------------------------
# 主循环
# ---------------------------------------------------------------------------

def repl() -> None:
    print(BANNER)
    while True:
        try:
            line = input("LoomQ-Agent > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not line:
            continue
        low = line.lower()
        if low.startswith("/exit") or low in ("quit", "exit"):
            print("再见！")
            break
        elif low.startswith("/help") or low in ("help", "帮助"):
            print(HELP_TEXT)
        elif low.startswith("/backends"):
            cmd_backends()
        elif low.startswith("/run "):
            cmd_run(line.split()[1:])
        elif _is_qasm(line):
            qasm = _read_qasm_block(line)
            try:
                result = run_circuit(qasm, "braket", DEFAULT_SHOTS)
                show_result(result, ">> 直接运行你粘贴的电路（braket 本地模拟器）：")
            except Exception as exc:
                print("运行失败：%s" % exc)
        else:
            reply = handle_natural_language(line)
            process_agent_reply(reply)


def main() -> int:
    if "--once" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--once"]
        cmd_run_once(rest)
        return 0
    if "--run" in sys.argv:
        idx = sys.argv.index("--run")
        cmd_run(sys.argv[idx + 1:])
        return 0
    repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
