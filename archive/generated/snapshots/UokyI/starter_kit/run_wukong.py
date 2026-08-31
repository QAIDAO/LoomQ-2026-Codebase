#!/usr/bin/env python3
"""本源悟空真机接入脚本（L1 真机证据采集）。

分两个阶段，避免排队/维护导致长时间阻塞：

    submit            提交任务，把 job_id 写入 evidence/files/wukong-job-id.txt
    query             读取 job_id，轮询结果，写 evidence/files/wukong-result.json

运行方式：
    $env:QUANTUM_API = [Environment]::GetEnvironmentVariable("QUANTUM_API", "Machine")
    python3 run_wukong.py submit
    python3 run_wukong.py query
"""

import json
import os
import sys
import time

from pyqpanda import (
    QCloud,
    QProg,
    H,
    CNOT,
    Measure,
    real_chip_type,
)

SHOTS = 8192
CHIP = 180  # 新一代「本源悟空」180 比特超导芯片（旧 72 比特芯片已停用）
HERE = os.path.dirname(os.path.abspath(__file__))
FILES = os.path.join(HERE, "evidence", "files")
JOB_ID_PATH = os.path.join(FILES, "wukong-job-id.txt")
RESULT_PATH = os.path.join(FILES, "wukong-result.json")


def load_token() -> str:
    token = os.environ.get("QUANTUM_API", "")
    if not token:
        raise RuntimeError("缺少 QUANTUM_API 环境变量（本源量子云 API Token）")
    return token


def new_machine():
    token = load_token()
    qm = QCloud()
    qm.set_configure(180, 180)
    qm.init_qvm(token, False)
    # pyqpanda 3.8.5 默认 API 域名已过时，覆盖为当前有效域名
    qm.compute_url = "https://console.originqc.com.cn/api/taskApi/submitTask.json"
    qm.inquire_url = "https://console.originqc.com.cn/api/taskApi/getTaskDetail.json"
    return qm


def build_bell(qm) -> QProg:
    q = qm.qAlloc_many(2)
    c = qm.cAlloc_many(2)
    prog = QProg()
    prog << H(q[0]) << CNOT(q[0], q[1]) << Measure(q[0], c[0]) << Measure(q[1], c[1])
    return prog


def probabilities_to_counts(prob: dict, shots: int) -> dict:
    raw = {k: round(v * shots) for k, v in prob.items()}
    total = sum(raw.values())
    if total != shots and raw:
        first = next(iter(raw))
        raw[first] += shots - total
    return raw


def cmd_submit() -> int:
    qm = new_machine()
    prog = build_bell(qm)
    task_id = qm.async_real_chip_measure(
        prog, SHOTS, CHIP, task_name="LoomQ Bell"
    )
    qm.finalize()
    os.makedirs(FILES, exist_ok=True)
    with open(JOB_ID_PATH, "w", encoding="utf-8") as handle:
        handle.write(task_id)
    print("提交成功，job_id:", task_id)
    return 0


def cmd_query() -> int:
    if not os.path.exists(JOB_ID_PATH):
        raise RuntimeError("未找到 job_id，请先执行 submit")
    with open(JOB_ID_PATH, encoding="utf-8") as handle:
        task_id = handle.read().strip()
    print("查询任务:", task_id)

    qm = new_machine()
    status = 0
    result = {}
    while True:
        time.sleep(3)
        status, result = qm.query_task_state_result(task_id)
        print("任务状态:", status)
        if status == QCloud.TaskStatus.FINISHED.value:
            break
        if status == QCloud.TaskStatus.FAILED.value:
            qm.finalize()
            print("任务失败")
            return 1
    qm.finalize()

    counts = probabilities_to_counts(result, SHOTS)
    payload = {
        "backend": "originq_wukong",
        "job_id": task_id,
        "shots": SHOTS,
        "counts": counts,
        "bit_order": "little",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "meta": {"chip": "origin_180", "raw_probabilities": result},
    }
    os.makedirs(FILES, exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print("真机结果已保存:", RESULT_PATH)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    command = sys.argv[1]
    if command == "submit":
        return cmd_submit()
    if command == "query":
        return cmd_query()
    print("未知命令:", command)
    return 1


if __name__ == "__main__":
    sys.exit(main())
