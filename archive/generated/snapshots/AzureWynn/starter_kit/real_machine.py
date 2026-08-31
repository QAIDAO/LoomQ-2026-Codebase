#!/usr/bin/env python3
"""Submit a circuit to a real quantum computer and save traceable evidence.

Providers (both free-quota):
  spinq    -> SpinQ Cloud (gemini_vp 2q / triangulum_vp 3q / superconductor_vp 8q)
              env: LOOMQ_SPINQ_USERNAME + LOOMQ_SPINQ_KEYFILE (RSA key, outside repo)
  originq  -> 本源量子云 悟空芯 72 比特 (real_chip_wukong_72)
              env: LOOMQ_ORIGINQ_TOKEN (API Token from http://qcloud.originqc.com.cn)

Usage:
  set -a; source .env; set +a
  python3 starter_kit/real_machine.py --provider spinq    --circuit bell
  python3 starter_kit/real_machine.py --provider originq  --circuit bell
  python3 starter_kit/real_machine.py --list-platforms    # spinq only

Outputs (evidence, to be committed):
  starter_kit/evidence/files/{spinq-cloud|originq-wukong}-<circuit>.qasm
  starter_kit/evidence/files/{spinq-cloud|originq-wukong}-<circuit>-result.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

_REQUIRED_ENV = {"spinq": ("LOOMQ_SPINQ_USERNAME", "LOOMQ_SPINQ_KEYFILE"),
                 "originq": ("LOOMQ_ORIGINQ_TOKEN",)}

_DEFAULT_PLATFORM = {"bell": "gemini_vp", "ghz3": "triangulum_vp"}


def _config(provider: str) -> dict:
    required = _REQUIRED_ENV[provider]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "missing required environment variable(s) for provider %r: %s"
            % (provider, ", ".join(missing))
            + " (see .env.example; private keys must live outside the repo)"
        )
    if provider == "spinq":
        return {
            "username": os.environ["LOOMQ_SPINQ_USERNAME"],
            "keyfile": os.environ["LOOMQ_SPINQ_KEYFILE"],
            "host": os.environ.get("LOOMQ_SPINQ_HOST", "http://cloud.spinq.cn:6060"),
            "platform": os.environ.get("LOOMQ_SPINQ_PLATFORM"),
            "shots": int(os.environ.get("LOOMQ_SPINQ_SHOTS", "1024")),
        }
    return {
        "token": os.environ["LOOMQ_ORIGINQ_TOKEN"],
        "shots": int(os.environ.get("LOOMQ_ORIGINQ_SHOTS", "1024")),
        "chip_id": int(os.environ.get("LOOMQ_ORIGINQ_CHIP", "72")),
    }


def _build_circuit(name: str):
    # SpinQ Cloud measures all qubits automatically at the end of the circuit;
    # explicit MEASURE gates are rejected by the platform.
    from spinqit import Circuit, H, CX

    circ = Circuit(name=name)
    if name == "bell":
        circ.allocateQubits(2)
        circ.append(H, [0])
        circ.append(CX, [0, 1])
    elif name == "ghz3":
        circ.allocateQubits(3)
        circ.append(H, [0])
        circ.append(CX, [0, 1])
        circ.append(CX, [1, 2])
    else:
        raise ValueError("unsupported circuit: %s (use bell or ghz3)" % name)
    return circ


def _qasm_for_evidence(name: str) -> str:
    if name == "bell":
        return (
            "OPENQASM 2.0;\ninclude \"qelib1.inc\";\n"
            "qreg q[2];\ncreg c[2];\nh q[0];\ncx q[0], q[1];\n"
            "measure q -> c;\n"
        )
    return (
        "OPENQASM 2.0;\ninclude \"qelib1.inc\";\n"
        "qreg q[3];\ncreg c[3];\nh q[0];\ncx q[0], q[1];\ncx q[1], q[2];\n"
        "measure q -> c;\n"
    )


def list_platforms(cfg):
    from spinqit.backend.spinq_cloud_backend import SpinQCloudBackend

    backend = SpinQCloudBackend(cfg["username"], cfg["keyfile"], cfg["host"])
    print("platforms: (code | name | max_bitnum | machine_count | simulator)")
    for p in backend._platforms:
        print("  %-24s %-40s %d   %d   %s"
              % (p.code, p.name, p.max_bitnum, p.machine_count, p.simu))


def submit(cfg, name: str):
    from spinqit.compiler import get_compiler
    from spinqit.backend.spinq_cloud_backend import SpinQCloudConfig, SpinQCloudBackend

    circ = _build_circuit(name)
    ir = get_compiler().compile(circ, level=0)
    backend = SpinQCloudBackend(cfg["username"], cfg["keyfile"], cfg["host"])
    config = SpinQCloudConfig()
    platform = cfg["platform"] or _DEFAULT_PLATFORM.get(name, "triangulum_vp")
    config.configure_platform(platform)
    config.configure_shots(cfg["shots"])
    config.configure_measured_qubits(list(range(circ.qubits_num)))
    config.configure_task("LoomQ-%s" % name, "LoomQ evidence submission")
    config.configure_process_now(True)

    print("submitting %s to %s (platform=%s, shots=%d) ..."
          % (name, cfg["host"], platform, cfg["shots"]))
    result = backend.execute(ir, config)

    counts = dict(result.counts)
    task_code = result.task_code
    payload = {
        "backend": "spinq_cloud_qpu",
        "platform": platform,
        "circuit": name,
        "job_id": task_code,
        "shots": getattr(result, "_shots", cfg["shots"]),
        "counts": counts,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "raw result from SpinQ Cloud; task_code traceable on platform console",
    }
    return _write_evidence("spinq-cloud", name, payload, counts)
    return 0


def submit_originq(cfg: dict, name: str) -> int:
    """Submit to 本源量子云 悟空芯 72-bit via pyqpanda QCloud (async + poll)."""
    from pyqpanda import QProg, H, CNOT, QCloud

    def build_prog(qcloud):
        qbits = qcloud.qAlloc_many(3 if name == "ghz3" else 2)
        prog = QProg()
        if name == "bell":
            prog << H(qbits[0]) << CNOT(qbits[0], qbits[1])
        elif name == "ghz3":
            prog << H(qbits[0]) << CNOT(qbits[0], qbits[1]) << CNOT(qbits[1], qbits[2])
        else:
            raise ValueError("unsupported circuit: %s" % name)
        return prog

    qcloud = QCloud()
    qcloud.init_qvm(cfg["token"])
    task_id = qcloud.async_real_chip_measure(
        build_prog(qcloud), cfg["shots"], chip_id=cfg["chip_id"],
        task_name="LoomQ-%s" % name,
    )
    print("task submitted to originq chip %d, task_id=%s (polling) ..."
          % (cfg["chip_id"], task_id))
    deadline = time.time() + 1800
    while time.time() < deadline:
        time.sleep(5)
        status, result = qcloud.query_task_state_result(task_id)
        if status == QCloud.TaskStatus.FINISHED.value:
            break
        if status == QCloud.TaskStatus.FAILED.value:
            raise RuntimeError("originq task %s failed" % task_id)
    else:
        raise RuntimeError("timed out waiting for originq task %s" % task_id)

    counts = {key: int(round(prob * cfg["shots"])) for key, prob in result.items()}
    payload = {
        "backend": "originq_wukong",
        "chip_id": cfg["chip_id"],
        "circuit": name,
        "job_id": task_id,
        "shots": cfg["shots"],
        "counts": counts,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "raw result from 本源量子云; task_id traceable on qcloud.originqc.com.cn console",
    }
    return _write_evidence("originq-wukong", name, payload, counts)


def _write_evidence(prefix: str, name: str, payload: dict, counts: dict) -> int:
    ev_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence", "files")
    os.makedirs(ev_dir, exist_ok=True)
    qasm_path = os.path.join(ev_dir, "%s-%s.qasm" % (prefix, name))
    json_path = os.path.join(ev_dir, "%s-%s-result.json" % (prefix, name))
    with open(qasm_path, "w", encoding="utf-8") as fh:
        fh.write(_qasm_for_evidence(name))
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    dominant = max(counts.items(), key=lambda kv: kv[1]) if counts else ("-", 0)
    expected = {"00", "11"} if name == "bell" else {"000", "111"}
    hit = dominant[0] in expected
    print("job_id: %s" % payload["job_id"])
    print("counts: %s" % counts)
    print("dominant state: %s (%d shots) -> %s"
          % (dominant[0], dominant[1], "PEAK MATCHES IDEAL" if hit else "peak does not match ideal"))
    print("evidence written to:")
    print("  %s" % qasm_path)
    print("  %s" % json_path)
    print("\nNext: fill the L1 real-machine block in starter_kit/evidence/README.md")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("spinq", "originq"), default="spinq")
    parser.add_argument("--circuit", choices=("bell", "ghz3"), default="bell")
    parser.add_argument("--list-platforms", action="store_true")
    args = parser.parse_args()
    cfg = _config(args.provider)
    if args.list_platforms:
        if args.provider != "spinq":
            print("--list-platforms is only supported for the spinq provider")
            return 1
        list_platforms(cfg)
        return 0
    if args.provider == "originq":
        return submit_originq(cfg, args.circuit)
    return submit(cfg, args.circuit)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("FAILED: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(1)