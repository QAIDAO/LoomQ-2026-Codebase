#!/usr/bin/env python3
"""LoomQ real-machine backends (L1 真机证据).

This module is the *optional* real-hardware layer of the LoomQ middle tier. The
core ``adapter.py`` stays dependency-free so the automated evaluator can run it
in an isolated container with no network and no third-party SDKs. This module
activates only when the vendor SDKs are importable, and submits circuits to the
real quantum machines (or their cloud simulators) to collect traceable evidence:

  * SpinQ Cloud  (spinqit)  -> real NMR/superconducting machines or simulator
  * Origin Cloud (pyqpanda) -> 悟空 real chip (origin_72) or full-amplitude sim

Each successful submission writes a raw result file under
``evidence/files/`` (job_id / task code + timestamp + counts) and returns the
unified result schema used everywhere in the project.

Usage (from the starter_kit directory, with the vendor SDKs installed):

    python real_backends.py --backend spinq --platform triangulum_vp
    python real_backends.py --backend originq
    python real_backends.py --backend spinq --platform simulator --all-circuits
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Make the sibling adapter importable (same package, runnable as a script).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapter import parse_qasm, Circuit  # noqa: E402

CIRCUITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "circuits")
EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence", "files")

# Platform identifiers per backend_capabilities.json
SPINQ_PLATFORMS = {
    "gemini_vp": "spinq_cloud_qpu",        # 2-bit NMR real machine
    "triangulum_vp": "spinq_cloud_qpu",    # 3-bit NMR real machine
    "superconductor_vp": "spinq_cloud_qpu",  # 8-bit superconducting real machine
    "hercules_vp": "spinq_cloud_qpu",      # 5-bit real machine
    "simulator": "spinq_taurus_simulator",  # 24-bit cloud simulator
}

# Circuit filenames shipped in circuits/ (public self-test set).
CIRCUIT_FILES = ("bell.qasm", "ghz3.qasm")


def _load_env() -> Dict[str, str]:
    """Load .env if present (simple parser; keeps secrets out of source)."""
    env = {}
    dotenv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    if os.path.exists(dotenv):
        with open(dotenv, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip("\"'")
    return env


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _save_evidence(name: str, payload: Dict[str, Any]) -> str:
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    path = os.path.join(EVIDENCE_DIR, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


# ---------------------------------------------------------------------------
# SpinQ cloud
# ---------------------------------------------------------------------------

def spinq_cloud_run(qasm_str: str, platform: str = "triangulum_vp",
                    shots: int = 8192) -> Dict[str, Any]:
    """Run a circuit on the SpinQ Cloud (real machine or cloud simulator).

    Returns the unified result schema. Raises if spinqit is not installed or
    the cloud rejects the task.
    """
    try:
        import spinqit  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("spinqit is not installed; cannot reach SpinQ Cloud") from exc

    env = _load_env()
    username = os.environ.get("LOOMQ_SPINQ_USERNAME") or env.get("LOOMQ_SPINQ_USERNAME")
    keyfile = os.environ.get("LOOMQ_SPINQ_KEYFILE") or env.get("LOOMQ_SPINQ_KEYFILE")
    if not username or not keyfile or not os.path.exists(keyfile):
        raise RuntimeError("SpinQ Cloud credentials missing (LOOMQ_SPINQ_USERNAME / KEYFILE)")

    from spinqit import get_spinq_cloud, get_compiler, SpinQCloudConfig

    backend = get_spinq_cloud(username, keyfile)

    circ = parse_qasm(qasm_str)
    if circ.num_qubits > 8:
        raise RuntimeError("SpinQ cloud QPU supports at most 8 qubits")

    # SpinQ Cloud measures automatically at the end of the circuit, so the
    # explicit measure statements must be stripped before submission.
    quantum_lines = []
    for line in qasm_str.splitlines():
        line = line.split("//", 1)[0].strip()
        if not line:
            continue
        if line.lower().startswith("measure"):
            continue
        quantum_lines.append(line)
    submit_qasm = "\n".join(quantum_lines) + "\n"

    # Compile QASM to SpinQ IR (cloud disallows explicit measure; measurement
    # is automatic at the end of the circuit).
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")
    try:
        tmp.write(submit_qasm)
        tmp.close()
        compiler = get_compiler("qasm")
        ir = compiler.compile(tmp.name, 0)
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)

    config = SpinQCloudConfig()
    config.configure_platform(platform)
    config.configure_shots(shots)
    config.configure_task("LoomQ", "LoomQ real machine evidence")
    config.configure_measure_qubits(list(range(circ.num_qubits)))

    result = backend.execute(ir, config)

    # Normalize counts: spinq cloud returns keys of len == num_qubits.
    raw_counts = dict(result.counts or {})
    normalized = {}
    for key, value in raw_counts.items():
        if not isinstance(key, str):
            key = format(int(key), "0%db" % circ.num_qubits)
        normalized[key] = int(value)

    schema = {
        "backend": SPINQ_PLATFORMS.get(platform, "spinq_cloud_qpu"),
        "job_id": getattr(result, "task_code", None) or "spinq-cloud-task",
        "shots": shots,
        "counts": normalized,
        "bit_order": "little",
        "timestamp": _utc_now(),
        "meta": {
            "platform": platform,
            "qubits_count": circ.num_qubits,
            "transpiled_gates": len(circ.gates),
            "raw_result_file": None,
        },
    }
    # Save raw evidence: full platform payload + unified schema.
    evidence = {
        "provider": "spinq",
        "platform": platform,
        "job_id": schema["job_id"],
        "timestamp": schema["timestamp"],
        "shots": shots,
        "circuit_qasm": qasm_str,
        "counts": normalized,
        "probabilities": dict(result.probabilities or {}),
        "unified_schema": schema,
    }
    fname = "spinq-%s-%s.json" % (platform, schema["job_id"])
    saved = _save_evidence(fname, evidence)
    schema["meta"]["raw_result_file"] = saved
    return schema


# ---------------------------------------------------------------------------
# Origin cloud (pyqpanda)
# ---------------------------------------------------------------------------

ORIGIN_BACKEND_IDS = {
    "real_chip": "originq_wukong",
    "full_amplitude": "originq_local_simulator",
    "noise": "originq_local_simulator",
}


def originq_cloud_run(qasm_str: str, shots: int = 8192,
                      mode: str = "real_chip", chip: Optional[str] = None) -> Dict[str, Any]:
    """Run a circuit on the Origin Quantum Cloud (悟空 real chip or simulator).

    mode: "real_chip" (real QPU) or "full_amplitude" (cloud simulator).
    chip: 真机标识，如 "origin_72"（悟空 72）/ "WK_C180_2"（悟空 180）等。
          缺省时读取环境变量 LOOMQ_ORIGINQ_CHIP；再缺省则用 origin_72。
          主办方确认真机不限于悟空 72，可选用当前在线的其他物理后端。
    """
    try:
        import pyqpanda as pq
        from pyqpanda.OriginService.QCloudMachine import QCloud
    except ImportError as exc:
        raise RuntimeError("pyqpanda is not installed; cannot reach Origin Cloud") from exc

    env = _load_env()
    token = os.environ.get("LOOMQ_ORIGINQ_TOKEN") or env.get("LOOMQ_ORIGINQ_TOKEN")
    if not token:
        raise RuntimeError("Origin Cloud token missing (LOOMQ_ORIGINQ_TOKEN)")

    machine = QCloud()
    machine.init_qvm(token, enable_logging=False, log_to_console=False)

    circ = parse_qasm(qasm_str)
    prog, qreg, creg = pq.convert_qasm_string_to_qprog(qasm_str, machine)

    if mode == "real_chip":
        # 真机 chip 可配置：参数 > 环境变量 > 默认 origin_72
        chip_name = chip or os.environ.get("LOOMQ_ORIGINQ_CHIP") or env.get("LOOMQ_ORIGINQ_CHIP")
        chip_id = getattr(pq.real_chip_type, chip_name, None) if chip_name else None
        if chip_id is None:
            chip_id = pq.real_chip_type.origin_72
        result = machine.real_chip_measure(
            prog, shot=shots, chip_id=chip_id
        )
        chip_used = getattr(chip_id, "name", chip_name or "origin_72")
    else:
        result = machine.full_amplitude_measure(prog, shot=shots)
        chip_used = "full_amplitude"

    # result is {binary_state: count} or {binary_state: probability}
    # normalize counts when mode==real_chip returns counts-like dict.
    total = sum(result.values()) if result else 0
    is_counts = abs(total - shots) < max(1, shots * 0.05) or total >= shots
    if is_counts:
        normalized = {k: int(v) for k, v in result.items()}
    else:
        normalized = {k: int(round(v * shots)) for k, v in result.items()}

    backend_id = ORIGIN_BACKEND_IDS.get(mode, "originq_wukong")
    schema = {
        "backend": backend_id,
        "job_id": "originq-%s-%s" % (mode, format(hash(qasm_str) & 0xFFFFFFFF, "08x")),
        "shots": shots,
        "counts": normalized,
        "bit_order": "little",
        "timestamp": _utc_now(),
        "meta": {
            "mode": mode,
            "chip": chip_used,
            "qubits_count": circ.num_qubits,
            "transpiled_gates": len(circ.gates),
        },
    }
    evidence = {
        "provider": "originq",
        "mode": mode,
        "job_id": schema["job_id"],
        "timestamp": schema["timestamp"],
        "shots": shots,
        "circuit_qasm": qasm_str,
        "raw_result": result,
        "unified_schema": schema,
    }
    fname = "originq-%s-%s.json" % (mode, schema["job_id"])
    saved = _save_evidence(fname, evidence)
    schema["meta"]["raw_result_file"] = saved
    return schema


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_circuit(name: str) -> str:
    path = os.path.join(CIRCUITS_DIR, name)
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="LoomQ real-machine evidence collector")
    parser.add_argument("--backend", choices=("spinq", "originq", "both"), default="both")
    parser.add_argument("--platform", default="triangulum_vp",
                        help="SpinQ platform code (gemini_vp / triangulum_vp / "
                             "superconductor_vp / hercules_vp / simulator)")
    parser.add_argument("--circuit", default=None, help="circuit file name (default: all public)")
    parser.add_argument("--shots", type=int, default=8192)
    parser.add_argument("--mode", choices=("real_chip", "full_amplitude"), default="real_chip")
    args = parser.parse_args()

    circuits = [args.circuit] if args.circuit else list(CIRCUIT_FILES)
    results = []
    exit_code = 0
    for name in circuits:
        qasm = _load_circuit(name)
        if args.backend in ("spinq", "both"):
            try:
                r = spinq_cloud_run(qasm, platform=args.platform, shots=args.shots)
                results.append(r)
                print("[OK] spinq %s -> %s (%s)" % (name, r["backend"], r["job_id"]))
                print("     counts top:", sorted(r["counts"].items(), key=lambda kv: -kv[1])[:3])
            except Exception as exc:
                print("[FAIL] spinq %s: %s" % (name, exc))
                exit_code = 1
        if args.backend in ("originq", "both"):
            try:
                r = originq_cloud_run(qasm, shots=args.shots, mode=args.mode)
                results.append(r)
                print("[OK] originq %s -> %s (%s)" % (name, r["backend"], r["job_id"]))
                print("     counts top:", sorted(r["counts"].items(), key=lambda kv: -kv[1])[:3])
            except Exception as exc:
                print("[FAIL] originq %s: %s" % (name, exc))
                exit_code = 1
    print("Evidence written to:", EVIDENCE_DIR)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())