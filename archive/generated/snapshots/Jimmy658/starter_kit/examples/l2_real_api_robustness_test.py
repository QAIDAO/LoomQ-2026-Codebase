#!/usr/bin/env python3
"""Real DeepSeek robustness test for LoomQ L2.

This script runs a small, fixed set of real API cases through the public
``adapter.agent_chat`` entry point. It stores the API key only in this Python
process and writes a secret-free JSON report for later failure analysis.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import sys
import time
from collections import defaultdict
from typing import Any


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import adapter  # noqa: E402
import l2_agent  # noqa: E402


DEFAULTS = {
    "LOOMQ_LLM_BASE_URL": "https://api.deepseek.com",
    "LOOMQ_LLM_MODEL": "deepseek-v4-flash",
    "LOOMQ_LLM_TIMEOUT_SECONDS": "60",
}
REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "l2_real_api_robustness_report.json")
FAILURE_TYPES = (
    "intent_error",
    "qasm_syntax_error",
    "semantic_error",
    "backend_constraint_error",
    "malformed_llm_output",
    "api_error",
    "timeout",
    "unknown_error",
)


CASES: list[dict[str, Any]] = [
    {
        "id": "CASE 01",
        "category": "known_task",
        "kind": "ghz",
        "num_qubits": 5,
        "prompt": "Generate a 5-qubit GHZ state and measure all qubits.",
    },
    {
        "id": "CASE 02",
        "category": "known_task",
        "kind": "ghz",
        "num_qubits": 5,
        "prompt": "Create five entangled qubits whose measurement outcomes are always identical.",
    },
    {
        "id": "CASE 03",
        "category": "known_task",
        "kind": "ghz",
        "num_qubits": 5,
        "prompt": "Build a five-qubit Greenberger-Horne-Zeilinger circuit.",
    },
    {
        "id": "CASE 04",
        "category": "known_task",
        "kind": "ghz",
        "num_qubits": 5,
        "prompt": "生成一个五比特 GHZ 态，并测量所有量子位。",
    },
    {
        "id": "CASE 05",
        "category": "known_task",
        "kind": "ghz",
        "num_qubits": 5,
        "prompt": "给我一个五个量子位测量结果完全相关的纠缠电路。",
    },
    {
        "id": "CASE 06",
        "category": "known_task",
        "kind": "bell",
        "prompt": "Create a Bell pair and measure both qubits.",
    },
    {
        "id": "CASE 07",
        "category": "known_task",
        "kind": "bell",
        "prompt": "Prepare two maximally entangled qubits.",
    },
    {
        "id": "CASE 08",
        "category": "known_task",
        "kind": "bell",
        "prompt": "生成一个贝尔态并测量两个量子比特。",
    },
    {
        "id": "CASE 09",
        "category": "repair",
        "kind": "bell",
        "prompt": "I want a Bell state. Please fix this QASM:\nH q[0];\nCX q[0] q[1]",
    },
    {
        "id": "CASE 10",
        "category": "repair",
        "kind": "bell",
        "prompt": "Complete this Bell fragment with the missing header, qreg, creg, and measure:\nh q[0];\ncx q[0],q[1];",
    },
    {
        "id": "CASE 11",
        "category": "repair",
        "kind": "ghz",
        "num_qubits": 3,
        "prompt": "Fix this 3-qubit GHZ OpenQASM where the cx commas are missing:\nOPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[3];\ncreg c[3];\nh q[0];\ncx q[0] q[1];\ncx q[1] q[2];\nmeasure q -> c;",
    },
    {
        "id": "CASE 12",
        "category": "repair",
        "kind": "bell",
        "prompt": "Fix this Bell QASM that uses uppercase gate names:\nOPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\ncreg c[2];\nH q[0];\nCX q[0],q[1];\nMEASURE q -> c;",
    },
    {
        "id": "CASE 13",
        "category": "repair",
        "kind": "bell",
        "prompt": "I want a Bell state. This circuit runs but is semantically wrong, please fix it:\nOPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\ncreg c[2];\nx q[0];\nmeasure q -> c;",
    },
    {
        "id": "CASE 14",
        "category": "generic_generation",
        "kind": "generic",
        "prompt": "Create a 1-qubit circuit that applies H and measures the qubit.",
        "num_qubits": 1,
        "required_qasm_patterns": [r"\bh\s+q\[0\]\s*;"],
    },
    {
        "id": "CASE 15",
        "category": "generic_generation",
        "kind": "generic",
        "prompt": "Create a 2-qubit circuit: apply X to q0, then CX from q0 to q1, then measure both.",
        "num_qubits": 2,
        "required_qasm_patterns": [r"\bx\s+q\[0\]\s*;", r"\bcx\s+q\[0\]\s*,\s*q\[1\]\s*;"],
    },
    {
        "id": "CASE 16",
        "category": "generic_generation",
        "kind": "generic",
        "prompt": "Generate OpenQASM 2.0 for a single-qubit RY(pi/2) rotation and measurement.",
        "num_qubits": 1,
        "required_qasm_patterns": [r"\bry\s*\("],
    },
    {
        "id": "CASE 17",
        "category": "generic_generation",
        "kind": "generic",
        "prompt": "Create a circuit using RZ(pi/4) on q0 and then measure it.",
        "num_qubits": 1,
        "required_qasm_patterns": [r"\brz\s*\("],
    },
    {
        "id": "CASE 18",
        "category": "generic_generation",
        "kind": "generic",
        "prompt": "Generate a small circuit using SWAP between two qubits and measure both.",
        "num_qubits": 2,
        "required_qasm_patterns": [r"\bswap\s+q\[0\]\s*,\s*q\[1\]\s*;"],
    },
    {
        "id": "CASE 19",
        "category": "backend_selection",
        "kind": "backend",
        "prompt": "I need at least 15 qubits, zero queue, and a free backend. Which backend should I use?",
        "constraints": {"min_qubits": 15, "queue": "none", "free_only": True},
    },
    {
        "id": "CASE 20",
        "category": "backend_selection",
        "kind": "backend",
        "prompt": "Recommend a local simulator that does not require an account.",
        "constraints": {"local_only": True, "no_account": True},
    },
    {
        "id": "CASE 21",
        "category": "backend_selection",
        "kind": "backend",
        "prompt": "I need real quantum hardware. Which backend should I choose?",
        "constraints": {"real_hardware": True},
    },
    {
        "id": "CASE 22",
        "category": "backend_selection",
        "kind": "backend",
        "prompt": "15比特、零排队、免费，我应该选哪个后端？",
        "constraints": {"min_qubits": 15, "queue": "none", "free_only": True},
    },
    {
        "id": "CASE 23",
        "category": "backend_selection",
        "kind": "backend",
        "prompt": "我只想用本地模拟器，而且不想注册账号。",
        "constraints": {"local_only": True, "no_account": True},
    },
    {
        "id": "CASE 24",
        "category": "backend_selection",
        "kind": "backend",
        "prompt": "I need 50 qubits, free, zero queue. Is anything available?",
        "constraints": {"min_qubits": 50, "queue": "none", "free_only": True},
        "expect_no_backend": True,
    },
    {
        "id": "CASE 25",
        "category": "mixed",
        "kind": "bell",
        "prompt": "Generate a Bell circuit that can run on a local simulator.",
    },
]


def configure_process_environment() -> bool:
    for name, value in DEFAULTS.items():
        os.environ.setdefault(name, value)
    if not os.environ.get("LOOMQ_LLM_API_KEY"):
        key = getpass.getpass("DeepSeek API Key: ")
        if not key.strip():
            print("No API key entered; stopping.")
            return False
        os.environ["LOOMQ_LLM_API_KEY"] = key.strip()
    return True


def sanitize_text(text: str) -> str:
    key = os.environ.get("LOOMQ_LLM_API_KEY", "")
    if key:
        text = text.replace(key, "[REDACTED_API_KEY]")
    return re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED_API_KEY]", text)


def extract_qasm(response: str) -> tuple[str | None, str | None]:
    try:
        return l2_agent._extract_qasm(response), None
    except Exception as exc:
        return None, str(exc)


def qreg_size(qasm: str) -> int | None:
    match = re.search(r"\bqreg\s+q\[(\d+)\]\s*;", qasm, re.IGNORECASE)
    return int(match.group(1)) if match else None


def validate_known(case: dict[str, Any], response: str) -> tuple[bool, str, str]:
    qasm, error = extract_qasm(response)
    if qasm is None:
        if "Recommended backend ID(s)" in response:
            return False, "intent_error", "Expected QASM generation, got backend recommendation."
        return False, "malformed_llm_output", "Could not extract OpenQASM 2.0: " + (error or "unknown")

    syntax = l2_agent._validate_qasm_locally(qasm)
    if not syntax.ok:
        return False, "qasm_syntax_error", syntax.message

    if case["kind"] == "bell":
        semantic = l2_agent._validate_bell_semantics(qasm, {})
    else:
        expected_n = int(case["num_qubits"])
        actual_n = qreg_size(qasm)
        if actual_n != expected_n:
            return False, "intent_error", f"Expected qreg q[{expected_n}], got qreg q[{actual_n}]."
        semantic = l2_agent._validate_ghz_semantics(qasm, {"num_qubits": expected_n})
    if not semantic.ok:
        return False, "semantic_error", semantic.message
    return True, "", semantic.message


def validate_generic(case: dict[str, Any], response: str) -> tuple[bool, str, str]:
    qasm, error = extract_qasm(response)
    if qasm is None:
        return False, "malformed_llm_output", "Could not extract OpenQASM 2.0: " + (error or "unknown")
    validation = l2_agent._validate_qasm_locally(qasm)
    if not validation.ok:
        return False, "qasm_syntax_error", validation.message
    expected_n = case.get("num_qubits")
    if expected_n is not None and qreg_size(qasm) != int(expected_n):
        return False, "semantic_error", f"Expected qreg q[{expected_n}], got qreg q[{qreg_size(qasm)}]."
    for pattern in case.get("required_qasm_patterns", []):
        if not re.search(pattern, qasm, re.IGNORECASE):
            return False, "semantic_error", f"QASM missing expected pattern: {pattern}"
    return True, "", validation.message


def backend_ids_in_response(response: str) -> set[str]:
    known_ids = {backend["id"] for backend in l2_agent._load_backend_capabilities()}
    return {backend_id for backend_id in known_ids if backend_id in response}


def validate_backend(case: dict[str, Any], response: str) -> tuple[bool, str, str]:
    constraints = case.get("constraints", {})
    expected_ids = {backend["id"] for backend in l2_agent.select_backends(constraints)}
    actual_ids = backend_ids_in_response(response)
    if case.get("expect_no_backend"):
        no_match_text = re.search(r"no\s+backend|no\s+match|not\s+available|nothing\s+available|没有|无可用|不满足", response, re.IGNORECASE)
        if expected_ids:
            return False, "backend_constraint_error", f"Test expected no backend, but selector has {sorted(expected_ids)}."
        if actual_ids:
            return False, "backend_constraint_error", f"Expected no backend, but response included {sorted(actual_ids)}."
        if no_match_text:
            return True, "", "Correctly reported no backend."
        return False, "backend_constraint_error", "Expected no backend response, but no clear no-match wording was found."
    if not actual_ids:
        if "OPENQASM" in response:
            return False, "intent_error", "Expected backend recommendation, got QASM."
        if expected_ids:
            return False, "backend_constraint_error", f"No canonical backend ID found; expected one of {sorted(expected_ids)}."
        return False, "malformed_llm_output", "No canonical backend ID found in response."
    invalid = actual_ids - expected_ids
    if invalid:
        return False, "backend_constraint_error", f"Response included backend IDs outside expected constraints: {sorted(invalid)}."
    return True, "", "Backend IDs satisfy expected constraints: " + ", ".join(sorted(actual_ids))


def classify_exception(exc: Exception) -> str:
    text = str(exc).lower()
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "api" in text or "http" in text or "unreachable" in text:
        return "api_error"
    return "unknown_error"


def validate_case(case: dict[str, Any], response: str) -> tuple[bool, str, str]:
    if case["kind"] in {"bell", "ghz"}:
        return validate_known(case, response)
    if case["kind"] == "generic":
        return validate_generic(case, response)
    if case["kind"] == "backend":
        return validate_backend(case, response)
    return False, "unknown_error", "Unknown test kind: " + str(case.get("kind"))


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    print("=" * 50)
    print(case["id"])
    print("Category:", case["category"])
    print("Prompt:")
    print(case["prompt"])
    print()

    start = time.perf_counter()
    response = ""
    passed = False
    failure_type = ""
    failure_reason = ""
    try:
        response = adapter.agent_chat(case["prompt"])
        passed, failure_type, failure_reason = validate_case(case, response)
    except Exception as exc:
        failure_type = classify_exception(exc)
        failure_reason = f"{type(exc).__name__}: {exc}"
        response = ""
    elapsed = time.perf_counter() - start

    status = "PASS" if passed else "FAIL"
    print("Status:", status)
    print(f"Elapsed: {elapsed:.2f} s")
    print()
    print("Response:")
    print(sanitize_text(response))
    print()
    print("Failure reason:")
    print("" if passed else sanitize_text(failure_reason))
    print("=" * 50)

    return {
        "id": case["id"],
        "category": case["category"],
        "prompt": case["prompt"],
        "passed": passed,
        "elapsed_seconds": round(elapsed, 4),
        "failure_type": "" if passed else failure_type,
        "failure_reason": "" if passed else sanitize_text(failure_reason),
        "response": sanitize_text(response),
    }


def print_summary(results: list[dict[str, Any]]) -> None:
    total = len(results)
    passed = sum(1 for result in results if result["passed"])
    latencies = [result["elapsed_seconds"] for result in results]
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    failure_counts = {failure_type: 0 for failure_type in FAILURE_TYPES}
    for result in results:
        by_category[result["category"]].append(result)
        if not result["passed"]:
            failure_counts[result["failure_type"] or "unknown_error"] += 1

    print("================ SUMMARY ================")
    print(f"Total cases: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Pass rate: {(passed / total * 100):.1f}%")
    print()
    print("Category breakdown:")
    print()
    for category in ("known_task", "repair", "generic_generation", "backend_selection", "mixed"):
        items = by_category.get(category, [])
        if not items:
            continue
        category_passed = sum(1 for item in items if item["passed"])
        print(f"{category}:")
        print(f"  {category_passed}/{len(items)} PASS")
        print()
    print("Failure types:")
    print()
    for failure_type in FAILURE_TYPES:
        print(f"{failure_type}: {failure_counts[failure_type]}")
    print()
    if latencies:
        print(f"Average latency: {sum(latencies) / len(latencies):.2f} s")
        print(f"Max latency: {max(latencies):.2f} s")
    print()
    print("=========================================")


def write_report(results: list[dict[str, Any]]) -> None:
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump({"cases": results}, handle, ensure_ascii=False, indent=2)
    print("Report saved to:", REPORT_PATH)


def main() -> int:
    if not configure_process_environment():
        return 1
    results = [run_case(case) for case in CASES]
    print_summary(results)
    write_report(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
