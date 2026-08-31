#!/usr/bin/env python3
"""SpinQ 量旋云真机跑批：QASM → 规范 QASM2 → spinqit IR → 云端真机 → 证据 JSON。

用法（在 tools/qpu 目录）：
  SPINQ_USERNAME=xxx SPINQ_KEYFILE=/path/to/key.pem \
    DYLD_LIBRARY_PATH=.venv/lib/python3.10/site-packages/spinqit \
    .venv/bin/python run_spinq_qpu.py --qasm ../../starter_kit/circuits/bell.qasm --shots 1000

凭证只从环境变量读取，绝不写入任何输出文件。
macOS 需要设置 DYLD_LIBRARY_PATH 指向 spinqit 包目录（wheel 的 rpath 缺陷 workaround）。
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from starter_kit.loomq import parse_qasm, transpile_to  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="SpinQ cloud QPU evidence runner")
    ap.add_argument("--qasm", default=None, help="输入 QASM 文件路径")
    ap.add_argument("--shots", type=int, default=1000)
    ap.add_argument("--platform", default="superconductor_vp",
                    help="平台代码；默认超导真机。传 --list 只列平台不提交")
    ap.add_argument("--list", action="store_true", help="仅列出可用平台")
    ap.add_argument("--task-name", default="LoomQ-evidence")
    args = ap.parse_args()
    if not args.qasm and not args.list:
        ap.error("--qasm 是必需的（除非使用 --list）")

    username = os.environ.get("SPINQ_USERNAME", "")
    keyfile = os.environ.get("SPINQ_KEYFILE", "")
    if not username or not keyfile or not Path(keyfile).is_file():
        print("请设置 SPINQ_USERNAME 与 SPINQ_KEYFILE（量旋云控制台下载的 RSA 私钥文件路径）",
              file=sys.stderr)
        return 2

    from spinqit import SpinQCloudConfig, get_spinq_cloud
    from spinqit.compiler.qasm_compiler import QASMCompiler

    backend = get_spinq_cloud(username, keyfile)
    print("可用平台：")
    for p in backend.platforms:
        print("  %-18s %-14s max_qubits=%s simu=%s online=%d" %
              (p.code, p.name, p.max_bitnum, p.simu, p.machine_count))
    if args.list:
        return 0

    qasm_text = Path(args.qasm).read_text(encoding="utf-8")
    circuit = parse_qasm(qasm_text)
    n_qubits = circuit.n_qubits
    normalized = transpile_to(circuit, "spinq")
    # SpinQ 云端不接受显式测量语句（自动全测量），提交版剥掉 measure 行
    cloud_src = "\n".join(
        line for line in normalized.splitlines() if not line.startswith("measure")
    ) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".qasm", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(cloud_src)
        tmp_path = handle.name
    try:
        ir = QASMCompiler().compile(tmp_path, 1)
    finally:
        os.unlink(tmp_path)
    if ir is None:
        print("spinqit QASM 编译失败", file=sys.stderr)
        return 1

    config = SpinQCloudConfig()
    config.configure_platform(args.platform)
    config.configure_shots(args.shots)
    config.configure_task(args.task_name, "LoomQ-2026 L1 real-machine evidence")
    submitted_at = datetime.now(timezone.utc).isoformat()
    print("提交中… shots=%d" % args.shots)
    result = backend.execute(ir, config)
    if result is None:
        print("任务失败（无结果返回，可能无在线机器，稍后重试）", file=sys.stderr)
        return 1

    counts = result.counts if result._counts is not None else None
    evidence = {
        "platform": "spinq_cloud_qpu",
        "platform_code": args.platform,
        "job_id": result.task_code,
        "submitted_at_utc": submitted_at,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "shots": args.shots,
        "qasm_source": str(Path(args.qasm).resolve().relative_to(REPO)),
        "qasm_contract_output": normalized,
        "qasm_cloud_submitted": cloud_src,
        "counts": counts,
        "probabilities": result.probabilities,
        "raw_task_code": result.task_code,
    }
    out_dir = REPO / "starter_kit" / "evidence" / "files" / "spinq"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.qasm).stem
    out_path = out_dir / ("%s_%s.json" % (stem, result.task_code))
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print("证据已保存：%s" % out_path)
    print("job_id(task_code)=%s" % result.task_code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
