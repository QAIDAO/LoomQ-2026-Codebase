#!/usr/bin/env python3
"""L2 智能体真实模型验证（需自备 OpenAI-compatible 模型服务）

用法（任选其一）：
  # 用环境变量（与正式评测同一套 LOOMQ_LLM_* 契约）
  export LOOMQ_LLM_BASE_URL="https://api.deepseek.com"
  export LOOMQ_LLM_API_KEY="sk-你的密钥"
  export LOOMQ_LLM_MODEL="deepseek-chat"     # 或 deepseek-v4-flash
  python3 starter_kit/verify_l2.py

  # 或直接传参
  python3 starter_kit/verify_l2.py \
      --base-url https://api.deepseek.com --api-key sk-xxx --model deepseek-chat

验证内容（对应赛题 L2 客观分三类任务，均为官方样例的改写变体）：
  1. 意图生成 ×4：回复须含可运行 OpenQASM 2.0，且经 L1 无噪声模拟后
     与理想分布 Hellinger 保真度 >= 0.97；
  2. 代码纠错 ×2：保持用户声明意图修复，同样验证保真度 >= 0.97；
  3. 智能选后端 ×3：回复须包含规范后端 id（对照 backend_capabilities.json）。
每个 case 先确认完成了一次有效模型调用（无调用直接判 FAIL）。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import adapter  # noqa: E402

# (prompt, 类型, 期望分布或期望后端id)
GENERATION_CASES = [
    ("生成一个 3 比特的最大纠缠态 (GHZ 态)，并进行全测量", "ghz3"),
    ("生成一个 2 比特的贝尔态并测量", "bell"),
    ("让三个量子比特各自处于均匀叠加态并测量", "uniform3"),
    ("制备一个 1 比特的 |1> 态并测量", "one"),
]
FIX_CASES = [
    ("我想制备一个贝尔态，但这段代码报错了，帮我修好：H q[0]; CX q[0] q[1]（未定义寄存器且门名大小写错误）", "bell"),
    ("帮我修复这段代码，我要 3 比特 GHZ 纠缠态：h q0; cx q0 q1; cx q0 q2（缺寄存器定义）", "ghz3"),
]
BACKEND_CASES = [
    # 15 比特 + 零排队：按官方能力表，三个本地模拟器（braket 25 / 量旋 24 / 本源 30 比特）
    # 都满足「比特数上限 + 零排队 + 免费 + 免账号」，正确答案集是三者；回复含任一即通过。
    ("我需要运行一个 15 比特电路，且零排队等待，选哪个平台？",
     ("braket_local_simulator", "spinq_taurus_simulator", "originq_local_simulator")),
    ("我要用最大的免费模拟器跑 30 比特电路", ("originq_local_simulator",)),
    ("跑 72 比特的悟空真机", ("originq_wukong",)),
]

IDEALS = {
    "ghz3": {"000": 0.5, "111": 0.5},
    "bell": {"00": 0.5, "11": 0.5},
    "uniform3": {"000": 1/8, "001": 1/8, "010": 1/8, "011": 1/8,
                 "100": 1/8, "101": 1/8, "110": 1/8, "111": 1/8},
    "one": {"1": 1.0},
}
IDEAL_QUBITS = {"ghz3": 3, "bell": 2, "uniform3": 3, "one": 1}

PASSED = 0
FAILED = 0


def hellinger(observed: dict, expected: dict) -> float:
    states = set(observed) | set(expected)
    dist = math.sqrt(
        sum((math.sqrt(observed.get(s, 0.0)) - math.sqrt(expected.get(s, 0.0))) ** 2
            for s in states)
    ) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - dist))


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  [PASS] {label}")
    else:
        FAILED += 1
        print(f"  [FAIL] {label} — {detail}")


def extract_qasm(reply: str) -> str | None:
    import re
    if not isinstance(reply, str):
        return None
    fenced = re.search(r"```(?:qasm|openqasm)?\s*(OPENQASM\s+2\.0;.*?)```",
                       reply, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    bare = re.search(r"(OPENQASM\s+2\.0;.*)", reply, re.DOTALL)
    return bare.group(1).strip() if bare else None


def verify_qasm_case(prompt: str, target: str) -> None:
    label = f"L2:{'fix' if '修复' in prompt or '修好' in prompt or '报错' in prompt else 'gen'}:{target}"
    t0 = time.time()
    reply = adapter.agent_chat(prompt)
    elapsed = time.time() - t0
    qasm = extract_qasm(reply)
    if not qasm:
        check(label, False, f"回复中无 OpenQASM 2.0（耗时 {elapsed:.0f}s）\n回复片段: {(reply or '')[:120]}")
        return
    try:
        result = adapter.run(qasm, "originq", 8192)
        observed = {k: v / result["shots"] for k, v in result["counts"].items()}
    except Exception as exc:  # noqa: BLE001
        check(label, False, f"L1 模拟运行失败: {type(exc).__name__}: {exc}")
        return
    # 比特数核对
    import re
    m = re.search(r"qreg\s+q\[\s*(\d+)\s*\]", qasm)
    n_q = int(m.group(1)) if m else 0
    if n_q != IDEAL_QUBITS[target]:
        check(label, False, f"比特数不符：期望 {IDEAL_QUBITS[target]}，得到 {n_q}（耗时 {elapsed:.0f}s）")
        return
    fid = hellinger(observed, IDEALS[target])
    check(label, fid >= 0.97,
          f"fidelity={fid:.4f}（需 ≥0.97，耗时 {elapsed:.0f}s）主峰={max(observed, key=observed.get)}")
    if fid >= 0.97:
        print(f"        电路: {qasm.splitlines()[0]} .. {len(qasm.splitlines())} 行")


def verify_backend_case(prompt: str, expected_ids: tuple) -> None:
    t0 = time.time()
    reply = adapter.agent_chat(prompt)
    elapsed = time.time() - t0
    hit = [i for i in expected_ids if i in reply]
    ok_contain = bool(hit)
    # 「首个规范 id」判法：回复开头第一个出现的后端 id 必须在答案集内
    import re
    first = None
    m = re.search(r"推荐后端：(\S+?)。", reply or "")
    if m:
        first = m.group(1).strip("`").strip()
    ok_first = first in expected_ids
    ok = ok_contain and (first is None or ok_first)
    check(f"L2:backend:{expected_ids[0]}", ok,
          f"答案集 {expected_ids}；包含命中={ok_contain}，首个id={first!r} 命中={ok_first}"
          f"（耗时 {elapsed:.0f}s）\n回复: {(reply or '')[:150]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="L2 智能体真实模型验证")
    parser.add_argument("--base-url", help="覆盖 LOOMQ_LLM_BASE_URL")
    parser.add_argument("--api-key", help="覆盖 LOOMQ_LLM_API_KEY")
    parser.add_argument("--model", help="覆盖 LOOMQ_LLM_MODEL")
    args = parser.parse_args()

    if args.base_url:
        os.environ["LOOMQ_LLM_BASE_URL"] = args.base_url
    if args.api_key:
        os.environ["LOOMQ_LLM_API_KEY"] = args.api_key
    if args.model:
        os.environ["LOOMQ_LLM_MODEL"] = args.model

    missing = [name for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")
               if not os.environ.get(name)]
    if missing:
        print("❌ 缺少模型服务配置: " + ", ".join(missing))
        print("   先设置环境变量，或传 --base-url/--api-key/--model 参数。")
        print("   自备 DeepSeek Key：https://platform.deepseek.com → API Keys")
        return 1

    print("=" * 66)
    print("L2 智能体真实模型验证（模型: %s）" % os.environ["LOOMQ_LLM_MODEL"])
    print("=" * 66)

    print("\n[1/3] 意图生成（4 个变体，保真度 ≥ 0.97）")
    for prompt, target in GENERATION_CASES:
        verify_qasm_case(prompt, target)

    print("\n[2/3] 代码纠错（2 个变体，保持意图 + 保真度 ≥ 0.97）")
    for prompt, target in FIX_CASES:
        verify_qasm_case(prompt, target)

    print("\n[3/3] 智能选后端（3 个变体，规范 id 核对）")
    for prompt, expected in BACKEND_CASES:
        verify_backend_case(prompt, expected)

    print("\n" + "=" * 66)
    print(f"结果：{PASSED} passed, {FAILED} failed")
    print("=" * 66)
    print("判定标准（赛题原文）：")
    print("  - 意图生成/纠错：产物 QASM 经无噪声模拟器验证 Fidelity ≥ 0.97 视为通过；")
    print("  - 选后端：回复须包含规范后端标识，按官方后端能力表核对；")
    print("  - 每个 case 必须完成至少一次有效模型调用（本脚本已隐含验证）。")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
