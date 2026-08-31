#!/usr/bin/env python3
"""容错提示实测：用"用户不配合"的输入去撞 Agent，看它怎么接

赛题第五节 3（主观分 10 分）的原文是：
    评委现场测试 Agent 面对零物理背景用户的交互友好度、**容错提示**与结果可视化。

`probe_l2_live.py` 测的是"题目问得清楚时能不能答对"。
这个脚本测的是另一半：**题目问得不清楚、问错了、或者根本不该问时，Agent 怎么接。**
评委现场不会照着标准 prompt 念——零物理背景的用户本来就问不出标准 prompt。

**这里没有自动判分**，因为"友好"不是布尔值。脚本负责把回复原样打出来，
判定标准写在下面，人工过一遍：

    A. 不装懂    —— 做不到 / 超范围的事，明确说做不到，不糊弄、不编
    B. 给下一步  —— 不是只说"不行"，而是给出用户接下来能做什么
    C. 不甩术语  —— 解释里不出现没铺垫过的行话
    D. 不误导    —— 用户的前提错了，要纠正前提，而不是顺着错前提往下答

用法（配置从环境变量或 .env 文件自动读，不用手动 export）：

    python3 starter_kit/tools/probe_l2_robustness.py
    python3 starter_kit/tools/probe_l2_robustness.py --only 3
"""

import argparse
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from starter_kit import adapter  # noqa: E402
from starter_kit.loomq import envfile  # noqa: E402

# (这一类不配合叫什么, 用户实际会打出来的话, 我们希望回复里出现什么)
CASES = [
    ("说不清要什么",
     "我想试试量子",
     "该反问或给出几个可选的具体目标，而不是自己随便挑一个就开始生成"),

    ("要的东西不在范围内",
     "帮我用量子计算机挖矿",
     "该说清挖矿不是量子计算擅长的事，并给出它擅长什么"),

    ("前提本身是错的",
     "量子计算机能同时试出所有答案，帮我用它把一个密码全试一遍",
     "该纠正「同时试所有答案」这个误解，而不是顺着它写电路"),

    ("贴了一段无关的东西",
     "def hello():\n    print('hi')\n\n这个能跑吗",
     "该指出这是普通 Python、不是量子电路，并问用户到底想做什么"),

    ("提了一个平台满足不了的要求",
     "帮我在真机上跑一个 100 比特的电路，现在就要，不要排队",
     "必须走查表那条路：逐条说明哪一项满足不了、最接近的是哪几个。"
     "泛泛解释一句「做不到」算不合格——加 reject 那条路时，这题曾经被 reject 抢走过"),

    ("打字乱且缺信息",
     "ghz 3bit 跑一下",
     "信息其实够了，该正常完成，不该因为格式不规范就拒答"),

    ("问的是「我该干什么」而不是任务",
     "我完全不懂量子，第一个实验应该做什么？",
     "该给一个具体、极小、能立刻跑的起点，而不是讲一堆概念"),

    ("要求解释而不是要代码",
     "你刚才给我的那个 h 是什么意思？我不懂物理",
     "该用不带行话的话解释，且不该假设用户读过前文术语"),
]


def main():
    parser = argparse.ArgumentParser(description="容错提示实测（需要真模型）")
    parser.add_argument("--only", type=int, help="只跑第几条（从 1 开始）")
    args = parser.parse_args()

    if not envfile.require("容错实测"):
        return 2
    print("模型：%s   端点：%s" % (os.environ["LOOMQ_LLM_MODEL"], os.environ["LOOMQ_LLM_BASE_URL"]))
    print("（不打印密钥）")
    print("\n本脚本不自动判分。判定标准：A 不装懂 / B 给下一步 / C 不甩术语 / D 不误导\n")

    cases = list(enumerate(CASES, start=1))
    if args.only:
        cases = [c for c in cases if c[0] == args.only]

    for index, (kind, prompt, want) in cases:
        print("=" * 74)
        print("[%02d] %s" % (index, kind))
        print("用户说：%s" % prompt.replace("\n", "\n        "))
        print("期望：%s" % want)
        print("-" * 74)
        started = time.monotonic()
        try:
            reply = adapter.agent_chat(prompt)
        except Exception as exc:  # noqa: BLE001
            reply = "【抛异常】%s: %s" % (type(exc).__name__, exc)
        print(reply)
        print("(%.1fs)\n" % (time.monotonic() - started))

    return 0


if __name__ == "__main__":
    sys.exit(main())
