#!/usr/bin/env python3
"""Submit Bell circuit to SpinQ Cloud (gemini_vp / triangulum_vp / superconductor_vp).

Required env:
  SPINQCLOUDUSERNAME   cloud.spinq.cn login name
  PRIVATEKEYPATH       path to SSH private key (default: ~/.ssh/id_rsa or id_ed25519)
Optional:
  SPINQ_PLATFORM       gemini_vp | triangulum_vp | superconductor_vp (default: gemini_vp)
  SPINQ_SHOTS          default 1024
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _default_key() -> str:
    home = Path.home() / ".ssh"
    for name in ("id_rsa", "id_ed25519"):
        p = home / name
        if p.is_file():
            return str(p)
    return str(home / "id_rsa")


def main() -> int:
    username = os.environ.get("SPINQCLOUDUSERNAME", "").strip()
    keyfile = os.environ.get("PRIVATEKEYPATH", _default_key()).strip()
    platform = os.environ.get("SPINQ_PLATFORM", "gemini_vp").strip()
    shots = int(os.environ.get("SPINQ_SHOTS", "1024"))

    if not username:
        print("缺少 SPINQCLOUDUSERNAME（cloud.spinq.cn 用户名）", file=sys.stderr)
        return 2
    if not Path(keyfile).is_file():
        print("私钥不存在: %s" % keyfile, file=sys.stderr)
        return 2

    from spinqit import SpinQCloudConfig, get_compiler, get_spinq_cloud

    qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
"""
    print("用户:", username)
    print("私钥:", keyfile)
    print("平台:", platform)
    print("shots:", shots)

    backend = get_spinq_cloud(username, keyfile)
    plat = backend.get_platform(platform)
    print("机器数:", getattr(plat, "machine_count", "?"))
    print("可用:", plat.available())
    if not plat.available():
        # try fallbacks
        for alt in ("gemini_vp", "triangulum_vp", "superconductor_vp"):
            if alt == platform:
                continue
            p2 = backend.get_platform(alt)
            print("尝试", alt, "可用=", p2.available(), "机器=", getattr(p2, "machine_count", "?"))
            if p2.available():
                platform = alt
                break
        else:
            print("当前无可用真机/虚拟机，请稍后再试或在网页查看排队。", file=sys.stderr)
            return 3

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")
    try:
        tmp.write(qasm)
        tmp.close()
        ir = get_compiler("qasm").compile(tmp.name, 0)
    finally:
        os.unlink(tmp.name)

    config = SpinQCloudConfig()
    config.configure_platform(platform)
    config.configure_shots(shots)
    config.configure_task("loomq-bell", "LoomQ competition Bell test")

    print("提交中…")
    result = backend.execute(ir, config)

    counts = getattr(result, "counts", None)
    probs = getattr(result, "probabilities", None) or {}
    if not counts and probs:
        counts = {k: int(round(float(v) * shots)) for k, v in probs.items()}
        # fix rounding to exact shots
        total = sum(counts.values())
        if total != shots and counts:
            # adjust largest bin
            kmax = max(counts, key=counts.get)
            counts[kmax] += shots - total
    counts = {str(k): int(v) for k, v in dict(counts or {}).items()}

    job_id = (
        getattr(result, "job_id", None)
        or getattr(result, "task_id", None)
        or getattr(result, "id", None)
        or "spinq-cloud-unknown"
    )

    payload = {
        "backend": "spinq_cloud_qpu",
        "job_id": str(job_id),
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta": {
            "platform": platform,
            "probabilities": {str(k): float(v) for k, v in dict(probs).items()},
            "raw_type": type(result).__name__,
        },
    }
    out = Path(__file__).resolve().parent / "evidence" / "files"
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / "spinq-result.json"
    qasm_path = out / "spinq-circuit.qasm"
    qasm_path.write_text(qasm, encoding="utf-8")
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("已写入:", result_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
