#!/usr/bin/env python3
"""SpinQ Cloud 真机接入脚本（L1 真机证据采集）

官方文档（doc.spinq.cn）确认的云后端用法：
    backend = get_spinq_cloud(username, keyfile)   # SSH 密钥认证
    platform = backend.get_platform("superconductor_vp")   # 超导真机 8 比特
    result = backend.execute(ir, config)           # SpinQCloudResult

使用前提：
1. 在 https://cloud.spinq.cn 注册并添加本地 SSH 公钥；
2. python 3.10 环境 + `pip install spinqit`（最高只提供 cp310 wheel）。

用法：
    python examples/run_spinq_cloud.py --username <cloud-user> \
        --keyfile ~/.ssh/id_rsa_spinq --platform superconductor_vp \
        --circuit circuits/bell.qasm --shots 4096 --out evidence/files/spinq-bell-result.json

成功后把任务页截图一并放入 evidence/files/，并在 evidence/README.md 的
L1 真机小节登记 job/任务 ID。
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

try:
    from spinqit import get_spinq_cloud, get_compiler, SpinQCloudConfig
except ImportError:  # pragma: no cover - guarded at runtime
    get_spinq_cloud = get_compiler = SpinQCloudConfig = None

PLATFORMS = {"gemini_vp": 2, "triangulum_vp": 3, "superconductor_vp": 8}


def load_circuit_qasm(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def compile_qasm_to_ir(qasm: str):
    """OpenQASM 2.0 -> SpinQit IR (via temporary file, per SDK contract).

    SpinQ Cloud auto-measures at the end of the circuit and rejects explicit
    measure instructions, so measurement statements are stripped first.
    """
    try:
        from qasm_parser import parse_qasm2
        from codegen import to_spinq_qasm
    except ImportError:  # standalone fallback
        from starter_kit.qasm_parser import parse_qasm2
        from starter_kit.codegen import to_spinq_qasm
    circuit = parse_qasm2(qasm)
    circuit.measures = []  # cloud measures automatically at the end
    qasm_clean = to_spinq_qasm(circuit)
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")
    try:
        handle.write(qasm_clean)
        handle.close()
        compiler = get_compiler("qasm")
        return compiler.compile(handle.name, 0)
    finally:
        os.unlink(handle.name)


def main() -> int:
    parser = argparse.ArgumentParser(description="SpinQ Cloud real-device runner")
    parser.add_argument("--username", required=True, help="SpinQ Cloud 登录用户名")
    parser.add_argument("--keyfile", required=True, help="本地 SSH 私钥路径 (id_rsa)")
    parser.add_argument("--platform", default="superconductor_vp", choices=sorted(PLATFORMS))
    parser.add_argument("--circuit", required=True, help="OpenQASM 2.0 电路文件路径")
    parser.add_argument("--shots", type=int, default=4096)
    parser.add_argument("--task-name", default="loomq-bell")
    parser.add_argument("--task-desc", default="LoomQ submission real-device evidence")
    parser.add_argument("--out", help="原始结果 JSON 输出路径 (evidence/files/...)")
    args = parser.parse_args()

    if get_spinq_cloud is None:
        print("spinqit 未安装。请在 python 3.10 环境: pip install spinqit", file=sys.stderr)
        return 2

    keyfile = os.path.expanduser(args.keyfile)
    if not os.path.isfile(keyfile):
        print("SSH 私钥不存在: %s" % keyfile, file=sys.stderr)
        return 2

    qasm = load_circuit_qasm(args.circuit)
    print("电路: %s (%d 字符 QASM)" % (args.circuit, len(qasm)))
    ir = compile_qasm_to_ir(qasm)
    print("编译为 SpinQit IR 完成，量子比特数: %s" % getattr(ir, "qnum", "?"))

    print("连接 SpinQ Cloud (%s, 平台 %s) ..." % (args.username, args.platform))
    try:
        backend = get_spinq_cloud(args.username, keyfile)
    except Exception as exc:
        print("认证失败：%s" % exc, file=sys.stderr)
        print("排查建议：", file=sys.stderr)
        print("  1. 确认 --username 与 cloud.spinq.cn 登录用户名一致；", file=sys.stderr)
        print("  2. 确认 --keyfile 指向本机私钥（id_rsa_spinq）；", file=sys.stderr)
        print("  3. 确认该私钥的公钥已添加到 cloud.spinq.cn 的 SSH 密钥管理；", file=sys.stderr)
        print("  完整步骤见 starter_kit/SPINQ_CLOUD_SETUP.md", file=sys.stderr)
        return 1
    platform = backend.get_platform(args.platform)
    print("平台 %s 可用机器数: %s" % (args.platform, getattr(platform, "machine_count", "?")))
    if not platform.available():
        print("平台 %s 当前无可用机器，请稍后重试或换平台。" % args.platform, file=sys.stderr)
        return 1

    config = SpinQCloudConfig()
    config.configure_platform(args.platform)
    config.configure_shots(args.shots)
    config.configure_task(args.task_name, args.task_desc)

    print("提交任务 (shots=%d) ..." % args.shots)
    # Explicit submit -> poll flow so the platform task code becomes the
    # traceable job_id (SpinQCloudResult itself does not carry it).
    status, msg, task_code = backend.submit_task(ir, config)
    if status in (200, 202):
        print("Task %s has been submitted successfully. Please wait for processing." % task_code)
        result = backend.get_task_result(task_code)
    elif status == 226:
        print("Task %s submitted but no machine online now; retry later." % task_code, file=sys.stderr)
        return 1
    elif status == 206:
        print("Task %s submitted but no machine fits the topology; retry later." % task_code, file=sys.stderr)
        return 1
    else:
        raise RuntimeError("Task submission failed: status=%s msg=%s" % (status, msg))
    print("任务完成。")

    probabilities = getattr(result, "probabilities", None) or {}
    counts = getattr(result, "counts", None) or {}
    payload = {
        "backend": "spinq_cloud_%s" % args.platform,
        "platform": args.platform,
        "job_id": task_code,
        "shots": args.shots,
        "counts": {str(k): int(v) for k, v in counts.items()},
        "probabilities": {str(k): float(v) for k, v in probabilities.items()},
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "circuit_file": args.circuit,
        "meta": {"task_name": args.task_name, "task_desc": args.task_desc},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print("原始结果已保存: %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
