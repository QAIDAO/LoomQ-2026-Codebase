#!/usr/bin/env python3
"""End-to-end test for the LoomQ Web UI server API (loomq_web.py).

Usage:
    python3 test_web_api.py                 # spawns the server itself
    python3 test_web_api.py --port 8765     # against a running server

Checks: health, index HTML, run on all three targets, fidelity sanity,
error handling for malformed QASM, and the chat 503 path when LLM env
variables are absent.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

BELL = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""


def post(base: str, path: str, payload: dict):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read()), response.status
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read()), exc.code


def get(base: str, path: str):
    with urllib.request.urlopen(base + path, timeout=30) as response:
        return json.loads(response.read())


def fidelity_from_counts(counts, shots: int, ideal: dict[str, float]) -> float:
    """Hellinger fidelity between sampled counts and an ideal distribution."""
    keys = set(ideal) | set(counts)
    term = 0.0
    for key in keys:
        p = math.sqrt((counts.get(key, 0) / shots))
        q = math.sqrt(ideal.get(key, 0.0))
        term += (p - q) ** 2
    return 1.0 - math.sqrt(term) / math.sqrt(2.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--spawn", action="store_true",
                        help="start the server in a subprocess (default when no server is listening)")
    args = parser.parse_args()

    server_proc = None
    port = args.port
    base = "http://127.0.0.1:%d" % port

    # Detect an already-running server; otherwise spawn one.
    try:
        get(base, "/api/health")
    except Exception:  # noqa: BLE001
        here = os.path.dirname(os.path.abspath(__file__))
        server_proc = subprocess.Popen(
            [sys.executable, os.path.join(here, "loomq_web.py"), "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                get(base, "/api/health")
                break
            except Exception:  # noqa: BLE001
                if server_proc.poll() is not None:
                    print("server exited early with code", server_proc.returncode)
                    return 1
                time.sleep(0.3)
        else:
            print("server did not become healthy in time")
            return 1

    passed = 0
    failed = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print("[PASS] %s %s" % (name, detail))
        else:
            failed += 1
            print("[FAIL] %s %s" % (name, detail))

    # 1. health
    health = get(base, "/api/health")
    check("health", health["ok"] and "spinq" in health["targets"])

    # 2. index HTML
    with urllib.request.urlopen(base + "/", timeout=30) as response:
        html = response.read().decode("utf-8")
    check("index", response.status == 200 and "LoomQ" in html and len(html) > 10_000)

    # 3. run on all three targets with fidelity check vs ideal Bell 00/11
    for target in ("spinq", "originq", "braket"):
        data, status = post(base, "/api/run", {"qasm": BELL, "target": target, "shots": 8192})
        check("run:%s" % target, status == 200 and data["ok"], data.get("error", ""))
        counts = data["result"]["counts"]
        fid = fidelity_from_counts(counts, 8192, {"00": 0.5, "11": 0.5})
        check("fidelity:%s>=0.97" % target, fid >= 0.97, "fid=%.4f" % fid)
        check("transpilations:%s" % target, target in data["transpilations"])
        check("explanation:%s" % target, "纠缠" in data["explanation"])

    # 4. circuit diagram endpoint
    data, status = post(base, "/api/circuit", {"qasm": BELL})
    check("circuit:bell", status == 200 and data["ok"] and data["num_qubits"] == 2
          and "standard_text" in data, "qubits=%s" % data.get("num_qubits"))
    data, status = post(base, "/api/circuit", {"qasm": "OPENQASM 2.0;\nzzz q[0];"})
    check("circuit:bad-qasm-422", status == 422 and not data["ok"])

    # 5. preset circuit files served with no traversal
    for name in ("bell.qasm", "ghz3.qasm", "ghz5.qasm", "qft4.qasm", "grover3.qasm"):
        with urllib.request.urlopen(base + "/circuits/" + name, timeout=30) as response:
            text = response.read().decode("utf-8")
        check("circuit-file:%s" % name, response.status == 200 and "OPENQASM" in text)
    import urllib.error as _ue

    try:
        urllib.request.urlopen(base + "/circuits/../.git/config", timeout=10)
        check("circuit:traversal-blocked", False)
    except _ue.HTTPError as exc:
        check("circuit:traversal-blocked", exc.code == 403)

    # 6. malformed QASM -> 422 with friendly error
    data, status = post(base, "/api/run",
                        {"qasm": "OPENQASM 2.0;\nqreg q[1];\nzzzz q[0];", "target": "spinq", "shots": 16})
    check("error:unknown-gate", status == 422 and not data["ok"] and data["error"], data.get("error", ""))

    # 5. empty qasm -> 400
    data, status = post(base, "/api/run", {"qasm": "", "target": "spinq", "shots": 16})
    check("error:empty-qasm", status == 400 and not data["ok"])

    # 6. shots out of range
    data, status = post(base, "/api/run", {"qasm": BELL, "target": "spinq", "shots": 10 ** 9})
    check("error:bad-shots", status == 400 and not data["ok"])

    # 7. chat without LLM config -> 503 actionable
    data, status = post(base, "/api/chat", {"prompt": "你好"})
    check("chat:no-llm-503", status == 503 and "LOOMQ_LLM" in data.get("error", ""), data.get("error", ""))

    # 8. backends table
    backends = get(base, "/api/backends")
    check("backends", backends["ok"] and len(backends["backends"]["backends"]) >= 6)

    print("\nWEB API TEST: %d passed, %d failed" % (passed, failed))
    if server_proc is not None:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_proc.kill()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
