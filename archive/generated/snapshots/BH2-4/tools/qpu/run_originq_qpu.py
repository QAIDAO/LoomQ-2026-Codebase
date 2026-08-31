#!/usr/bin/env python3
"""本源量子云真机跑批：QASM → OriginIR → 悟空真机 → 证据 JSON。

用法（在 tools/qpu 目录）：
  ORIGINQ_TOKEN=xxx .venv/bin/python run_originq_qpu.py \
    --qasm ../../starter_kit/circuits/bell.qasm --shots 1000

凭证只从环境变量读取，绝不写入任何输出文件。
返回的概率结果按平台原始值保存，counts 为 round(p*shots) 供人读。
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from starter_kit.loomq import parse_qasm, transpile_to  # noqa: E402

STATUS_FINISHED = 3
STATUS_FAILED = 4


def main() -> int:
    ap = argparse.ArgumentParser(description="OriginQ cloud QPU evidence runner")
    ap.add_argument("--qasm", required=True, help="输入 QASM 文件路径")
    ap.add_argument("--shots", type=int, default=1000)
    ap.add_argument("--chip", default="origin_72",
                    choices=["origin_72", "origin_wuyuan_d3", "origin_wuyuan_d4",
                             "origin_wuyuan_d5"],
                    help="真机芯片，默认悟空 origin_72")
    ap.add_argument("--task-name", default="LoomQ-evidence")
    ap.add_argument("--timeout", type=int, default=900, help="轮询超时（秒）")
    args = ap.parse_args()

    token = os.environ.get("ORIGINQ_TOKEN", "")
    if not token:
        print("请设置 ORIGINQ_TOKEN（本源量子云控制台的 API Key）", file=sys.stderr)
        return 2

    import pyqpanda as pq

    qasm_text = Path(args.qasm).read_text(encoding="utf-8")
    circuit = parse_qasm(qasm_text)
    originir = transpile_to(circuit, "originq")

    machine = pq.QCloud()
    machine.init_qvm(token)
    chip_id = getattr(pq.real_chip_type, args.chip)
    submitted_at = datetime.now(timezone.utc).isoformat()
    task_id = machine.async_real_chip_measure(
        prog=originir, shot=args.shots, chip_id=chip_id,
        is_amend=True, is_mapping=True, is_optimization=True,
        task_name=args.task_name)
    print("已提交，task_id=%s，轮询结果…" % task_id)

    deadline = time.time() + args.timeout
    status, result = None, None
    while time.time() < deadline:
        status, result = machine.query_task_state_result(task_id)
        if status == STATUS_FINISHED:
            break
        if status == STATUS_FAILED:
            print("平台返回任务失败", file=sys.stderr)
            return 1
        time.sleep(5)
    if status != STATUS_FINISHED:
        print("轮询超时（task_id=%s），可稍后手动查询" % task_id, file=sys.stderr)
        return 1

    probabilities = {k: float(v) for k, v in result.items()}
    counts = {k: round(p * args.shots) for k, p in probabilities.items()}
    evidence = {
        "platform": "originq_wukong",
        "chip": args.chip,
        "job_id": task_id,
        "submitted_at_utc": submitted_at,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "shots": args.shots,
        "qasm_source": str(Path(args.qasm).resolve().relative_to(REPO)),
        "originir_submitted": originir,
        "probabilities": probabilities,
        "counts_derived": counts,
        "note": "counts_derived 由平台概率四舍五入而来，求和可能与 shots 有个位数差异",
    }
    out_dir = REPO / "starter_kit" / "evidence" / "files" / "originq"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.qasm).stem
    out_path = out_dir / ("%s_%s.json" % (stem, str(task_id)[:40]))
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print("证据已保存：%s" % out_path)
    print("job_id(task_id)=%s" % task_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
