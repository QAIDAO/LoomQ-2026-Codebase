#!/usr/bin/env python3
"""L2 实测打分：拿真模型跑一批 prompt 变体，按评委的判法自己打一次分

`verify_l2.py` 用桩模型测的是"我们的代码在模型各种表现下拿不拿得住"。
这个脚本测的是另一件事：**接上真模型之后，实际能得多少分。**

正式评测的规则（赛题第五节 2）：
- 三类任务：意图生成 / 代码纠错 / 智能选后端
- **实际使用未公开的同类变体**（改写措辞、更换比特数与目标态）
- 12 个 case，每个限时 120 秒
- 客观分 = 通过率 × 20

所以这里也用变体，而不是照抄官方示例——照抄示例测出来的通过率没有意义。

**判分标准与评委一致**：
- 生成 / 纠错：从回复里提取 QASM，真的跑一遍，与目标态的保真度 ≥ 0.97
- 选后端：回复中必须出现正确答案集里的规范标识

**每道题的标准答案是写死在这个文件里的**，不是从 Agent 自己的判断里取的——
否则 Agent 把目标态认错时，判分也会跟着错，测出来的通过率是假的。

用法（配置从环境变量或 .env 文件自动读，不用手动 export）：

    python3 starter_kit/tools/probe_l2_live.py
    python3 starter_kit/tools/probe_l2_live.py --only backend
"""

import argparse
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from starter_kit import adapter  # noqa: E402
from starter_kit.evaluator import calculate_hellinger_fidelity, extract_qasm  # noqa: E402
from starter_kit.loomq import envfile  # noqa: E402

THRESHOLD = 0.97
SHOTS = 8192


def ghz(n):
    return {"0" * n: 0.5, "1" * n: 0.5}


def uniform(n):
    return {format(v, "0%db" % n): 1.0 / (2**n) for v in range(2**n)}


def w(n):
    share = 1.0 / n
    return {"".join("1" if p == i else "0" for p in range(n - 1, -1, -1)): share for i in range(n)}


# (类别, prompt, 标准答案)
#   circuit 类 -> 标准答案是理想分布（写死，不从 Agent 的判断里取）
#   backend 类 -> 标准答案是可接受的规范标识集合
CASES = [
    # ---------- 意图生成 ----------
    ("circuit", "生成一个 3 比特的最大纠缠态 (GHZ 态)，并进行全测量", ghz(3)),
    ("circuit", "帮我写一个贝尔态的电路，两个比特都要测量", ghz(2)),
    ("circuit", "我想要一个 4 比特的 GHZ 态，全部测量出来", ghz(4)),
    ("circuit", "做一个 2 比特的电路，让四种结果等概率出现，并且测量", uniform(2)),
    ("circuit", "请给我一个 5 比特的最大纠缠态，全测量", ghz(5)),
    ("circuit", "生成一个 3 比特的 W 态并全测量", w(3)),
    # ---------- 代码纠错（prompt 里明确声明目标态）----------
    ("circuit", "我想制备一个贝尔态，但这段代码报错了，帮我修好：\nH q[0]; CX q[0] q[1]", ghz(2)),
    ("circuit", "下面这段想做 3 比特 GHZ 态，但跑不起来，帮我改对：\n"
                "OPENQASM 2.0;\nqreg q[3];\nh q[0];\ncx q[0],q[1];\ncx q[1],q[2];", ghz(3)),
    ("circuit", "这段代码我想让它输出贝尔态，但结果不对，帮我看看：\n"
                "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\ncreg c[2];\n"
                "h q[0];\nmeasure q -> c;", ghz(2)),
    ("circuit", "帮我修好这个 4 比特 GHZ 电路，它用了不存在的门：\n"
                "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[4];\ncreg c[4];\n"
                "h q[0];\ncy q[0],q[1];\ncy q[1],q[2];\ncy q[2],q[3];\nmeasure q -> c;", ghz(4)),
    # ---------- 智能选后端 ----------
    ("backend", "我需要运行一个 15 比特电路，且零排队等待，选哪个平台？",
     {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
    ("backend", "我想在真实的量子硬件上跑一个 5 比特电路，但不想花钱，用哪个？",
     {"spinq_cloud_qpu", "originq_wukong"}),
    ("backend", "我一个账号都不想注册，想跑 20 比特的电路，有什么选择？",
     {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
    ("backend", "我要跑一个 50 比特的电路，要模拟器，而且不能排队，推荐哪个？",
     {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
    ("backend", "预算无所谓，我要比特数最多的真机，选谁？", {"originq_wukong"}),
]


def grade_circuit(reply, ideal):
    qasm = extract_qasm(reply)
    if not qasm:
        return False, "回复里提取不到 OpenQASM 2.0 程序"
    try:
        payload = adapter.run(qasm, "originq", SHOTS)
    except Exception as exc:  # noqa: BLE001
        return False, "产物跑不起来：%s: %s" % (type(exc).__name__, exc)
    observed = {key: value / SHOTS for key, value in payload["counts"].items()}
    fidelity = calculate_hellinger_fidelity(observed, ideal)
    return fidelity >= THRESHOLD, "保真度 %.4f" % fidelity


def grade_backend(reply, acceptable):
    hits = sorted(item for item in acceptable if item in reply)
    if hits:
        return True, "命中 %s" % "、".join(hits)
    return False, "回复中没有出现任何正确的规范标识"


def main():
    parser = argparse.ArgumentParser(description="L2 实测打分（需要真模型）")
    parser.add_argument("--only", choices=("circuit", "backend"), help="只跑某一类")
    args = parser.parse_args()

    if not envfile.require("L2 实测打分"):
        return 2
    print("模型：%s   端点：%s" % (os.environ["LOOMQ_LLM_MODEL"], os.environ["LOOMQ_LLM_BASE_URL"]))
    print("（不打印密钥）\n")

    cases = [c for c in CASES if not args.only or c[0] == args.only]
    passed = 0
    slowest = 0.0
    failures = []

    for index, (kind, prompt, expected) in enumerate(cases, start=1):
        started = time.monotonic()
        try:
            reply = adapter.agent_chat(prompt)
            error = None
        except Exception as exc:  # noqa: BLE001
            reply, error = "", "agent_chat 抛异常：%s: %s" % (type(exc).__name__, exc)
        elapsed = time.monotonic() - started
        slowest = max(slowest, elapsed)

        if error:
            ok, detail = False, error
        elif kind == "circuit":
            ok, detail = grade_circuit(reply, expected)
        else:
            ok, detail = grade_backend(reply, expected)

        passed += ok
        first_line = prompt.splitlines()[0]
        print("%s [%02d] %-6s %5.1fs  %-34s %s"
              % ("✅" if ok else "❌", index, kind, elapsed,
                 first_line[:34], detail))
        if not ok:
            failures.append((index, prompt, detail, reply))

    total = len(cases)
    rate = passed / total if total else 0.0
    print("\n" + "=" * 72)
    print("通过 %d / %d  =  %.0f%%    最慢一题 %.1f 秒（正式评测每题限时 120 秒）"
          % (passed, total, rate * 100, slowest))
    print("按客观分 20 分折算：约 %.1f 分" % (rate * 20))

    for index, prompt, detail, reply in failures:
        print("\n" + "-" * 72)
        print("第 %d 题失败：%s" % (index, detail))
        print("prompt: %s" % prompt.replace("\n", " ⏎ ")[:200])
        print("回复前 600 字：\n%s" % reply[:600])

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
