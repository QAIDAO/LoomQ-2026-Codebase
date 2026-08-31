#!/usr/bin/env python3
"""Compare LoomQ prompt versions with deterministic task grading."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple

try:
    from .llm_client import chat_completion
    from .loomq_agent.service import (
        _content,
        _extract_qasm,
        _legacy_system_prompt,
        _system_prompt,
        respond,
    )
    from .loomq_agent.validation import validate_generated_qasm
except ImportError:
    from llm_client import chat_completion
    from loomq_agent.service import (
        _content,
        _extract_qasm,
        _legacy_system_prompt,
        _system_prompt,
        respond,
    )
    from loomq_agent.validation import validate_generated_qasm


@dataclass(frozen=True)
class QualityCase:
    case_id: str
    category: str
    prompt: str
    accepted_backends: Tuple[str, ...] = ()
    expects_no_backend: bool = False


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    category: str
    passed: bool
    reason: str
    answer: str


BACKEND_IDS = (
    "spinq_taurus_simulator",
    "spinq_cloud_qpu",
    "originq_local_simulator",
    "originq_wukong",
    "braket_local_simulator",
    "braket_cloud",
)


CASES = (
    QualityCase("generate-ghz4-cn", "generation", "生成一个 4 比特 GHZ 态并对全部量子比特进行测量。"),
    QualityCase("generate-epr-en", "generation", "Create a 2-qubit EPR pair and measure both qubits."),
    QualityCase("generate-pair-cn", "generation", "生成一个三比特线路，使测量结果等概率为 001 和 110。"),
    QualityCase("generate-basis-cn", "generation", "制备计算基态 |101>，然后进行全测量。"),
    QualityCase(
        "repair-bell-case-comma",
        "repair",
        "我想制备贝尔态，请修复：H q[0]; CX q[0] q[1]。",
    ),
    QualityCase(
        "repair-ghz-semantics",
        "repair",
        "这段程序想生成 3 比特 GHZ 态，但结果不对，请修好："
        "OPENQASM 2.0; include \"qelib1.inc\"; qreg q[3]; creg c[3]; "
        "h q[0]; h q[1]; h q[2]; measure q -> c;",
    ),
    QualityCase(
        "repair-cat4-incomplete",
        "repair",
        "目标是四比特猫态并全测量。补全并修复：h q[0] cx q[0],q[1]; "
        "cx q[0],q[2]; cx q[0],q[3];",
    ),
    QualityCase(
        "repair-explicit-pair",
        "repair",
        "我需要等概率得到 010 和 111，但下面只有独立叠加，请重写正确完整线路："
        "h q[0]; h q[2];",
    ),
    QualityCase(
        "backend-15-no-queue",
        "backend",
        "我要运行 15 比特电路，必须零排队，推荐哪个后端？",
        ("spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"),
    ),
    QualityCase(
        "backend-qpu5-free",
        "backend",
        "5 比特线路必须使用真实量子硬件，而且不能付费，应该选什么？",
        ("spinq_cloud_qpu", "originq_wukong"),
    ),
    QualityCase(
        "backend-local28-no-account",
        "backend",
        "我要在本地运行 28 比特电路，不注册账号，选哪个后端？",
        ("originq_local_simulator",),
    ),
    QualityCase(
        "backend-40-no-queue",
        "backend",
        "40 比特电路要求零排队等待。是否有后端满足全部条件？",
        expects_no_backend=True,
    ),
)


def evaluate_versions(
    versions: Sequence[str], cases: Iterable[QualityCase] = CASES, mode: str = "raw"
) -> Dict[str, object]:
    selected_cases = tuple(cases)
    results: Dict[str, list[CaseResult]] = {}
    prompts = {"legacy": _legacy_system_prompt, "v2": _system_prompt}
    for version in versions:
        if version not in prompts:
            raise ValueError(f"unknown prompt version: {version}")
        if mode == "agent" and version != "v2":
            raise ValueError("agent mode supports only the production v2 prompt")
        version_results = []
        system_prompt = prompts[version]()
        for case in selected_cases:
            try:
                if mode == "agent":
                    answer = respond(case.prompt)
                else:
                    answer = _content(
                        chat_completion(
                            [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": case.prompt},
                            ],
                            request_timeout_seconds=120,
                        )
                    )
                passed, reason = grade_answer(case, answer)
            except Exception as error:
                answer = ""
                passed = False
                reason = f"{type(error).__name__}: {error}"
            version_results.append(
                CaseResult(case.case_id, case.category, passed, reason, answer)
            )
        result_name = version + ("-agent" if mode == "agent" else "")
        results[result_name] = version_results
    return build_report(results)


def grade_answer(case: QualityCase, answer: str) -> Tuple[bool, str]:
    if case.category in {"generation", "repair"}:
        qasm = _extract_qasm(answer)
        if qasm is None:
            return False, "response contains no complete OpenQASM 2.0 program"
        try:
            result = validate_generated_qasm(case.prompt, qasm)
        except Exception as error:
            return False, f"{type(error).__name__}: {error}"
        fidelity = "not-applicable" if result.fidelity is None else f"{result.fidelity:.4f}"
        return True, f"parse and semantic validation passed; fidelity={fidelity}"
    mentioned = tuple(backend for backend in BACKEND_IDS if backend in answer)
    if case.expects_no_backend:
        no_solution = bool(
            re.search(r"没有.{0,16}(?:满足|符合)|无.{0,8}(?:后端|解)|no backend", answer, re.I | re.S)
        )
        return (
            (True, "correctly reports that no backend satisfies every constraint")
            if no_solution
            else (False, f"no-solution statement missing; mentioned={mentioned}")
        )
    accepted = tuple(backend for backend in mentioned if backend in case.accepted_backends)
    if accepted:
        return True, "accepted backend id present: " + ", ".join(accepted)
    return False, f"accepted backend id missing; mentioned={mentioned}"


def build_report(results: Dict[str, list[CaseResult]]) -> Dict[str, object]:
    summaries = {}
    serialized = {}
    for version, version_results in results.items():
        passed = sum(item.passed for item in version_results)
        total = len(version_results)
        summaries[version] = {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": passed / total if total else 0.0,
        }
        serialized[version] = [asdict(item) for item in version_results]
    report: Dict[str, object] = {"summaries": summaries, "results": serialized}
    if "legacy" in summaries and "v2" in summaries:
        legacy_rate = summaries["legacy"]["pass_rate"]
        v2_rate = summaries["v2"]["pass_rate"]
        report["improvement"] = {
            "absolute_pass_rate": v2_rate - legacy_rate,
            "additional_passed_cases": summaries["v2"]["passed"] - summaries["legacy"]["passed"],
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare LoomQ prompt answer quality")
    parser.add_argument("--versions", default="legacy,v2")
    parser.add_argument("--case-limit", type=int, default=len(CASES))
    parser.add_argument("--mode", choices=("raw", "agent"), default="raw")
    parser.add_argument("--json-out")
    arguments = parser.parse_args()
    if arguments.case_limit <= 0 or arguments.case_limit > len(CASES):
        parser.error(f"--case-limit must be between 1 and {len(CASES)}")
    versions = tuple(item.strip() for item in arguments.versions.split(",") if item.strip())
    report = evaluate_versions(versions, CASES[: arguments.case_limit], mode=arguments.mode)
    if arguments.json_out:
        path = Path(arguments.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summaries"], ensure_ascii=False, indent=2))
    if "improvement" in report:
        print(json.dumps(report["improvement"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
