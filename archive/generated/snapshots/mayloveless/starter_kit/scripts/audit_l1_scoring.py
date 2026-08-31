#!/usr/bin/env python3
"""以 8192 shots 执行 L1 三平台 scoring-like 审计并输出 JSON。"""

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 支持按任务文档直接运行 ``python scripts/audit_l1_scoring.py``。
STARTER_KIT_ROOT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT_ROOT))

import adapter
from evaluator import calculate_hellinger_fidelity, validate_schema
from loomq.parser import parse_qasm
from loomq.serializers.braket import serialize_braket
from scripts.l1_native import execute_native_artifact, normalized_native_counts
from tests.test_l1_hidden_like import (
    RANDOM_SEEDS,
    GateRecord,
    basis_preparation,
    build_qasm,
    grover_3_operations,
    inverse_operations,
    oracle_cases,
    qft_operations,
    random_identity_case,
)


DEFAULT_SHOTS = 8192
TARGETS = ("spinq", "originq", "braket")
FIDELITY_THRESHOLD = 0.97


@dataclass(frozen=True)
class AuditCase:
    case_id: str
    source: str
    expected: Dict[str, float]
    native: bool = True


def _audit_cases() -> Tuple[AuditCase, ...]:
    ghz = build_qasm(
        5,
        (GateRecord("h", (0,)),)
        + tuple(GateRecord("cx", (index, index + 1)) for index in range(4)),
    )
    qft = qft_operations(4)
    qft_round_trip = build_qasm(
        4, basis_preparation("1010") + qft + inverse_operations(qft)
    )
    # 一轮三比特 Grover：标记态概率 25/32，其余七态各 1/32。
    grover_expected = {
        format(value, "03b"): (25.0 / 32.0 if value == 7 else 1.0 / 32.0)
        for value in range(8)
    }
    cases: List[AuditCase] = [
        AuditCase("ghz_5", ghz, {"00000": 0.5, "11111": 0.5}),
        AuditCase("qft_4_round_trip", qft_round_trip, {"1010": 1.0}),
        AuditCase(
            "grover_3",
            build_qasm(3, grover_3_operations()),
            grover_expected,
        ),
    ]
    for seed in RANDOM_SEEDS:
        source, initial_key, _operations = random_identity_case(seed)
        cases.append(
            AuditCase("random_u_inverse_%d" % seed, source, {initial_key: 1.0})
        )
    for case in oracle_cases():
        cases.append(
            AuditCase(
                "oracle_%s" % case.case_id,
                case.source,
                {case.expected_key: 1.0},
                # 厂商结果对象未统一暴露未测量经典位；run 路径仍完整覆盖。
                native=case.case_id != "multiple_classical_registers",
            )
        )
    return tuple(cases)


def _source_sha(source: str) -> str:
    return "sha256:%s" % hashlib.sha256(source.encode("utf-8")).hexdigest()


def _repository_state() -> Dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    try:
        revision = subprocess.run(
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
        return {"commit": revision, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "unavailable", "dirty": None}


def _target_available(target: str) -> Tuple[bool, str]:
    try:
        if target == "braket":
            available = importlib.util.find_spec("braket") is not None
            return available, "available" if available else "braket import unavailable"
        if target == "spinq":
            from loomq.runners.spinq import _find_spinq_python

            return True, str(_find_spinq_python())
        if target == "originq":
            from loomq.runners.originq import _find_originq_python

            return True, str(_find_originq_python())
    except RuntimeError as exc:
        return False, str(exc)
    return False, "unsupported target"


def _distribution(counts: Dict[str, int], shots: int) -> Dict[str, float]:
    return {key: value / shots for key, value in counts.items()}


def _score_entry(
    case: AuditCase,
    target: str,
    path: str,
    shots: int,
    counts: Dict[str, int],
    elapsed: float,
    sdk_version: Optional[str],
) -> Dict[str, Any]:
    observed = _distribution(counts, shots)
    fidelity = calculate_hellinger_fidelity(observed, case.expected)
    deterministic_key = (
        next(iter(case.expected))
        if len(case.expected) == 1 and next(iter(case.expected.values())) == 1.0
        else None
    )
    deterministic_probability = (
        observed.get(deterministic_key, 0.0) if deterministic_key else None
    )
    return {
        "source_sha": _source_sha(case.source),
        "case_id": case.case_id,
        "target": target,
        "path": path,
        "shots": shots,
        "fidelity": round(fidelity, 8),
        "deterministic_probability": (
            round(deterministic_probability, 8)
            if deterministic_probability is not None
            else None
        ),
        "status": "PASS" if fidelity >= FIDELITY_THRESHOLD else "FAIL",
        "elapsed_seconds": round(elapsed, 6),
        "sdk_version": sdk_version,
    }


def _run_case(case: AuditCase, target: str, shots: int) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        result = adapter.run(case.source, target, shots)
        valid, reason = validate_schema(result)
        if not valid:
            raise ValueError(reason)
        entry = _score_entry(
            case,
            target,
            "run",
            shots,
            dict(result["counts"]),
            time.perf_counter() - started,
            None,
        )
        entry["backend"] = result.get("backend")
        return entry
    except Exception as exc:
        return {
            "source_sha": _source_sha(case.source),
            "case_id": case.case_id,
            "target": target,
            "path": "run",
            "shots": shots,
            "fidelity": None,
            "deterministic_probability": None,
            "status": "FAIL",
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "sdk_version": None,
            "error": "%s: %s" % (type(exc).__name__, exc),
        }


def _run_native_case(case: AuditCase, target: str, shots: int) -> Dict[str, Any]:
    started = time.perf_counter()
    path = "transpile_native"
    try:
        if target == "braket":
            # pinned LocalSimulator 无法直接解析比赛 canonical stdgates artifact；
            # 此路径只审计 Runner 使用的 SDK 兼容方言。
            artifact = serialize_braket(
                parse_qasm(case.source),
                include_stdgates=False,
                execution_mode=True,
            )
            path = "execution_mode_sdk"
        else:
            artifact = adapter.transpile(case.source, target)
        payload = execute_native_artifact(target, artifact, shots)
        counts = normalized_native_counts(payload, shots)
        return _score_entry(
            case,
            target,
            path,
            shots,
            counts,
            time.perf_counter() - started,
            str(payload.get("sdk_version") or "unknown"),
        )
    except Exception as exc:
        return {
            "source_sha": _source_sha(case.source),
            "case_id": case.case_id,
            "target": target,
            "path": path,
            "shots": shots,
            "fidelity": None,
            "deterministic_probability": None,
            "status": "FAIL",
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "sdk_version": None,
            "error": "%s: %s" % (type(exc).__name__, exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=int, default=DEFAULT_SHOTS)
    parser.add_argument("--targets", default=",".join(TARGETS))
    parser.add_argument("--json-out")
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="任一目标 SDK 不可用时返回失败，供最终 Docker 审计使用",
    )
    args = parser.parse_args()
    selected = tuple(
        target.strip() for target in args.targets.split(",") if target.strip()
    )
    unknown = sorted(set(selected) - set(TARGETS))
    if unknown:
        parser.error("unsupported target(s): %s" % ", ".join(unknown))
    if args.shots <= 0:
        parser.error("--shots must be positive")

    capabilities = {
        target: dict(zip(("available", "detail"), _target_available(target)))
        for target in selected
    }
    entries: List[Dict[str, Any]] = []
    versions: Dict[str, str] = {}
    for target in selected:
        if not capabilities[target]["available"]:
            continue
        for case in _audit_cases():
            run_entry = _run_case(case, target, args.shots)
            entries.append(run_entry)
            print(
                "[%s] %s %s run %.3fs"
                % (
                    run_entry["status"],
                    target,
                    case.case_id,
                    run_entry["elapsed_seconds"],
                )
            )
            if case.native:
                native_entry = _run_native_case(case, target, args.shots)
                entries.append(native_entry)
                if native_entry.get("sdk_version"):
                    versions[target] = native_entry["sdk_version"]
                print(
                    "[%s] %s %s %s %.3fs"
                    % (
                        native_entry["status"],
                        target,
                        case.case_id,
                        native_entry["path"],
                        native_entry["elapsed_seconds"],
                    )
                )

    for entry in entries:
        if entry["sdk_version"] is None and entry["target"] in versions:
            entry["sdk_version"] = versions[entry["target"]]
    missing = [
        target for target, capability in capabilities.items() if not capability["available"]
    ]
    passed = sum(entry["status"] == "PASS" for entry in entries)
    failed = sum(entry["status"] == "FAIL" for entry in entries)
    report = {
        "suite": "l1-scoring-like",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": _repository_state(),
        "shots": args.shots,
        "fidelity_threshold": FIDELITY_THRESHOLD,
        "capabilities": capabilities,
        "validation_boundaries": {
            "spinq": "public QASM2 via SpinQit QASM compiler",
            "originq": "public OriginIR via pyQPanda converter and CPUQVM",
            "braket": (
                "canonical public OQ3 is contract-shape validated; SDK semantics "
                "use execution_mode_sdk because pinned LocalSimulator has a "
                "stdgates parser dialect difference"
            ),
        },
        "summary": {
            "passed": passed,
            "failed": failed,
            "total": len(entries),
            "missing_targets": missing,
        },
        "cases": entries,
        "notice": (
            "Audit report for these exact source_sha values; later executable "
            "changes invalidate it. This is not final submission evidence."
        ),
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    if failed:
        return 1
    if args.require_all and missing:
        return 1
    return 0 if entries else 1


if __name__ == "__main__":
    sys.exit(main())
