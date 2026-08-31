#!/usr/bin/env python3
"""Interactive console for non-experts — L2 UX entry point.

Zero dependencies, pure stdin/stdout. Two modes:

    python cli.py                          # REPL chat
    python cli.py "生成3比特GHZ态并测量"     # one-shot, prints answer

REPL extras: :demo walks through the three showcase tasks; :backend lists
the live capability table; :run <file.qasm> executes a circuit locally and
prints an ASCII histogram; :help shows commands.
"""

from __future__ import annotations

import os
import sys
from collections import Counter

try:
    from .adapter import agent_chat, run
    from .config import describe, LoomqConfig
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from adapter import agent_chat, run
    from config import describe, LoomqConfig


BANNER = r"""
  _                      ___  ___ ______ _
 | |                    / _ \/ _ \___  /| |
 | |    __ _ _____   _ / /_\ \(_)//  / /| |
 | |   / _` |_  / | | |  _  |/ _ \ / /_| |
 | |__| (_| |/ /| |_| | | | | (_)/ /\  |
 |_____\__,_/___|\__,_\_| |_/\___/_/  \_|
 让不懂量子的人，也能指挥量子计算机 —— 输入自然语言即可
"""


def _histogram(counts: dict[str, int], width: int = 32) -> str:
    total = sum(counts.values()) or 1
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:8]
    lines = []
    for key, hits in top:
        bar = "█" * max(1, round(width * hits / total))
        lines.append("  %s  %-6.2f%% %s" % (key.ljust(8), 100.0 * hits / total, bar))
    return "\n".join(lines)


def _capabilities_table() -> str:
    try:
        from .plugin_loader import load_plugins
        from .di import bootstrap
    except ImportError:
        from plugin_loader import load_plugins
        from di import bootstrap
    registry = load_plugins(LoomqConfig.load())
    rows = ["%-28s %-9s %6s  %-14s %s" %
            ("backend id", "kind", "qubits", "queue", "cost")]
    for row in registry.capability_table():
        rows.append("%-28s %-9s %6d  %-14s %s" %
                    (row["id"], row["kind"], row["max_qubits"],
                     row["queue"], row["cost"]))
    return "\n".join(rows)


def _run_file(path: str) -> None:
    try:
        qasm = open(path, encoding="utf-8").read()
        result = run(qasm, "spinq", 2048)
    except OSError as exc:
        print("  无法读取文件：%s" % exc)
        return
    except Exception as exc:
        print("  运行失败：%s: %s" % (type(exc).__name__, exc))
        return
    print("  backend=%s engine=%s shots=%d" %
          (result["backend"], result.get("engine", "-"), result["shots"]))
    print("  测量结果分布：")
    print(_histogram(result["counts"]))


DEMOS = (
    ("① 自然语言生成电路", "帮我生成一个 3 比特 GHZ 最大纠缠态并进行全测量"),
    ("② 智能修复报错代码", "我想制备一个贝尔态，但这段代码报错了，帮我修好："
                           "H q[0]; CX q[0] q[1]（未定义寄存器且门名大小写错误）"),
    ("③ 智能选择后端", "我需要运行一个 15 比特电路，而且要求零排队等待、完全免费，选哪个平台？"),
)

GLOSSARY = {
    "量子比特": "经典比特只能是 0 或 1；量子比特（qubit）可以同时“部分是 0、部分是 1”，"
              "这种状态叫叠加。n 个量子比特能同时承载 2^n 个振幅信息。",
    "叠加": "把多个可能状态按“振幅”组合在一起。测量前谁也说不准结果，"
           "测量时按概率坍缩成某一个确定状态。",
    "纠缠": "两个量子比特共享同一个整体状态：测其中一个，另一个瞬间确定。"
           "贝尔态就是最简单的两比特最大纠缠态。",
    "测量": "读取量子比特的唯一方式，会把叠加态坍缩成一个经典比特。"
           "所以 QASM 里 measure 必须显式写出，重复运行会得到统计分布。",
    "h门": "Hadamard 门：把 |0> 变成 50%/50% 叠加，是几乎所有量子算法的起手式。",
    "cnot门": "受控翻转门：目标比特在控制比特为 1 时翻转。H+CNOT 组合即可造出贝尔纠缠态。",
    "ghz态": "多比特最大纠缠态：(|00…0> + |11…1>)/√2。3 比特 GHZ 用 H + 两条 CNOT 就能制备。",
    "贝尔态": "两比特最大纠缠态 (|00>+|11>)/√2：只会测到 00 或 11，各一半概率。",
    "w态": "(|100>+|010>+|001>)/√3：恰好有一个 1，且三个位置等概率，纠缠结构比 GHZ 更微妙。",
}

HELP = """\
命令：
  直接输入中文需求      生成 QASM / 修错 / 推荐后端
  :start                零基础引导：从概念到第一次运行
  :demo                 三个示例任务演示
  :explain <关键词>     量子概念速查（如 :explain 纠缠）
  :backend              查看后端能力表
  :run <file.qasm>     本地运行一个 QASM 文件并画出直方图
  :status               显示当前配置（密钥脱敏）
  :help                 本帮助
  :quit / :q            退出
提示：配置 LOOMQ_LLM_BASE_URL / API_KEY / MODEL 后接入大模型；
     未配置时使用内置确定性引擎，依然可以完成三类任务。"""


def _try_command(line: str) -> bool:
    """Handle a ':' command; return False when the line is a normal prompt."""
    lowered = line.lower()
    if lowered in (":q", ":quit", ":exit"):
        raise SystemExit(0)
    if lowered in (":help", ":h", "?"):
        print(HELP)
        return True
    if lowered == ":start":
        _guided_tour()
        return True
    if lowered.startswith(":explain"):
        parts = line.split(None, 1)
        if len(parts) < 2:
            print("  用法：:explain <关键词>，可选：%s" % "、".join(sorted(GLOSSARY)))
        else:
            key = parts[1].strip().lower().replace(" ", "")
            entry = GLOSSARY.get(key) or GLOSSARY.get(key.replace("门", ""))
            print("  %s" % entry) if entry else print(
                "  暂无该词条。可选：%s" % "、".join(sorted(GLOSSARY)))
        return True
    if lowered == ":demo":
        for title, demo_prompt in DEMOS:
            print("\n—— %s ——" % title)
            print("你：%s" % demo_prompt)
            _answer(demo_prompt)
        return True
    if lowered == ":backend":
        print(_capabilities_table())
        return True
    if lowered == ":status":
        print("  %s" % describe(LoomqConfig.load()))
        return True
    if lowered.startswith(":run"):
        parts = line.split(None, 1)
        if len(parts) < 2:
            print("  用法：:run <file.qasm>")
        else:
            _run_file(parts[1].strip())
        return True
    if lowered.startswith(":"):
        print("  未知命令，输入 :help 查看可用命令。")
        return True
    return False


def repl() -> None:
    print(BANNER)
    try:
        cfg = LoomqConfig.load()
        print("  配置：%s" % describe(cfg))
        if not cfg.llm.configured:
            print("  （未检测到 LLM 环境变量 —— 当前为离线模式，输入 :help 查看说明）")
    except Exception:
        pass
    print()
    while True:
        try:
            line = input("loomq> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.startswith(":"):
            try:
                _try_command(line)
            except SystemExit:
                break
            continue
        _answer(line)
    print("再见！愿你早日跑出第一个量子实验。")


def _guided_tour() -> None:
    """Zero-basis walkthrough: concept -> generate -> run -> read results."""
    print("""
—— 第 1 步 · 30 秒概念 ——
  量子比特可以叠加（同时“部分 0 部分 1”），纠缠让多个比特联动，
  测量把它们坍缩成经典比特串。下面我们亲手走一遍这条链路。""")
    print("—— 第 2 步 · 用一句中文生成电路 ——")
    _answer(DEMOS[0][1])
    print("""
—— 第 3 步 · 本地运行并读结果 ——
  把上面的 QASM 存成文件后可用 :run ghz.qasm 执行；
  这里直接替你跑一次：""")
    bell_qasm = ("OPENQASM 2.0;\ninclude \"qelib1.inc\";\n"
                 "qreg q[2]; creg c[2];\nh q[0];\ncx q[0],q[1];\nmeasure q -> c;\n")
    try:
        result = run(bell_qasm, "spinq", 2048)
        print("  贝尔态只会出现 00 和 11，各约 50%%：这就是纠缠的直接证据。")
        print(_histogram(result["counts"]))
    except Exception as exc:
        print("  运行失败：%s: %s" % (type(exc).__name__, exc))
    print("""
—— 第 4 步 · 接下来你可以 ——
  输入任意中文需求（如“生成 5 比特均匀叠加态并测量”）；
  :demo 看三个完整案例；:explain 查概念；:backend 选平台。
  遇到报错？把报错代码直接贴进来，我会修好并解释。""")


def _answer(prompt: str) -> None:
    print("…")
    try:
        reply = agent_chat(prompt)
    except Exception as exc:
        print("  出错了：%s: %s" % (type(exc).__name__, exc))
        print("  可以换个说法再试一次，例如“生成2比特贝尔态并测量”。")
        return
    print(reply)


def main(argv: list[str]) -> int:
    args = [a for a in argv if a.strip()]
    if not args:
        repl()
        return 0
    pending_prompt: list[str] = []
    for token in args:
        if token.startswith(":"):
            if pending_prompt:
                _answer(" ".join(pending_prompt))
                pending_prompt = []
            try:
                _try_command(token)
            except SystemExit:
                pass
        else:
            pending_prompt.append(token)
    if pending_prompt:
        _answer(" ".join(pending_prompt))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
