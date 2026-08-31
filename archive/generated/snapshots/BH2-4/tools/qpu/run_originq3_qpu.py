#!/usr/bin/env python3
"""本源量子云真机跑批（pyqpanda3 / QPanda3 动态后端发现版）。

Q&A 官方确认：真机权限分时段开放，且不限定 origin_72——任何在线真机后端
（WK_C180_2 等）均可用于证据。本脚本动态查询在线后端，优先选真机。

用法（在 tools/qpu 目录）：
  ORIGINQ_TOKEN=xxx .venv/bin/python run_originq3_qpu.py \
    --qasm ../../starter_kit/circuits/bell.qasm --shots 1000
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from starter_kit.loomq import parse_qasm, transpile_to  # noqa: E402

# 真机后端优先级（均为超导真机；*_amplitude 是模拟器，排除）
REAL_CHIP_PRIORITY = ["WK_C180_2", "WK_C180", "PQPUMESH8", "HanYuan_01"]


def pick_backend(backends: dict, preferred: str):
    if preferred:
        if preferred in backends and backends[preferred]:
            return preferred
        return None
    for name in REAL_CHIP_PRIORITY:
        if backends.get(name):
            return name
    online = [n for n, ok in backends.items() if ok]
    return None if not online else None  # 没有真机在线时不退化为模拟器


def main() -> int:
    ap = argparse.ArgumentParser(description="OriginQ QPU evidence runner (pyqpanda3)")
    ap.add_argument("--qasm", default=None)
    ap.add_argument("--shots", type=int, default=1000)
    ap.add_argument("--backend", default=None,
                    help="指定后端名；默认按优先级自动选在线真机")
    ap.add_argument("--list", action="store_true", help="仅列出后端在线状态")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()
    if not args.qasm and not args.list:
        ap.error("--qasm 是必需的（除非使用 --list）")

    token = os.environ.get("ORIGINQ_TOKEN", "")
    if not token:
        print("请设置 ORIGINQ_TOKEN", file=sys.stderr)
        return 2

    from pyqpanda3 import qcloud
    from pyqpanda3.intermediate_compiler import convert_qasm_string_to_qprog

    service = qcloud.QCloudService(api_key=token)
    backends = service.backends()
    if args.list:
        for name, online in backends.items():
            print("  %-18s %s" % (name, "在线" if online else "离线"))
        return 0

    chosen = pick_backend(backends, args.backend)
    if not chosen:
        print("当前无真机后端在线：%s" % backends, file=sys.stderr)
        return 1

    qasm_text = Path(args.qasm).read_text(encoding="utf-8")
    circuit = parse_qasm(qasm_text)
    qasm_submitted = transpile_to(circuit, "spinq")  # 规范 QASM2 直投
    prog = convert_qasm_string_to_qprog(qasm_submitted)

    backend = service.backend(chosen)
    submitted_at = datetime.now(timezone.utc).isoformat()
    print("后端 %s 提交中… shots=%d" % (chosen, args.shots))
    job = backend.run(prog, args.shots)
    result = job.result()
    counts = None
    probs = None
    try:
        counts = result.get_counts() or None
    except Exception:
        pass
    try:
        probs = result.get_probs()
    except Exception:
        pass
    if not counts and not probs:
        err = getattr(result, "error_message", "") or "无结果"
        print("任务失败：%s" % err, file=sys.stderr)
        return 1

    def _val(obj, name):
        value = getattr(obj, name, None)
        return value() if callable(value) else value

    job_id = _val(job, "job_id") or "unknown"
    if not counts and probs:
        counts = {k: round(p * args.shots) for k, p in probs.items()}
    evidence = {
        "platform": "originq_cloud_qpu",
        "backend": chosen,
        "job_id": job_id,
        "submitted_at_utc": submitted_at,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "shots": args.shots,
        "qasm_source": str(Path(args.qasm).resolve().relative_to(REPO)),
        "qasm_submitted": qasm_submitted,
        "counts": counts,
        "probabilities": probs,
        "counts_note": "counts 由平台概率换算（若有）",
    }
    out_dir = REPO / "starter_kit" / "evidence" / "files" / "originq"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.qasm).stem
    safe_job = str(job_id).replace("/", "_")[:40]
    out_path = out_dir / ("%s_%s_%s.json" % (stem, chosen, safe_job))
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2,
                                   default=str) + "\n", encoding="utf-8")
    print("证据已保存：%s" % out_path)
    print("job_id=%s" % job_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
