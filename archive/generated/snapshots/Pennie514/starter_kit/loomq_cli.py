#!/usr/bin/env python3
"""LoomQ 引导式命令行入口（L2 交互体验）

面向零量子背景用户：全程大白话提示，不要求先懂 QASM 或量子门。
启动：python3 starter_kit/loomq_cli.py

设计要点：菜单 4（现成实验）与菜单 5（概念讲解）**完全本地**，
未配置模型服务也能看到真实量子模拟结果与解释，不会抛异常。
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# 交互式 CLI 用行缓冲：避免后端 SDK fork 子进程时继承未刷新的块缓冲，
# 导致重定向到文件时出现重复行。
try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

import adapter  # noqa: E402

REQUIRED_LLM_ENV = ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")

BACKEND_LABELS = {
    "spinq": "量旋 SpinQit 本地模拟器",
    "originq": "本源 pyqpanda 本地模拟器",
    "braket": "AWS Braket 本地模拟器",
}

EXAMPLES = {
    "1": (
        "量子硬币：一个比特的真随机",
        "把一枚硬币立在半空——它既不是正面也不是反面，直到你看它的那一刻。\n"
        "  这不是「我们不知道结果」，而是结果在测量前真的还没定。",
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
measure q -> c;
""",
    ),
    "2": (
        "Bell 态：两个比特的纠缠",
        "两枚硬币被「绑」在一起：看了其中一枚，另一枚立刻就定了，\n"
        "  而且永远和第一枚一样。距离多远都成立。",
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
""",
    ),
    "3": (
        "GHZ 态：三个比特一起纠缠",
        "三枚硬币绑在一起：要么全是正面，要么全是反面，没有中间情况。",
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0], q[1];
cx q[0], q[2];
measure q -> c;
""",
    ),
    "4": (
        "均匀叠加：三个比特各自独立随机",
        "三枚硬币各自独立抛——8 种组合概率相同。\n"
        "  和上一个例子对比，你能直观看出「纠缠」和「独立」的差别。",
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
h q[1];
h q[2];
measure q -> c;
""",
    ),
}

CONCEPTS = {
    "1": (
        "量子比特是什么",
        "普通比特只能是 0 或 1，像一个开关。\n"
        "量子比特在被测量前可以处于 0 和 1 的「叠加」——不是「一半时间 0 一半时间 1」，\n"
        "而是同时保有两种可能。一旦测量，它才随机坍缩成 0 或 1 其中之一。",
    ),
    "2": (
        "纠缠是什么",
        "两个量子比特可以被关联起来，使得测量其中一个的瞬间，另一个的结果也随之确定。\n"
        "在 Bell 态里，你永远只会看到「都是 0」或「都是 1」，绝不会看到「一个 0 一个 1」。\n"
        "这不是事先商量好的——是量子力学里经过实验反复验证的真实现象。",
    ),
    "3": (
        "为什么要跑很多次",
        "量子测量的结果是概率性的：跑一次只能得到一个结果，看不出规律。\n"
        "所以要跑成百上千次（每次叫一个 shot），统计每种结果出现多少次，\n"
        "才能看出这个电路真正的行为。这就是结果里那张柱状图的含义。",
    ),
    "4": (
        "量子门是什么",
        "量子门是对量子比特的基本操作，相当于经典程序里的运算符。\n"
        "本工具支持 12 个标准门，常用的有：H（进入叠加）、X（翻转）、CX（产生纠缠）。\n"
        "你不需要记住它们——用菜单 1 直接描述你想要什么，让智能体来选门。",
    ),
    "5": (
        "这个工具在做什么",
        "各家量子平台的指令格式互不相通（量旋、本源、AWS 各说一套「黑话」）。\n"
        "本工具把标准 OpenQASM 2.0 翻译成三家各自的格式，一份电路到处能跑；\n"
        "再配一个智能体，让你用自然语言就能生成电路，不必先学会写 QASM。",
    ),
}


# --- 输出辅助 ---------------------------------------------------------------

def heading(text: str) -> None:
    print("\n" + "-" * 62)
    print(text)
    print("-" * 62)


def show_histogram(counts: dict, shots: int) -> None:
    """把测量结果画成柱状图。纯文本，不依赖颜色或特殊字形。"""
    if not counts:
        print("  没有测量结果——电路里可能缺少 measure 语句。")
        return
    peak = max(counts.values())
    width = 40
    print("  测量结果（每一行是一种可能的结果，条越长表示出现越频繁）：")
    for state, count in sorted(counts.items()):
        bars = "#" * max(1, int(count / peak * width))
        share = count / shots * 100
        print(f"    |{state}>  {bars:<{width}} {count:>6} 次  {share:5.1f}%")
    print(f"  共测量 {shots} 次。")


def interpret(counts: dict, shots: int) -> None:
    """用大白话解释这张分布意味着什么。"""
    if not counts:
        return
    states = sorted(counts, key=lambda s: counts[s], reverse=True)
    top = states[0]
    n_states = len(states)
    all_same = all(set(s) == {"0"} or set(s) == {"1"} for s in states)

    print("\n  这说明什么：")
    if n_states == 1:
        print(f"    结果完全确定——每次都是 |{top}>，这个电路没有随机性。")
    elif n_states == 2 and all_same and len(top) > 1:
        print("    只出现「全 0」和「全 1」两种结果，各占一半，中间情况一次都没有。")
        print("    这就是纠缠的指纹：这些比特的测量结果被锁死在一起了。")
    elif n_states == 2 ** len(top):
        print(f"    {n_states} 种组合都出现了，概率接近相同。")
        print("    这些比特各自独立随机，彼此没有关联——和纠缠正好相反。")
    else:
        print(f"    出现了 {n_states} 种结果，最常见的是 |{top}>"
              f"（{counts[top] / shots * 100:.1f}%）。")


def llm_missing() -> list:
    return [name for name in REQUIRED_LLM_ENV if not os.environ.get(name)]


def explain_llm_missing() -> None:
    """模型服务未配置时给出可执行指引，而不是抛异常。"""
    missing = llm_missing()
    heading("这个功能需要先配置模型服务")
    print("  缺少下面的环境变量：")
    for name in missing:
        print(f"    - {name}")
    print("\n  配置方法（把引号里的内容换成你自己的）：")
    print('    export LOOMQ_LLM_BASE_URL="https://api.deepseek.com/v1"')
    print('    export LOOMQ_LLM_API_KEY="你的密钥"')
    print('    export LOOMQ_LLM_MODEL="deepseek-v4-flash"')
    print("\n  现在还不想配也没关系：")
    print("    菜单 4（现成实验）和菜单 5（概念讲解）完全在本地运行，")
    print("    不需要密钥，照样能看到真实的量子模拟结果。")


def extract_qasm(text: str) -> str | None:
    """从模型回复里取出 QASM 程序。"""
    if not isinstance(text, str):
        return None
    fenced = re.search(
        r"```(?:qasm|openqasm)?\s*(OPENQASM\s+2\.0;.*?)```", text, re.DOTALL | re.IGNORECASE
    )
    if fenced:
        return fenced.group(1).strip()
    bare = re.search(r"(OPENQASM\s+2\.0;.*)", text, re.DOTALL)
    return bare.group(1).strip() if bare else None


def run_and_show(qasm: str, target: str = "spinq", shots: int = 1000) -> bool:
    """在指定后端跑电路并展示结果。出错时给出可操作建议。"""
    label = BACKEND_LABELS.get(target, target)
    print(f"\n  正在 {label} 上运行 {shots} 次……")
    sys.stdout.flush()
    try:
        result = adapter.run(qasm, target, shots)
    except Exception as exc:
        print(f"  运行失败：{type(exc).__name__}: {exc}")
        print("\n  可以检查：")
        print("    1. 电路里是否有 measure 语句（没有测量就没有结果）")
        print("    2. 比特编号是否超出了 qreg 声明的数量")
        print("    3. 依赖是否装好：pip install -r starter_kit/requirements.txt")
        return False
    show_histogram(result["counts"], result["shots"])
    interpret(result["counts"], result["shots"])
    return True


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "q"


def offer_rerun(qasm: str, used: str) -> None:
    """同一份电路换后端再跑一次——这是「统一中间层」最直观的演示。"""
    if ask("\n  换一个平台跑同一份电路？(y/n) ").lower() not in ("y", "yes"):
        return
    others = [t for t in BACKEND_LABELS if t != used]
    for index, target in enumerate(others, 1):
        print(f"    {index}. {BACKEND_LABELS[target]}")
    choice = ask("  选择 (回车取消) ")
    if choice.isdigit() and 1 <= int(choice) <= len(others):
        picked = others[int(choice) - 1]
        run_and_show(qasm, picked)
        print("\n  注意：同一份 OpenQASM 电路，未改一个字符，")
        print("  在不同厂商的平台上得到了一致的结果分布。")


def flow_generate() -> None:
    heading("用自己的话描述你想要的电路")
    print("  例如：让三个量子比特纠缠在一起，然后全部测量")
    print("        做一个两比特的随机数发生器")
    request = ask("\n  你想要什么？ ")
    if not request or request.lower() == "q":
        return
    if llm_missing():
        explain_llm_missing()
        return
    print("\n  正在请智能体把它翻译成量子电路……")
    sys.stdout.flush()
    reply = adapter.agent_chat(request)
    qasm = extract_qasm(reply)
    if not qasm:
        print("\n  智能体的回复里没有找到可运行的电路。它说：")
        print("  " + (reply or "")[:400])
        print("\n  建议把需求说得更具体，比如写明「几个比特」和「要不要测量」。")
        return
    heading("生成的电路")
    print(qasm)
    if ask("\n  现在就跑一遍看结果？(y/n) ").lower() in ("y", "yes"):
        if run_and_show(qasm):
            offer_rerun(qasm, "spinq")


def flow_fix() -> None:
    heading("修一段有问题的电路")
    print("  把代码粘进来，空行结束。也请说明你原本想做什么。")
    intent = ask("\n  你想做的是？（例如：一个贝尔态） ")
    print("  粘贴代码，然后按两次回车：")
    lines = []
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            break
        if not line.strip():
            break
        lines.append(line)
    broken = "\n".join(lines)
    if not broken.strip():
        print("  没有收到代码。")
        return
    if llm_missing():
        explain_llm_missing()
        return
    print("\n  正在诊断并修复……")
    sys.stdout.flush()
    reply = adapter.agent_chat(
        f"我想做的是{intent or '一个量子电路'}，但这段代码有问题，请修好它：\n{broken}"
    )
    qasm = extract_qasm(reply)
    if not qasm:
        print("\n  智能体没有给出可运行的修复结果。它说：")
        print("  " + (reply or "")[:400])
        return
    heading("修复后的电路")
    print(qasm)
    if ask("\n  验证一下修好了没？(y/n) ").lower() in ("y", "yes"):
        run_and_show(qasm)


def flow_backend() -> None:
    heading("帮我选一个平台")
    print("  说明你的约束，例如：我要跑 15 个比特，不想排队")
    need = ask("\n  你的要求是？ ")
    if not need or need.lower() == "q":
        return
    if llm_missing():
        explain_llm_missing()
        print("\n  各平台能力对照表（本地文件，随时可看）：")
        print("    starter_kit/backend_capabilities.md")
        return
    print("\n  正在按官方后端能力表筛选……")
    sys.stdout.flush()
    print("\n" + adapter.agent_chat(need))


def flow_examples() -> None:
    heading("现成的实验（不需要密钥，直接能跑）")
    for key, (title, _, _) in EXAMPLES.items():
        print(f"  {key}. {title}")
    choice = ask("\n  选一个 (回车返回) ")
    if choice not in EXAMPLES:
        return
    title, story, qasm = EXAMPLES[choice]
    heading(title)
    print("  " + story)
    print("\n  电路代码：")
    for line in qasm.strip().splitlines():
        print("    " + line)
    if run_and_show(qasm):
        offer_rerun(qasm, "spinq")


def flow_concepts() -> None:
    heading("量子概念讲解（大白话，没有公式）")
    for key, (title, _) in CONCEPTS.items():
        print(f"  {key}. {title}")
    choice = ask("\n  想了解哪个 (回车返回) ")
    if choice not in CONCEPTS:
        return
    title, body = CONCEPTS[choice]
    heading(title)
    for line in body.splitlines():
        print("  " + line)


# --- 主菜单 -----------------------------------------------------------------

MENU = (
    ("1", "用自己的话生成一个量子电路", flow_generate),
    ("2", "修一段报错的电路", flow_fix),
    ("3", "帮我选一个运行平台", flow_backend),
    ("4", "跑现成的实验（不需要密钥）", flow_examples),
    ("5", "量子概念讲解（大白话）", flow_concepts),
)


def main() -> int:
    print("=" * 62)
    print("LoomQ · 让不懂「黑话」的人也能用上量子计算")
    print("=" * 62)
    print("\n第一次用？建议从 4 开始——它不需要任何配置，")
    print("能直接看到真实的量子模拟结果和解释。")

    if llm_missing():
        print("\n提示：模型服务尚未配置，菜单 1/2/3 会先告诉你怎么配。")
        print("      菜单 4/5 完全本地，现在就能用。")

    while True:
        print("\n" + "=" * 62)
        for key, title, _ in MENU:
            print(f"  {key}. {title}")
        print("  q. 退出")
        choice = ask("\n请选择: ").lower()
        if choice in ("q", "quit", "exit"):
            print("\n再见。想继续探索就再跑一次：python3 starter_kit/loomq_cli.py")
            return 0
        for key, _, handler in MENU:
            if choice == key:
                handler()
                break
        else:
            if choice:
                print(f"  没有「{choice}」这个选项，请输入 1-5 或 q。")


if __name__ == "__main__":
    sys.exit(main())
