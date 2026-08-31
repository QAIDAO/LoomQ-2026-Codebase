#!/usr/bin/env python3
"""LoomQ CLI —— 让零量子背景的用户也能指挥真实量子计算机。

交互入口（L2 交互体验交付）。用法：

    python3 cli_agent.py "生成 3 比特 GHZ 态并测量"
    python3 cli_agent.py --target spinq --shots 8192 "制备贝尔态"
    python3 cli_agent.py --interactive      # 对话模式

流程：自然语言 → agent_chat 生成/修复 QASM → 自验 → transpile → run
（本地模拟器）→ 把 counts 翻译成"人话"。

--real 可用 real_backends.py 提交到真实量子计算机（需装 SDK 与凭证）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapter import (  # noqa: E402
    agent_chat,
    run,
    transpile,
    SUPPORTED_TARGETS,
    parse_qasm,
)


def _translate_counts(counts, num_qubits, expected_hint=None):
    """把二进制 counts 翻译成零基础用户能看懂的话（含 ASCII 可视化）。"""
    total = sum(counts.values())
    if not total:
        return "没有拿到任何测量结果。"
    probs = {k: v / total for k, v in counts.items()}
    top = sorted(probs.items(), key=lambda kv: -kv[1])

    # ASCII 条形图（无门槛可视化）：展示主要状态的概率
    lines = []
    lines.append("测量结果分布（共 %d 次采样）：" % total)
    bar = "  "
    for state, p in top[:6]:
        width = max(1, int(round(p * 30)))
        bar += "|%s> %s %.1f%%\n  " % (state, "█" * width, p * 100)
    lines.append(bar.rstrip() + "  ")

    all0 = "0" * num_qubits
    all1 = "1" * num_qubits
    p0 = probs.get(all0, 0)
    p1 = probs.get(all1, 0)

    if abs(p0 - 0.5) < 0.08 and abs(p1 - 0.5) < 0.08:
        lines.append("提示：|%s> 和 |%s> 各占约一半 —— 这正是一个最大纠缠态 "
                     "（GHZ/贝尔态）的特征，量子比特之间确实发生了纠缠。" % (all0, all1))
    elif len(probs) >= (1 << (num_qubits - 1)):
        lines.append("提示：结果在所有状态上大致均匀 —— 量子比特处于均匀叠加。")
    else:
        dominant = top[0]
        lines.append("提示：主峰集中在 |%s>（%.1f%%），其余为噪声/统计涨落。"
                     % (dominant[0], dominant[1] * 100))
    return "\n".join(lines)


def _extract_prompt_qasm(reply):
    """agent_chat 通常直接返回裸 QASM，无需额外解析。"""
    if "OPENQASM" in reply:
        return reply
    return None


def run_one(prompt, target="spinq", shots=8192, real=False, chip=None):
    print("→ 你在问：%s" % prompt)
    print("→ 智能体正在理解你的意图……")
    reply = agent_chat(prompt)

    qasm = _extract_prompt_qasm(reply)
    if not qasm:
        print("智能体返回（非 QASM）：\n%s" % reply)
        return None

    print("→ 已生成 / 修复的电路（已自验）：")
    print("  " + qasm.replace("\n", "\n  "))

    circ = parse_qasm(qasm)
    print("→ 电路信息：%d 个量子比特，%d 个门。" % (circ.num_qubits, len(circ.gates)))

    if real:
        print("→ 正在提交真实量子计算机……（需要 SDK 与凭证，凭证通过环境变量注入）")
        try:
            from real_backends import spinq_cloud_run, originq_cloud_run
            if target == "originq":
                result = originq_cloud_run(qasm, shots=shots, chip=chip)
            else:
                result = spinq_cloud_run(qasm, shots=shots)
        except Exception as exc:
            print("✗ 真机提交失败：%s" % exc)
            print("  提示：可用本地模拟器先体验，或在装好 SDK/凭证后重试。")
            return None
    else:
        print("→ 正在本地模拟器上运行（%s）……" % target)
        result = run(qasm, target, shots)

    print("→ 统一结果 Schema：")
    print("  backend : %s" % result["backend"])
    print("  job_id  : %s" % result["job_id"])
    print(_translate_counts(result["counts"], circ.num_qubits))
    return result


def interactive(target, shots, real, chip=None):
    print("LoomQ 量子助手 —— 直接用中文描述你想做什么（输入 exit 退出）。")
    print("示例：'生成 3 比特 GHZ 态并测量'、'帮我修好这段报错代码'、'选个免费无排队的后端'")
    while True:
        try:
            prompt = input("\n你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not prompt:
            continue
        if prompt.lower() in ("exit", "quit", "退出"):
            break
        run_one(prompt, target=target, shots=shots, real=real, chip=chip)


def main():
    parser = argparse.ArgumentParser(description="LoomQ 量子助手 CLI")
    parser.add_argument("prompt", nargs="*", help="自然语言意图（不填则进入交互模式）")
    parser.add_argument("--target", choices=SUPPORTED_TARGETS, default="spinq")
    parser.add_argument("--shots", type=int, default=8192)
    parser.add_argument("--real", action="store_true",
                        help="提交到真实量子计算机（需 SDK 与凭证，凭证走环境变量）")
    parser.add_argument("--chip", default=None,
                        help="本源真机标识（如 origin_72 / WK_C180_2），缺省读 LOOMQ_ORIGINQ_CHIP")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args()

    if args.prompt:
        prompt = " ".join(args.prompt)
        result = run_one(prompt, target=args.target, shots=args.shots,
                         real=args.real, chip=args.chip)
        if args.json and result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result else 1)
    else:
        interactive(args.target, args.shots, args.real, args.chip)


if __name__ == "__main__":
    main()