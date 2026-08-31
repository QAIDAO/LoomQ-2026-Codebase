#!/usr/bin/env python3
"""Concurrent live stress test starting from raw end-user L2 prompts."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple


STARTER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STARTER))

from experiments.l2_live_benchmark import (  # noqa: E402
    BACKEND_CASES,
    QASM_CASES,
    run_backend,
    run_qasm,
)


Case = Tuple[str, str, str, str, Set[str]]


def qasm_cases() -> List[Case]:
    cases: List[Case] = []
    templates = (
        "生成一个 {n} 比特 GHZ 态，并对全部量子比特进行测量。",
        "Prepare a {n}-qubit GHZ state, then measure every qubit.",
        "零基础用户想制备 {n} 个量子比特 GHZ 态；请给出可执行、全测量的 OpenQASM 2.0。",
    )
    for qubits in range(3, 9):
        for variant, template in enumerate(templates, 1):
            cases.append((
                "generate:ghz%d-v%d" % (qubits, variant), "qasm", "generate",
                template.format(n=qubits), set(),
            ))
    bell_prompts = (
        "生成一个两比特 Bell 态并测量所有量子位。",
        "Create a Bell pair and measure all qubits.",
        "请用 OpenQASM 2.0 制备贝尔态，两个量子位都要测量。",
        "I need a complete measured Bell-state circuit, not an explanation.",
        "帮新手生成 2 比特 Bell state，最后全测量。",
        "Return executable OpenQASM 2.0 for a Bell pair with every qubit measured.",
    )
    cases.extend(
        ("generate:bell-v%d" % index, "qasm", "generate", prompt, set())
        for index, prompt in enumerate(bell_prompts, 1)
    )
    return cases


def repair_cases() -> List[Case]:
    cases: List[Case] = []
    for qubits in range(3, 9):
        prefix = "OPENQASM 2.0; qreg q[%d]; creg c[%d]; h q[0]; " % (qubits, qubits)
        incomplete = prefix + " ".join(
            "cx q[0],q[%d];" % index for index in range(1, qubits - 1)
        ) + " measure q -> c;"
        correct_gates = " ".join(
            "cx q[0],q[%d];" % index for index in range(1, qubits)
        )
        partial = prefix + correct_gates + " measure q[0] -> c[0];"
        duplicate = prefix + "cx q[0],q[0]; " + correct_gates + " measure q -> c;"
        prompts = (
            "修复这个 {n} 比特 GHZ 态电路并全测量，返回完整 QASM：{code}".format(
                n=qubits, code=incomplete
            ),
            "Repair this {n}-qubit GHZ circuit so every qubit is measured: {code}".format(
                n=qubits, code=partial
            ),
            "纠正以下 {n} 个量子比特 GHZ 电路的操作数错误，并保留全测量：{code}".format(
                n=qubits, code=duplicate
            ),
        )
        for variant, prompt in enumerate(prompts, 1):
            cases.append((
                "repair:ghz%d-v%d" % (qubits, variant), "qasm", "repair", prompt, set()
            ))
    bell_faults = (
        "OPENQASM 2.0; qreg q[2]; creg c[2]; h q[0] cx q[0],q[1]; measure q -> c;",
        "OPENQASM 2.0; qreg q[2]; creg c[2]; h q[0]; cx q[0],q[0]; measure q -> c;",
        "OPENQASM 2.0; qreg q[2]; creg c[2]; cx q[0],q[1]; measure q -> c;",
        "OPENQASM 2.0; qreg q[2]; creg c[2]; h q[0]; cx q[0],q[1]; measure q[0] -> c[0];",
        "OPENQASM 2.0; qreg q[2]; creg c[2]; x q[0]; cx q[0],q[1]; measure q -> c;",
        "OPENQASM 2.0; qreg q[2]; h q[0]; cx q[0],q[1]; measure q -> c;",
    )
    for index, code in enumerate(bell_faults, 1):
        cases.append((
            "repair:bell-v%d" % index,
            "qasm",
            "repair",
            "Fix this 2-qubit Bell-state program and measure every qubit; return complete QASM: " + code,
            set(),
        ))
    return cases


def backend_cases() -> List[Case]:
    rows: Sequence[Tuple[str, str, Set[str]]] = (
        ("local15", "运行 15 比特电路且无需排队，选择后端。", {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
        ("sim26", "Choose a simulator that supports at least 26 qubits.", {"originq_local_simulator"}),
        ("free25", "我要至少 25 比特、免费且无需账号的后端。", {"originq_local_simulator", "braket_local_simulator"}),
        ("free30", "Select a free backend for a 30-qubit circuit.", {"originq_local_simulator"}),
        ("cloud31", "A paid cloud backend for 31 qubits is acceptable.", {"braket_cloud"}),
        ("cloud34", "选择支持 34 比特的云端后端。", {"braket_cloud"}),
        ("qpu35", "I need real quantum hardware for at least 35 qubits.", {"originq_wukong"}),
        ("qpu70", "运行 70 比特任务，必须用真机。", {"originq_wukong"}),
        ("qpu8", "8 比特真机，免费额度可以接受。", {"spinq_cloud_qpu", "originq_wukong"}),
        ("qpu9", "Choose a QPU for a 9-qubit circuit.", {"originq_wukong"}),
        ("spinq-sim", "只用 SpinQ 平台的模拟器。", {"spinq_taurus_simulator"}),
        ("origin-noacct", "Use OriginQ without requiring an account.", {"originq_local_simulator"}),
        ("braket-nowait", "Braket platform with zero waiting time.", {"braket_local_simulator"}),
        ("braket-paid", "Use a paid Braket cloud backend that requires an account.", {"braket_cloud"}),
        ("noaws25", "25 比特模拟器，但不要 AWS 或 Braket。", {"originq_local_simulator"}),
        ("noacct24", "At least 24 qubits, and no account registration.", {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
        ("noacct26", "至少 26 比特且无需注册账号。", {"originq_local_simulator"}),
        ("paid30", "A paid backend supporting 30 qubits is fine.", {"braket_cloud"}),
        ("cloud30", "选择能跑 30 比特的 cloud backend。", {"braket_cloud"}),
        ("qpu72", "Need a 72-qubit hardware QPU.", {"originq_wukong"}),
        ("sim24-nowait", "24 比特模拟器，并且零排队。", {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
        ("free25-nowait", "Free, no-queue backend for 25 qubits.", {"originq_local_simulator", "braket_local_simulator"}),
        ("qpu-hours", "真机后端，排队数小时可以接受。", {"originq_wukong"}),
        ("spinq-qpu", "必须是 SpinQ 平台的 QPU 真机。", {"spinq_cloud_qpu"}),
    )
    return [
        ("backend:" + name, "backend", "backend", prompt, expected)
        for name, prompt, expected in rows
    ]


def adversarial_backend_cases() -> List[Case]:
    rows: Sequence[Tuple[str, str, Set[str]]] = (
        ("aws-no-account", "Use AWS without an account for 20 qubits.", {"braket_local_simulator"}),
        ("aws-no-registration", "Use AWS without requiring an account for 20 qubits.", {"braket_local_simulator"}),
        ("aws-without-registration", "Use AWS without registration for 20 qubits.", {"braket_local_simulator"}),
        ("aws-no-paid", "Use AWS but no paid services for 20 qubits.", {"braket_local_simulator"}),
        ("aws-with-no-paid", "AWS with no paid services for 25 qubits.", {"braket_local_simulator"}),
        ("dont-want-aws", "I don't want AWS; choose a 25-qubit simulator.", {"originq_local_simulator"}),
        ("except-aws", "Choose any 25-qubit simulator except AWS.", {"originq_local_simulator"}),
        ("anything-except-braket", "Anything except Braket: choose a 25-qubit simulator.", {"originq_local_simulator"}),
        ("avoid-aws", "Avoid AWS; select a 25-qubit simulator.", {"originq_local_simulator"}),
        ("exclude-braket", "Exclude Braket and run a 20-qubit circuit.", {"spinq_taurus_simulator"}),
        ("do-not-use-aws", "Do not use AWS for this 20-qubit circuit.", {"spinq_taurus_simulator"}),
        ("do-not-choose-aws", "Do not choose AWS; use a 25-qubit simulator.", {"originq_local_simulator"}),
        ("without-using-aws", "Run 20 qubits without using AWS.", {"spinq_taurus_simulator"}),
        ("without-use-of-braket", "Run 20 qubits without use of Braket.", {"spinq_taurus_simulator"}),
        ("but-not-aws", "Use any backend but not AWS for 20 qubits.", {"spinq_taurus_simulator"}),
        ("zh-no-aws", "运行 20 比特电路，但不要 AWS。", {"spinq_taurus_simulator"}),
        ("zh-no-braket", "运行 20 比特电路，不使用 Braket。", {"spinq_taurus_simulator"}),
        ("real-machine", "Use a real machine for 8 qubits.", {"spinq_cloud_qpu"}),
        ("physical-qc", "Use a physical quantum computer for 9 qubits.", {"originq_wukong"}),
        ("physical-hardware", "Use physical quantum hardware for 8 qubits.", {"spinq_cloud_qpu"}),
    )
    return [
        ("adversarial:" + name, "backend", "backend_adversarial", prompt, expected)
        for name, prompt, expected in rows
    ]


def fixed_cases() -> List[Case]:
    cases = [
        ("fixed:" + case_id, "qasm", "fixed", prompt, set())
        for case_id, prompt in QASM_CASES
    ]
    cases.extend(
        ("fixed:" + case_id, "backend", "fixed", prompt, expected)
        for case_id, prompt, expected in BACKEND_CASES
    )
    return cases


def execute(case: Case, round_index: int) -> Dict[str, Any]:
    case_id, task, category, prompt, expected = case
    if task == "backend":
        result = run_backend(case_id, prompt, expected)
    else:
        result = run_qasm(case_id, prompt)
    result["category"] = category
    result["round"] = round_index
    result["prompt"] = prompt
    if expected:
        result["expected"] = sorted(expected)
    return result


def percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def _category_summaries(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    categories = {}
    for category in sorted({item["category"] for item in results}):
        selected = [item for item in results if item["category"] == category]
        passed = sum(item["status"] == "PASS" for item in selected)
        categories[category] = {
            "passed": passed,
            "failed": len(selected) - passed,
            "total": len(selected),
            "pass_rate": round(passed / len(selected), 6),
        }
    return categories


def _round_summaries(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    summaries = {}
    for round_index in sorted({item["round"] for item in results}):
        selected = [item for item in results if item["round"] == round_index]
        passed = sum(item["status"] == "PASS" for item in selected)
        summaries[str(round_index)] = {
            "passed": passed,
            "failed": len(selected) - passed,
            "total": len(selected),
            "pass_rate": round(passed / len(selected), 6),
        }
    return summaries


def _telemetry_summary(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    metrics = [item.get("agent_metrics", {}) for item in results]
    totals = {
        key: sum(int(item.get(key, 0)) for item in metrics)
        for key in (
            "attempts", "successful_responses", "valid_responses",
            "repair_attempts", "http_retries", "canonical_recoveries",
            "input_tokens", "output_tokens", "prompt_usage_responses",
            "completion_usage_responses",
        )
    }
    return {
        "totals": totals,
        "per_case_budget": {
            "max_input_tokens_observed": max(
                (int(item.get("input_tokens", 0)) for item in metrics), default=0
            ),
            "max_output_tokens_observed": max(
                (int(item.get("output_tokens", 0)) for item in metrics), default=0
            ),
            "input_token_limit": 8000,
            "output_token_limit": 2000,
            "max_tokens_per_request": 1000,
            "attempt_limit": 3,
        },
    }


def _write_artifacts(
    json_out: Path, stdout_out: Path, results: Sequence[Dict[str, Any]],
    summary: Dict[str, Any], stdout_lines: Sequence[str],
) -> None:
    stdout_text = "\n".join(stdout_lines) + "\n"
    stdout_bytes = stdout_text.encode("utf-8")
    stdout_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    stdout_out.write_bytes(stdout_bytes)
    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "stdout": {
            "path": str(stdout_out),
            "bytes": len(stdout_bytes),
            "sha256": hashlib.sha256(stdout_bytes).hexdigest(),
        },
        "summary": summary,
        "results": list(results),
    }
    json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run fixed, 72-case stress, and adversarial LoomQ L2 live sets."
    )
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--stdout-out", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    if args.workers < 1:
        parser.error("--workers must be positive")
    if (args.json_out is None) != (args.stdout_out is None):
        parser.error("--json-out and --stdout-out must be supplied together")

    fixed = fixed_cases()
    stress = qasm_cases() + repair_cases() + backend_cases()
    adversarial = adversarial_backend_cases()
    cases = fixed + stress + adversarial
    wall_started = time.monotonic()
    results: List[Dict[str, Any]] = []
    stdout_lines: List[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(execute, case, round_index): (case[0], round_index)
            for round_index in range(1, args.rounds + 1)
            for case in cases
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            suffix = ": " + result["reason"] if "reason" in result else ""
            metrics = result.get("agent_metrics", {})
            line = (
                "[round %d/%d] [%s] %s (%.3fs) attempts=%d repair=%d "
                "retry=%d canonical=%d input=%d output=%d%s"
            ) % (
                result["round"], args.rounds, result["status"], result["case_id"],
                result["seconds"], metrics.get("attempts", 0),
                metrics.get("repair_attempts", 0), metrics.get("http_retries", 0),
                metrics.get("canonical_recoveries", 0), metrics.get("input_tokens", 0),
                metrics.get("output_tokens", 0), suffix,
            )
            stdout_lines.append(line)
            print(line, flush=True)
    wall_seconds = time.monotonic() - wall_started
    latencies = [item["seconds"] for item in results]
    passed = sum(item["status"] == "PASS" for item in results)
    summary = {
        "passed": passed,
        "failed": len(results) - passed,
        "total": len(results),
        "rounds": args.rounds,
        "case_sets_per_round": {
            "fixed": len(fixed), "stress": len(stress), "adversarial": len(adversarial),
        },
        "categories": _category_summaries(results),
        "round_results": _round_summaries(results),
        "telemetry": _telemetry_summary(results),
        "concurrency": args.workers,
        "wall_seconds": round(wall_seconds, 3),
        "throughput_cases_per_second": round(len(results) / wall_seconds, 3),
        "latency_seconds": {
            "median": round(statistics.median(latencies), 3),
            "p95": round(percentile(latencies, 0.95), 3),
            "maximum": round(max(latencies), 3),
        },
    }
    summary_line = json.dumps(summary, ensure_ascii=False)
    stdout_lines.append(summary_line)
    print(summary_line, flush=True)
    if args.json_out is not None and args.stdout_out is not None:
        _write_artifacts(args.json_out, args.stdout_out, results, summary, stdout_lines)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
