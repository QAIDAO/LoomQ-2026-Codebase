#!/usr/bin/env python3
"""LoomQ L2 私有变体自测（12 个 case，模拟正式评测的判定方式）。

用法（在 fork 根目录）：

    export LOOMQ_LLM_BASE_URL=https://api.deepseek.com
    export LOOMQ_LLM_API_KEY=<你的 Key>
    export LOOMQ_LLM_MODEL=deepseek-v4-flash
    export LOOMQ_LLM_TIMEOUT_SECONDS=120
    python3 tools/l2_selfcheck.py

可选参数：
    --only generate|repair|backend   只跑某一类
    --case C03                       只跑某个 case
    --repeat 2                       每个 case 跑 N 遍，观察稳定性
    --json-out tools/l2_selfcheck.json
    --show                           打印模型完整回复（调试用）

判定完全在本地做，与模型无关：
  * 生成/纠错类：抽出 QASM -> 解析 -> 无噪声模拟 -> 与本文件写死的目标分布比较，
    Fidelity >= 0.97 视为通过（与题面一致）。
  * 选后端类：从回复中抽取规范后端 id，必须恰好命中一个且落在可接受答案集内。

本脚本不参与评分，也不会被 adapter 引用；它只是把"正式评测会怎么判"复现在本地。
不要提交任何 Key。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "starter_kit"))

try:  # 优先走正式入口，和评测器一致
    from starter_kit.adapter import agent_chat
except Exception:  # 缺少 braket/pyqpanda 时退回直接调用 agent
    from starter_kit.l2_agent import agent_chat  # type: ignore

from starter_kit.l2.normalize import normalize
from starter_kit.l2.simulate import simulate
from starter_kit.l2.verify import fidelity

FIDELITY_THRESHOLD = 0.97
CASE_TIME_LIMIT = 120.0
QASM_START = re.compile(r"OPENQASM\s+2\.0\s*;", re.IGNORECASE)
BACKEND_ID = re.compile(r"\b(?:spinq|originq|braket)_[a-z0-9_]+\b")


def uniform(n: int) -> dict:
    states = [format(i, f"0{n}b") for i in range(1 << n)]
    return {state: 1.0 / len(states) for state in states}


# --- 12 个私有变体 --------------------------------------------------------
# 措辞、比特数和目标态都与公开示例不同，重点覆盖两类历史上会挂的路径：
#   * 真机 + 附加约束（放宽时不能退化成模拟器）
#   * 非内置目标态（模型只要标 custom 就可能绕过语义校验）
CASES = [
    # ---------- 意图生成 ----------
    dict(id="C01", kind="generate", note="GHZ 换比特数",
         prompt="我要做一个四个量子比特都纠缠在一起的态，就是那种要么全 0 要么全 1 的，"
                "然后把四个比特都测量出来。",
         expect={"0000": 0.5, "1111": 0.5}),
    dict(id="C02", kind="generate", note="均匀叠加",
         prompt="帮我准备 3 个量子比特的等概率叠加态，8 种结果出现的机会一样大，全部测量。",
         expect=uniform(3)),
    dict(id="C03", kind="generate", note="W 态（非 GHZ 的多体纠缠）",
         prompt="请生成一个 3 比特的 W 态，也就是恰好有一个比特为 1、三种情况等概率，并全测量。",
         expect={"001": 1 / 3, "010": 1 / 3, "100": 1 / 3}),
    dict(id="C04", kind="generate", note="计算基态（位序陷阱）",
         prompt="给我一个 3 比特电路，让测量结果确定性地是 101，并把三个比特都测出来。",
         expect={"101": 1.0}),
    dict(id="C05", kind="generate", note="custom：反相纠缠，非内置 kind",
         prompt="我需要两个比特的纠缠态，但要求测出来永远相反：一个是 0 另一个就是 1，"
                "两种情况各一半概率，两个比特都要测量。",
         expect={"01": 0.5, "10": 0.5}),
    dict(id="C06", kind="generate", note="custom：带翻转的三比特均匀叠加",
         prompt="做一个 3 比特电路：q[0] 和 q[2] 处于等概率叠加，q[1] 固定为 |1>，"
                "三个比特全部测量（c[k] 对应 q[k]）。",
         expect={"010": 0.25, "011": 0.25, "110": 0.25, "111": 0.25}),

    # ---------- 位序诊断（目标态在位串翻转下不对称）----------
    dict(id="C13", kind="generate", note="基态 100（非回文，专测位序）",
         prompt="给我一个 3 比特电路，让测量结果确定性地是 100，并把三个比特都测出来。",
         expect={"100": 1.0}),
    dict(id="C14", kind="generate", note="q[0] 固定为 1，其余叠加（C06 的镜像）",
         prompt="做一个 3 比特电路：q[1] 和 q[2] 处于等概率叠加，q[0] 固定为 |1>，"
                "三个比特全部测量（c[k] 对应 q[k]）。",
         expect={"001": 0.25, "011": 0.25, "101": 0.25, "111": 0.25}),

    # ---------- 代码纠错 ----------
    dict(id="C07", kind="repair", note="缺寄存器 + 大小写 + 越界",
         prompt="我想制备一个贝尔态（两个比特同为 0 或同为 1），但这段代码报错了，帮我修好：\n"
                "H q[0]; CX q[0] q[2];",
         expect={"00": 0.5, "11": 0.5}),
    dict(id="C08", kind="repair", note="漏测量 + 目标是 GHZ3",
         prompt="目标是 3 比特 GHZ 态并测量全部比特，但下面这段少了点东西，请修复：\n"
                "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[3];\ncreg c[3];\n"
                "h q[0];\ncx q[0],q[1];\nmeasure q[0] -> c[0];",
         expect={"000": 0.5, "111": 0.5}),
    dict(id="C09", kind="repair", note="门用错（cx 写成 cz 语义）",
         prompt="我要的是两个比特测量结果始终相同的纠缠态，但这段跑出来两个比特没有关联，"
                "帮我改对并保持全测量：\n"
                "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\ncreg c[2];\n"
                "h q[0];\nh q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];",
         expect={"00": 0.5, "11": 0.5}),

    # ---------- 智能选后端 ----------
    dict(id="C10", kind="backend", note="真机 + 免费 + 零排队（约束冲突，绝不能给模拟器）",
         prompt="我想把电路跑在真正的量子硬件上，最好是免费的、而且不用排队等太久，选哪个平台？",
         accept={"spinq_cloud_qpu", "originq_wukong"}, ideal="spinq_cloud_qpu"),
    dict(id="C11", kind="backend", note="真机 + 不可能的比特数（只能放宽容量）",
         prompt="我需要在真实量子计算机上跑一个 100 比特的电路，你推荐哪个后端？",
         accept={"originq_wukong"}, ideal="originq_wukong"),
    dict(id="C12", kind="backend", note="无账号 + 免费 + 容量（应给本地模拟器）",
         prompt="我没有任何云平台账号，也不想付费，只想在本机跑一个 20 比特的电路，用什么？",
         accept={"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"},
         ideal="braket_local_simulator"),
]


def extract_qasm(text: str) -> str | None:
    match = QASM_START.search(text)
    if not match:
        return None
    tail = text[match.start():]
    fence = re.search(r"^\s*```", tail, re.MULTILINE)
    return (tail[: fence.start()] if fence else tail).strip()


def judge(case: dict, answer: str) -> tuple[bool, str]:
    if case["kind"] == "backend":
        found = sorted(set(BACKEND_ID.findall(answer)))
        if not found:
            return False, "回复里没有规范后端标识"
        if len(found) > 1:
            return False, f"回复里出现多个后端标识：{found}"
        picked = found[0]
        if picked not in case["accept"]:
            return False, f"选了 {picked}，可接受集合是 {sorted(case['accept'])}"
        flag = "" if picked == case["ideal"] else f"（非首选，首选 {case['ideal']}）"
        return True, f"{picked}{flag}"

    qasm = extract_qasm(answer)
    if not qasm:
        return False, "回复里没有可解析的 OpenQASM 2.0 程序"
    try:
        _, circuit = normalize(qasm)
        observed = simulate(circuit)
    except Exception as exc:
        return False, f"电路无法解析或模拟：{type(exc).__name__}: {exc}"
    score = fidelity(observed, case["expect"])
    if score >= FIDELITY_THRESHOLD:
        return True, f"fidelity={score:.4f}"
    top = sorted(observed.items(), key=lambda kv: -kv[1])[:4]
    return False, f"fidelity={score:.4f} < {FIDELITY_THRESHOLD}；实际主峰 {top}"


def require_environment() -> None:
    missing = [
        name for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")
        if not os.environ.get(name)
    ]
    if missing:
        print("缺少环境变量：" + ", ".join(missing))
        print("请先 export 这三个变量后重试（不要把 Key 写进任何文件）。")
        raise SystemExit(2)
    print(f"base_url={os.environ['LOOMQ_LLM_BASE_URL']}  model={os.environ['LOOMQ_LLM_MODEL']}"
          f"  api_key=<已设置，长度 {len(os.environ['LOOMQ_LLM_API_KEY'])}>")


def main() -> int:
    parser = argparse.ArgumentParser(description="LoomQ L2 私有变体自测")
    parser.add_argument("--only", choices=("generate", "repair", "backend"))
    parser.add_argument("--case", help="只跑指定 case id，例如 C05")
    parser.add_argument("--repeat", type=int, default=1, help="每个 case 重复次数")
    parser.add_argument("--json-out", default="tools/l2_selfcheck.json")
    parser.add_argument("--show", action="store_true", help="打印模型完整回复")
    args = parser.parse_args()

    require_environment()

    selected = [
        case for case in CASES
        if (not args.only or case["kind"] == args.only)
        and (not args.case or case["id"] == args.case.upper())
    ]
    if not selected:
        print("没有匹配的 case")
        return 2

    records = []
    passed = 0
    total = 0
    print(f"\n共 {len(selected)} 个 case × {args.repeat} 轮，单 case 时限 {CASE_TIME_LIMIT:.0f}s\n")

    for case in selected:
        for attempt in range(1, args.repeat + 1):
            total += 1
            label = f"{case['id']}" + (f".{attempt}" if args.repeat > 1 else "")
            started = time.time()
            try:
                answer = agent_chat(case["prompt"])
                ok, detail = judge(case, answer)
            except Exception as exc:
                answer, ok, detail = "", False, f"调用异常：{type(exc).__name__}: {exc}"
            elapsed = time.time() - started
            if elapsed > CASE_TIME_LIMIT:
                ok, detail = False, f"超时 {elapsed:.1f}s > {CASE_TIME_LIMIT:.0f}s（{detail}）"
            passed += ok
            print(f"[{'PASS' if ok else 'FAIL'}] {label} {elapsed:6.1f}s  {case['kind']:<8} "
                  f"{case['note']}\n        {detail}")
            if args.show or not ok:
                preview = answer if args.show else answer[:400]
                print("        --- 回复 ---")
                for line in (preview or "<空>").splitlines():
                    print("        " + line)
                print("        ------------")
            records.append(dict(case=case["id"], attempt=attempt, kind=case["kind"],
                                note=case["note"], ok=bool(ok), detail=detail,
                                seconds=round(elapsed, 2), answer=answer))

    rate = passed / total if total else 0.0
    print(f"\n通过 {passed}/{total} = {rate:.1%}   ->  客观分估算 {rate * 20:.1f} / 20")
    if rate * 20 < 12:
        print("注意：客观分低于 12，L2 交互体验那 10 分不计入。")

    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"passed": passed, "total": total, "pass_rate": rate,
         "objective_estimate": round(rate * 20, 2), "cases": records},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"明细已写入 {out}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
