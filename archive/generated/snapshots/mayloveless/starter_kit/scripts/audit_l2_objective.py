#!/usr/bin/env python3
"""运行 12-case L2 客观分 hidden-like scoring 审计。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


# 支持从 starter_kit 直接执行 ``python scripts/audit_l2_objective.py``。
STARTER_KIT_ROOT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT_ROOT))

import adapter
import llm_client
from loomq.backend_selector import BackendConstraints, load_backends, select_backends
from loomq.ir import MeasureOperation
from loomq.parser import parse_qasm
from loomq.qasm_tools import extract_qasm
from loomq.semantic_verifier import (
    parse_target_specification,
    verify_semantics,
)


CASE_SET_VERSION = "l2-hidden-like-2026-08-20-v1"
FORMAL_MODEL = "deepseek-v4-flash"
_REQUIRED_MODEL_CONFIGURATION = (
    "LOOMQ_LLM_BASE_URL",
    "LOOMQ_LLM_API_KEY",
    "LOOMQ_LLM_MODEL",
)


@dataclass(frozen=True)
class AuditCase:
    """一个固定 prompt 与测试侧独立期望。"""

    case_id: str
    task_type: str
    prompt: str
    expected_target_payload: Mapping[str, Any] | None = None
    measurement_policy: str = "not_applicable"
    expected_backend_constraints: BackendConstraints | None = None


def _statevector_target(
    qubit_count: int,
    amplitudes: Sequence[tuple[str, float, float]],
) -> dict[str, Any]:
    return {
        "verification_mode": "statevector",
        "pure_state_requested": True,
        "qubit_count": qubit_count,
        "amplitudes": [
            {"basis": basis, "real": real, "imag": imag}
            for basis, real, imag in amplitudes
        ],
        "explanation": "audit-owned expected pure state",
    }


_SQRT_HALF = 1.0 / math.sqrt(2.0)
_BELL_PLUS = _statevector_target(
    2,
    (("00", _SQRT_HALF, 0.0), ("11", _SQRT_HALF, 0.0)),
)
_BELL_MINUS = _statevector_target(
    2,
    (("00", _SQRT_HALF, 0.0), ("11", -_SQRT_HALF, 0.0)),
)
_GHZ_PLUS = _statevector_target(
    3,
    (("000", _SQRT_HALF, 0.0), ("111", _SQRT_HALF, 0.0)),
)


AUDIT_CASES = (
    AuditCase(
        case_id="generate_epr_correlated_measurement",
        task_type="generate_qasm",
        prompt=(
            "请搭一个二量子位纠缠对：两者读出时只能同为 0 或同为 1，"
            "概率各半（EPR 的正号态），最后逐位测量两个量子位。"
        ),
        expected_target_payload=_BELL_PLUS,
        measurement_policy="required",
    ),
    AuditCase(
        case_id="generate_bell_minus_phase_offset",
        task_type="generate_qasm",
        prompt=(
            "Create a two-qubit pure state whose |00⟩ and |11⟩ components have "
            "equal magnitude but a phase offset of pi; do not add measurement."
        ),
        expected_target_payload=_BELL_MINUS,
        measurement_policy="forbidden",
    ),
    AuditCase(
        case_id="generate_ghz_three_readout",
        task_type="generate_qasm",
        prompt=(
            "把三个量子位制备成全零与全一等权叠加、相位相同的纠缠态，"
            "并把三个量子位全部读出。"
        ),
        expected_target_payload=_GHZ_PLUS,
        measurement_policy="required",
    ),
    AuditCase(
        case_id="generate_explicit_basis_ket",
        task_type="generate_qasm",
        prompt=(
            "State-preparation request: initialize exactly the two-qubit ket |01⟩; "
            "leave the circuit unmeasured."
        ),
        expected_target_payload=_statevector_target(2, (("01", 1.0, 0.0),)),
        measurement_policy="forbidden",
    ),
    AuditCase(
        case_id="repair_syntax_preserve_epr",
        task_type="repair_qasm",
        prompt=(
            "修好下面的 OpenQASM；原意是制备正号 EPR 对并测量两位，不能改变原意：\n"
            "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\ncreg c[2];\n"
            "h q[0]\ncx q[0],q[1];\nmeasure q -> c;"
        ),
        expected_target_payload=_BELL_PLUS,
        measurement_policy="required",
    ),
    AuditCase(
        case_id="repair_semantic_wrong_cx_direction",
        task_type="repair_qasm",
        prompt=(
            "这段程序语法没错但没有实现目标。目标是 (|00⟩+|11⟩)/sqrt(2)，"
            "且不要测量；请纠正并保持目标：\nOPENQASM 2.0;\n"
            "include \"qelib1.inc\";\nqreg q[2];\nh q[0];\ncx q[1],q[0];"
        ),
        expected_target_payload=_BELL_PLUS,
        measurement_policy="forbidden",
    ),
    AuditCase(
        case_id="repair_relative_phase_sign",
        task_type="repair_qasm",
        prompt=(
            "原需求是制备 (|00⟩-|11⟩)/sqrt(2) 且不做测量，但现有程序的"
            "相对相位符号错了。请保持原始意图修复：\nOPENQASM 2.0;\n"
            "include \"qelib1.inc\";\nqreg q[2];\nh q[0];\ncx q[0],q[1];"
        ),
        expected_target_payload=_BELL_MINUS,
        measurement_policy="forbidden",
    ),
    AuditCase(
        case_id="repair_missing_required_measurement",
        task_type="repair_qasm",
        prompt=(
            "原本要准备 |10⟩ 并测量两个量子位；输入漏掉了读出，请修复且"
            "不要改变制备态：\nOPENQASM 2.0;\ninclude \"qelib1.inc\";\n"
            "qreg q[2];\nx q[0];"
        ),
        expected_target_payload=_statevector_target(2, (("10", 1.0, 0.0),)),
        measurement_policy="required",
    ),
    AuditCase(
        case_id="backend_negative_constraints",
        task_type="select_backend",
        prompt="帮我找后端：不用真机、不付费、不要账号，而且零排队。",
        expected_backend_constraints=BackendConstraints(
            min_qubits=None,
            require_qpu=False,
            require_no_queue=True,
            cost_policy="free_only",
            allow_account_required=False,
        ),
    ),
    AuditCase(
        case_id="backend_qpu_free_quota",
        task_type="select_backend",
        prompt="必须上真实量子硬件，费用只能是免费或带免费额度；账号可以注册。",
        expected_backend_constraints=BackendConstraints(
            min_qubits=None,
            require_qpu=True,
            require_no_queue=False,
            cost_policy="free_or_quota",
            allow_account_required=True,
        ),
    ),
    AuditCase(
        case_id="backend_25q_no_account_no_queue",
        task_type="select_backend",
        prompt=(
            "至少容纳 25 个量子位；别让我注册账号，也不能排队等待。"
            "不要求是真机，本地方案完全可以。"
        ),
        expected_backend_constraints=BackendConstraints(
            min_qubits=25,
            require_qpu=False,
            require_no_queue=True,
            cost_policy="unspecified",
            allow_account_required=False,
        ),
    ),
    AuditCase(
        case_id="backend_qpu_no_queue_no_match",
        task_type="select_backend",
        prompt="我只接受真实 QPU，并且必须零排队；其他条件不限。",
        expected_backend_constraints=BackendConstraints(
            min_qubits=None,
            require_qpu=True,
            require_no_queue=True,
            cost_policy="unspecified",
            allow_account_required=None,
        ),
    ),
)


def _repository_state() -> dict[str, Any]:
    root = STARTER_KIT_ROOT.parent
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(root),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=True,
            ).stdout.strip()
        )
        return {"source_commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"source_commit": "unavailable", "dirty": None}


def _base_entry(
    case: AuditCase,
    repository: Mapping[str, Any],
    model: str,
) -> dict[str, Any]:
    return {
        "case_set_version": CASE_SET_VERSION,
        "case_id": case.case_id,
        "task_type": case.task_type,
        "source_commit": repository["source_commit"],
        "source_dirty": repository["dirty"],
        "model": model,
        "status": "FAIL",
        "llm_calls": 0,
        "elapsed_seconds": 0.0,
        "parser_valid": None,
        "semantic_mode": None,
        "semantic_valid": None,
        "fidelity": None,
        "measurement_valid": None,
        "backend_ids": None,
        "no_match": None,
        "repair_triggered": None,
        "error_category": None,
    }


def _error_category(error: Exception) -> str:
    """只返回安全高层分类，不保留原异常或 HTTP 内容。"""
    message = str(error)
    if "deadline exhausted" in message:
        return "deadline_exhausted"
    if "model request failed" in message:
        return "model_request_failed"
    if "cannot downgrade" in message:
        return "pure_state_downgrade"
    if "JSON" in message or "model response" in message:
        return "invalid_structured_output"
    if "verification" in message or "OpenQASM" in message:
        return "candidate_verification_failed"
    return "agent_failure"


def _measurement_valid(case: AuditCase, circuit: Any) -> bool:
    measured = any(
        isinstance(operation, MeasureOperation) for operation in circuit.operations
    )
    if case.measurement_policy == "required":
        return measured
    if case.measurement_policy == "forbidden":
        return not measured
    return True


def _run_real_case(
    case: AuditCase,
    repository: Mapping[str, Any],
    model: str,
) -> dict[str, Any]:
    entry = _base_entry(case, repository, model)
    call_count = 0
    reply: str | None = None
    original_chat_completion = llm_client.chat_completion

    def counted_chat_completion(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return original_chat_completion(*args, **kwargs)

    started = time.monotonic()
    llm_client.chat_completion = counted_chat_completion
    try:
        # 严格经过官方入口；模型 transport 只计数，不替换、不 mock。
        reply = adapter.agent_chat(case.prompt)

        if case.task_type == "select_backend":
            observed_ids = [
                backend.id
                for backend in load_backends()
                if "`%s`" % backend.id in reply
            ]
            assert case.expected_backend_constraints is not None
            expected_ids = [
                backend.id
                for backend in select_backends(case.expected_backend_constraints)
            ]
            entry["backend_ids"] = observed_ids
            entry["no_match"] = not bool(observed_ids)
            entry["status"] = "PASS" if observed_ids == expected_ids else "FAIL"
            if entry["status"] == "FAIL":
                entry["error_category"] = "backend_selection_mismatch"
        else:
            qasm = extract_qasm(reply)
            entry["parser_valid"] = False
            if qasm is None:
                raise RuntimeError("final reply has no unambiguous OpenQASM")
            circuit = parse_qasm(qasm)
            entry["parser_valid"] = True
            entry["measurement_valid"] = _measurement_valid(case, circuit)
            assert case.expected_target_payload is not None
            expected_target = parse_target_specification(
                case.expected_target_payload
            )
            semantic = verify_semantics(circuit, expected_target)
            entry["semantic_mode"] = semantic.mode
            entry["semantic_valid"] = semantic.passed
            entry["fidelity"] = (
                round(semantic.fidelity, 12)
                if semantic.fidelity is not None
                else None
            )
            entry["status"] = (
                "PASS"
                if semantic.passed and bool(entry["measurement_valid"])
                else "FAIL"
            )
            if not entry["measurement_valid"]:
                entry["error_category"] = "measurement_semantics_mismatch"
            elif not semantic.passed:
                entry["error_category"] = "independent_semantic_mismatch"
    except Exception as exc:
        entry["error_category"] = _error_category(exc)
    finally:
        llm_client.chat_completion = original_chat_completion
        entry["llm_calls"] = call_count
        entry["repair_triggered"] = (
            call_count == 3 if case.task_type != "select_backend" else False
        )
        entry["elapsed_seconds"] = round(time.monotonic() - started, 6)

    if call_count > 3:
        entry["status"] = "FAIL"
        entry["error_category"] = "llm_call_limit_exceeded"
    if entry["elapsed_seconds"] >= 120.0:
        entry["status"] = "FAIL"
        entry["error_category"] = "case_time_limit_exceeded"
    if entry["status"] == "FAIL" and reply is not None:
        # 仅保留 adapter 最终文本，绝不记录原始 HTTP response 或请求头。
        entry["model_output"] = reply
    return entry


def build_report() -> dict[str, Any]:
    """运行真实模型，或在缺少凭证时生成明确的 pending 报告。"""
    repository = _repository_state()
    configured = all(os.environ.get(name) for name in _REQUIRED_MODEL_CONFIGURATION)
    model = os.environ.get("LOOMQ_LLM_MODEL") or "unavailable"
    compatibility_notice = (
        "formal-model compatibility benchmark"
        if model == FORMAL_MODEL
        else "local compatibility benchmark only; not final formal-model evidence"
    )
    started = time.monotonic()

    if not configured:
        entries = []
        for case in AUDIT_CASES:
            entry = _base_entry(case, repository, model)
            entry["status"] = "SKIP"
            entry["error_category"] = "real_model_unavailable"
            entries.append(entry)
        status = "SKIP"
        availability = "unavailable"
    else:
        entries = [
            _run_real_case(case, repository, model) for case in AUDIT_CASES
        ]
        status = "PASS" if all(entry["status"] == "PASS" for entry in entries) else "FAIL"
        availability = "available"

    passed = sum(entry["status"] == "PASS" for entry in entries)
    failed = sum(entry["status"] == "FAIL" for entry in entries)
    pending = sum(entry["status"] == "SKIP" for entry in entries)
    return {
        "suite": "l2-objective-hidden-like",
        "case_set_version": CASE_SET_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": repository["source_commit"],
        "dirty": repository["dirty"],
        "model": model,
        "formal_model": FORMAL_MODEL,
        "status": status,
        "availability": availability,
        "compatibility_notice": compatibility_notice,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "summary": {
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "total": len(entries),
        },
        "cases": entries,
        "notice": (
            "Hidden-like local audit only; cases are not official private tests. "
            "Executable changes after this source commit invalidate the report."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)

    report = build_report()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(rendered + "\n", encoding="utf-8")
        print(
            "[%s] %s: %d pass, %d fail, %d pending"
            % (
                report["status"],
                CASE_SET_VERSION,
                report["summary"]["passed"],
                report["summary"]["failed"],
                report["summary"]["pending"],
            )
        )
    else:
        print(rendered)
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["AUDIT_CASES", "AuditCase", "CASE_SET_VERSION", "build_report", "main"]
