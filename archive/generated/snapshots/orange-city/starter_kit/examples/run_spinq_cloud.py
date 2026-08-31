#!/usr/bin/env python3
"""Submit Bell state to SpinQ Cloud QPU and save LoomQ evidence."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BELL_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
"""

# SpinQ Cloud rejects explicit measure; hardware measures all qubits at the end.
BELL_QASM_CLOUD = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];
"""


def main() -> int:
    username = os.environ.get("SPINQ_USERNAME", "").strip()
    keyfile = os.path.expanduser(os.environ.get("SPINQ_KEYFILE", "~/.ssh/id_rsa"))
    platform = os.environ.get("SPINQ_PLATFORM", "gemini_vp")
    shots = int(os.environ.get("SPINQ_SHOTS", "8192"))
    out_dir = Path(__file__).resolve().parents[1] / "evidence" / "files" / "spinq"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not username:
        print("请先设置量旋云用户名：")
        print('  export SPINQ_USERNAME="你的量旋云用户名"')
        return 1
    if not os.path.isfile(keyfile):
        print("找不到私钥: %s" % keyfile)
        return 1

    try:
        from spinqit import SpinQCloudConfig, get_compiler, get_spinq_cloud
    except ImportError:
        print("未安装 spinqit。请先执行：")
        print("  pip install spinqit==0.2.4")
        return 1

    print("登录量旋云: user=%s platform=%s shots=%d" % (username, platform, shots))
    backend = get_spinq_cloud(username, keyfile)
    plat = backend.get_platform(platform)
    print("机器数: %s  可用: %s" % (getattr(plat, "machine_count", "?"), plat.available()))
    if not plat.available():
        print("当前平台无空闲真机。可改试：")
        print('  export SPINQ_PLATFORM=triangulum_vp   # 3 比特')
        print('  export SPINQ_PLATFORM=superconductor_vp  # 8 比特超导')
        return 2

    with tempfile.NamedTemporaryFile("w", suffix=".qasm", delete=False, encoding="utf-8") as handle:
        handle.write(BELL_QASM_CLOUD)
        path = handle.name
    try:
        compiler = get_compiler("qasm")
        ir = compiler.compile(path, 0)
    finally:
        os.unlink(path)

    config = SpinQCloudConfig()
    config.configure_platform(platform)
    config.configure_shots(shots)
    config.configure_task("loomq-bell", "LoomQ 2026 L1 hardware evidence")

    print("提交真机任务中（可能排队数分钟）...")
    result = backend.execute(ir, config)

    counts = getattr(result, "counts", None) or {}
    probs = getattr(result, "probabilities", None) or {}
    if not counts and probs:
        counts = {str(k): int(round(float(v) * shots)) for k, v in probs.items()}
        diff = shots - sum(counts.values())
        if diff and counts:
            key = max(counts, key=counts.get)
            counts[key] += diff

    job_id = (
        getattr(result, "job_id", None)
        or getattr(result, "task_id", None)
        or getattr(result, "task_name", None)
        or getattr(result, "task_code", None)
        or "unknown"
    )
    # Prefer task code from cloud response attributes if nested
    for attr in dir(result):
        if attr.lower() in {"taskcode", "task_code", "code"} and not attr.startswith("_"):
            val = getattr(result, attr, None)
            if val and str(val) not in {"", "None"}:
                job_id = str(val)
                break
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "backend": "spinq_cloud_qpu",
        "platform": platform,
        "job_id": str(job_id),
        "shots": shots,
        "counts": {str(k): int(v) for k, v in dict(counts).items()},
        "probabilities": {str(k): float(v) for k, v in dict(probs).items()},
        "bit_order": "little",
        "timestamp": timestamp,
        "qasm": BELL_QASM,
        "meta": {
            "task": "loomq-bell",
            "username": username,
            "is_mock": False,
        },
    }

    result_path = out_dir / "result.json"
    qasm_path = out_dir / "bell.qasm"
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    qasm_path.write_text(BELL_QASM, encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("\n已写入:")
    print("  %s" % result_path)
    print("  %s" % qasm_path)
    print("\n下一步：打开 https://cloud.spinq.cn 找到该任务，截图保存为")
    print("  %s" % (out_dir / "console-job.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
