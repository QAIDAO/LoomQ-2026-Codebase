#!/usr/bin/env python3
"""Small deterministic live-model benchmark for the three L2 objective tasks."""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set


STARTER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STARTER))

from loomq_l2 import (  # noqa: E402
    agent_chat as measured_agent_chat,
    _semantic_diagnostic,
    _target_spec,
    _validated_candidate,
)


QASM_CASES = [
    ("generate:ghz3-zh", "生成一个 3 比特 GHZ 态并进行全测量"),
    ("generate:bell-en", "Create a Bell state and measure all qubits."),
    ("generate:ghz4-en", "Prepare a 4-qubit GHZ state and measure every qubit."),
    ("generate:ghz5-zh", "请制备 5 个量子比特 GHZ 态，并测量全部量子位。"),
    (
        "repair:bell-syntax",
        "修复下面的 2 比特 Bell 态电路并全测量，返回完整 QASM：\n"
        "OPENQASM 2.0; qreg q[2]; creg c[2]; h q[0] cx q[0],q[1]; measure q -> c;",
    ),
    (
        "repair:ghz3-gate",
        "Repair this 3-qubit GHZ circuit and measure all qubits; return complete QASM: "
        "OPENQASM 2.0; qreg q[3]; creg c[3]; h q[0]; cx q[0],q[1]; measure q -> c;",
    ),
    (
        "repair:ghz4-measure",
        "修复这个 4 比特 GHZ 态电路，要求全测量：OPENQASM 2.0; qreg q[4]; creg c[4]; "
        "h q[0]; cx q[0],q[1]; cx q[0],q[2]; cx q[0],q[3]; measure q[0] -> c[0];",
    ),
    (
        "repair:bell-operand",
        "Fix the 2-qubit Bell state below and measure every qubit: "
        "OPENQASM 2.0; qreg q[2]; creg c[2]; h q[0]; cx q[0],q[0]; measure q -> c;",
    ),
]


BACKEND_CASES = [
    (
        "backend:local15",
        "我需要运行一个 15 比特电路，而且无需排队，请选择后端。",
        {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"},
    ),
    (
        "backend:local30",
        "Choose a simulator for 30 qubits with no queue.",
        {"originq_local_simulator"},
    ),
    (
        "backend:qpu70",
        "我要运行 70 比特电路，必须使用真机。",
        {"originq_wukong"},
    ),
    (
        "backend:braket-paid",
        "Use the Braket platform; a paid cloud backend that requires an account is acceptable.",
        {"braket_cloud"},
    ),
]


def run_qasm(case_id: str, prompt: str) -> Dict[str, Any]:
    started = time.monotonic()
    metrics: Dict[str, Any] = {}
    try:
        reply = measured_agent_chat(prompt, metrics=metrics)
        candidate = _validated_candidate(reply)
        target = _target_spec(prompt)
        if target is None:
            raise AssertionError("benchmark target could not be recovered")
        diagnostic = _semantic_diagnostic(candidate, target)
        if diagnostic:
            raise AssertionError(diagnostic)
        return {
            "case_id": case_id, "status": "PASS",
            "seconds": time.monotonic() - started, "agent_metrics": metrics,
        }
    except Exception as exc:
        return {
            "case_id": case_id,
            "status": "FAIL",
            "seconds": time.monotonic() - started,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "agent_metrics": metrics,
        }


def run_backend(case_id: str, prompt: str, expected: Set[str]) -> Dict[str, Any]:
    started = time.monotonic()
    metrics: Dict[str, Any] = {}
    try:
        reply = measured_agent_chat(prompt, metrics=metrics).strip()
        if reply not in expected:
            raise AssertionError("unexpected backend id: %s" % reply)
        return {
            "case_id": case_id, "status": "PASS",
            "seconds": time.monotonic() - started, "agent_metrics": metrics,
        }
    except Exception as exc:
        return {
            "case_id": case_id,
            "status": "FAIL",
            "seconds": time.monotonic() - started,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "agent_metrics": metrics,
        }


def main() -> int:
    results: List[Dict[str, Any]] = []
    for case_id, prompt in QASM_CASES:
        result = run_qasm(case_id, prompt)
        results.append(result)
        suffix = ": " + result["reason"] if "reason" in result else ""
        print("[%s] %s (%.3fs)%s" % (
            result["status"], result["case_id"], result["seconds"], suffix
        ))
    for case_id, prompt, expected in BACKEND_CASES:
        result = run_backend(case_id, prompt, expected)
        results.append(result)
        suffix = ": " + result["reason"] if "reason" in result else ""
        print("[%s] %s (%.3fs)%s" % (
            result["status"], result["case_id"], result["seconds"], suffix
        ))
    passed = sum(item["status"] == "PASS" for item in results)
    latencies = [item["seconds"] for item in results]
    summary = {
        "passed": passed,
        "failed": len(results) - passed,
        "total": len(results),
        "latency_seconds": {
            "median": round(statistics.median(latencies), 3),
            "maximum": round(max(latencies), 3),
        },
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
