#!/usr/bin/env python3
"""运行 L2 backend capability snapshot release preflight。"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


STARTER_KIT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = STARTER_KIT_ROOT.parent
CAPABILITY_PATH = STARTER_KIT_ROOT / "backend_capabilities.json"
CAPABILITY_DOC_PATH = STARTER_KIT_ROOT / "backend_capabilities.md"
if str(STARTER_KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT_ROOT))

from loomq.backend_selector import (
    Backend,
    BackendConstraints,
    load_backends,
    load_capability_version,
    select_backends,
)


CASE_SET_VERSION = "backend-capability-preflight-2026-08-20-v1"
PINNED_CAPABILITY_VERSION = "2026-07"
PINNED_CAPABILITY_SHA256 = (
    "1d1c2511e01c58c951f0ba9a1a59d8465b37007ae8259280c008caeac1f5cd7b"
)
PINNED_BACKEND_IDS = (
    "spinq_taurus_simulator",
    "spinq_cloud_qpu",
    "originq_local_simulator",
    "originq_wukong",
    "braket_local_simulator",
    "braket_cloud",
)
UPSTREAM_REF = "upstream/main"
_RECOGNIZED_KINDS = {"simulator", "qpu", "cloud"}
_RECOGNIZED_QUEUE_CLASSES = {"none", "minutes_to_hours", "hours"}
_RECOGNIZED_COST_CLASSES = {"free", "free_quota", "paid"}


@dataclass(frozen=True)
class RegressionCase:
    case_id: str
    constraints: BackendConstraints
    expected_backend_ids: tuple[str, ...]


def _constraints(
    *,
    min_qubits: int | None = None,
    require_qpu: bool | None = None,
    require_no_queue: bool = False,
    cost_policy: str = "unspecified",
    allow_account_required: bool | None = None,
) -> BackendConstraints:
    return BackendConstraints(
        min_qubits=min_qubits,
        require_qpu=require_qpu,
        require_no_queue=require_no_queue,
        cost_policy=cost_policy,
        allow_account_required=allow_account_required,
    )


REGRESSION_CASES = (
    RegressionCase(
        "normal_15q_zero_queue",
        _constraints(min_qubits=15, require_no_queue=True),
        (
            "spinq_taurus_simulator",
            "originq_local_simulator",
            "braket_local_simulator",
        ),
    ),
    RegressionCase(
        "negative_not_qpu_not_paid_no_account_no_queue",
        _constraints(
            require_qpu=False,
            require_no_queue=True,
            cost_policy="free_only",
            allow_account_required=False,
        ),
        (
            "spinq_taurus_simulator",
            "originq_local_simulator",
            "braket_local_simulator",
        ),
    ),
    RegressionCase(
        "no_paid",
        _constraints(cost_policy="free_only"),
        (
            "spinq_taurus_simulator",
            "originq_local_simulator",
            "braket_local_simulator",
        ),
    ),
    RegressionCase(
        "no_account",
        _constraints(allow_account_required=False),
        (
            "spinq_taurus_simulator",
            "originq_local_simulator",
            "braket_local_simulator",
        ),
    ),
    RegressionCase(
        "no_queue",
        _constraints(require_no_queue=True),
        (
            "spinq_taurus_simulator",
            "originq_local_simulator",
            "braket_local_simulator",
        ),
    ),
    RegressionCase(
        "qpu_free_or_quota_5q",
        _constraints(
            min_qubits=5,
            require_qpu=True,
            cost_policy="free_or_quota",
        ),
        ("spinq_cloud_qpu", "originq_wukong"),
    ),
    RegressionCase(
        "qpu_zero_queue_no_match",
        _constraints(require_qpu=True, require_no_queue=True),
        (),
    ),
    RegressionCase(
        "over_capacity_no_match",
        _constraints(min_qubits=73),
        (),
    ),
)


def _git_output(arguments: Sequence[str]) -> str | None:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=str(REPOSITORY_ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _repository_state() -> dict[str, Any]:
    metadata_available = (
        _git_output(("rev-parse", "--is-inside-work-tree")) == "true"
    )
    if not metadata_available:
        return {
            "source_commit": "unavailable",
            "dirty": None,
            "git_metadata_available": False,
        }
    dirty_output = _git_output(("status", "--porcelain"))
    return {
        "source_commit": _git_output(("rev-parse", "HEAD")) or "unavailable",
        "dirty": bool(dirty_output) if dirty_output is not None else None,
        "git_metadata_available": True,
    }


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _doc_backend_ids(text: str) -> tuple[str, ...]:
    result = []
    for line in text.splitlines():
        match = re.match(r"^\| `([^`]+)` \|", line)
        if match is not None:
            result.append(match.group(1))
    return tuple(result)


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "detail": detail,
    }


def _skip_check(name: str, detail: str) -> dict[str, Any]:
    return {"name": name, "status": "SKIP", "passed": None, "detail": detail}


def _snapshot_contract(
    raw_payload: Mapping[str, Any],
    raw_backends: Sequence[Mapping[str, Any]],
    content_sha256: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    loaded = load_backends(CAPABILITY_PATH)
    loaded_version = load_capability_version(CAPABILITY_PATH)
    ids = tuple(backend.id for backend in loaded)
    selector_fields = tuple(Backend.__dataclass_fields__)
    field_sets = [set(backend) for backend in raw_backends]
    common_fields = set.intersection(*field_sets) if field_sets else set()
    all_fields = set.union(*field_sets) if field_sets else set()
    fields_consistent = bool(field_sets) and all(
        fields == field_sets[0] for fields in field_sets
    )
    kinds = {backend.get("kind") for backend in raw_backends}
    queues = {backend.get("queue") for backend in raw_backends}
    costs = {backend.get("cost") for backend in raw_backends}
    doc_text = CAPABILITY_DOC_PATH.read_text(encoding="utf-8")
    doc_ids = _doc_backend_ids(doc_text)

    checks = [
        _check(
            "pinned_capability_version",
            loaded_version == PINNED_CAPABILITY_VERSION,
            "observed=%s expected=%s"
            % (loaded_version, PINNED_CAPABILITY_VERSION),
        ),
        _check(
            "pinned_content_sha256",
            content_sha256 == PINNED_CAPABILITY_SHA256,
            "observed=%s expected=%s"
            % (content_sha256, PINNED_CAPABILITY_SHA256),
        ),
        _check(
            "selector_loader_accepts_snapshot",
            len(loaded) == len(raw_backends),
            "loader_count=%d raw_count=%d" % (len(loaded), len(raw_backends)),
        ),
        _check(
            "selector_fields_present",
            set(selector_fields).issubset(common_fields),
            "selector_fields=%s" % ",".join(selector_fields),
        ),
        _check(
            "backend_field_structure_consistent",
            fields_consistent,
            "field_count=%d" % len(all_fields),
        ),
        _check(
            "backend_ids_unique",
            len(ids) == len(set(ids)),
            "backend_count=%d unique_id_count=%d" % (len(ids), len(set(ids))),
        ),
        _check(
            "backend_ids_and_order_pinned",
            ids == PINNED_BACKEND_IDS,
            "observed=%s" % ",".join(ids),
        ),
        _check(
            "selector_enum_values_recognized",
            kinds.issubset(_RECOGNIZED_KINDS)
            and queues.issubset(_RECOGNIZED_QUEUE_CLASSES)
            and costs.issubset(_RECOGNIZED_COST_CLASSES),
            "kind=%s queue=%s cost=%s"
            % (sorted(kinds), sorted(queues), sorted(costs)),
        ),
        _check(
            "documentation_version_matches",
            PINNED_CAPABILITY_VERSION in doc_text,
            "documented_version=%s" % PINNED_CAPABILITY_VERSION,
        ),
        _check(
            "documentation_backend_ids_and_order_match",
            doc_ids == ids,
            "documented_ids=%s" % ",".join(doc_ids),
        ),
    ]
    first_backend = raw_backends[0] if raw_backends else {}
    schema = {
        "top_level_fields": {
            key: _json_type(value) for key, value in raw_payload.items()
        },
        "backend_fields": {
            key: _json_type(value) for key, value in first_backend.items()
        },
        "selector_required_fields": list(selector_fields),
        "common_backend_fields": sorted(common_fields),
        "all_backend_fields": sorted(all_fields),
        "consistent_across_backends": fields_consistent,
        "observed_enums": {
            "kind": sorted(kinds),
            "queue": sorted(queues),
            "cost": sorted(costs),
        },
    }
    return checks, schema


def _repository_drift_checks(
    git_drift: Mapping[str, Any],
) -> list[dict[str, Any]]:
    names = (
        "working_tree_matches_head_blob",
        "local_upstream_ref_available",
        "working_tree_matches_local_upstream_blob",
        "head_matches_local_upstream_blob",
    )
    if not git_drift["repository_metadata_available"]:
        # Docker / archive 不携带仓库元数据，显式记录不可用而不是伪造通过。
        return [
            _skip_check(name, "Git repository metadata unavailable")
            for name in names
        ]
    return [
        _check(
            names[0],
            bool(git_drift["working_tree_matches_head"]),
            "working=%s head=%s"
            % (git_drift["working_tree_blob_oid"], git_drift["head_blob_oid"]),
        ),
        _check(
            names[1],
            bool(git_drift["upstream_available"]),
            "ref=%s commit=%s"
            % (UPSTREAM_REF, git_drift["upstream_commit"]),
        ),
        _check(
            names[2],
            bool(git_drift["working_tree_matches_upstream"]),
            "working=%s upstream=%s"
            % (
                git_drift["working_tree_blob_oid"],
                git_drift["upstream_blob_oid"],
            ),
        ),
        _check(
            names[3],
            bool(git_drift["head_matches_upstream"]),
            "head=%s upstream=%s"
            % (git_drift["head_blob_oid"], git_drift["upstream_blob_oid"]),
        ),
    ]


def _regression_entry(
    case: RegressionCase,
    capabilities: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    selected = select_backends(case.constraints, capabilities_path=CAPABILITY_PATH)
    selected_ids = [backend.id for backend in selected]
    expected_ids = list(case.expected_backend_ids)
    invented = [backend_id for backend_id in selected_ids if backend_id not in capabilities]
    mismatch_reasons = []
    if selected_ids != expected_ids:
        mismatch_reasons.append("selector result or official table order differs")
    if invented:
        mismatch_reasons.append("selector returned backend id outside capability snapshot")
    return {
        "case_id": case.case_id,
        "input_constraints": asdict(case.constraints),
        "current_capability": [capabilities[backend_id] for backend_id in selected_ids],
        "selector_result": selected_ids,
        "expected_result": expected_ids,
        "invented_backend_ids": invented,
        "no_match": not bool(selected_ids),
        "ordering_stable": selected_ids == expected_ids,
        "status": "PASS" if not mismatch_reasons else "FAIL",
        "mismatch_reason": "; ".join(mismatch_reasons) or None,
    }


def build_report() -> dict[str, Any]:
    started = time.perf_counter()
    repository = _repository_state()
    raw_bytes = CAPABILITY_PATH.read_bytes()
    raw_payload = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(raw_payload, dict):
        raise RuntimeError("backend capability snapshot must be a JSON object")
    raw_backends_value = raw_payload.get("backends")
    if not isinstance(raw_backends_value, list) or not all(
        isinstance(backend, dict) for backend in raw_backends_value
    ):
        raise RuntimeError("backend capability snapshot must contain object entries")
    raw_backends: list[Mapping[str, Any]] = raw_backends_value
    content_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    relative_path = str(CAPABILITY_PATH.relative_to(REPOSITORY_ROOT))
    metadata_available = repository["git_metadata_available"]
    working_blob = (
        _git_output(("hash-object", relative_path)) if metadata_available else None
    )
    head_blob = (
        _git_output(("rev-parse", "HEAD:%s" % relative_path))
        if metadata_available
        else None
    )
    upstream_commit = (
        _git_output(("rev-parse", UPSTREAM_REF)) if metadata_available else None
    )
    upstream_blob = (
        _git_output(("rev-parse", "%s:%s" % (UPSTREAM_REF, relative_path)))
        if metadata_available
        else None
    )
    git_drift = {
        "repository_metadata_available": metadata_available,
        "availability": "available" if metadata_available else "unavailable",
        "working_tree_blob_oid": working_blob,
        "head_blob_oid": head_blob,
        "upstream_ref": UPSTREAM_REF,
        "upstream_commit": upstream_commit,
        "upstream_blob_oid": upstream_blob,
        "upstream_available": (
            upstream_commit is not None and upstream_blob is not None
            if metadata_available
            else None
        ),
        "working_tree_matches_head": (
            working_blob is not None and working_blob == head_blob
            if metadata_available
            else None
        ),
        "working_tree_matches_upstream": (
            working_blob is not None and working_blob == upstream_blob
            if metadata_available
            else None
        ),
        "head_matches_upstream": (
            head_blob is not None and head_blob == upstream_blob
            if metadata_available
            else None
        ),
        "network_requests": 0,
    }
    checks, schema = _snapshot_contract(
        raw_payload,
        raw_backends,
        content_sha256,
    )
    repository_drift_checks = _repository_drift_checks(git_drift)
    capabilities = {
        str(backend["id"]): dict(backend) for backend in raw_backends
    }
    regressions = [
        _regression_entry(case, capabilities) for case in REGRESSION_CASES
    ]
    regression_passed = sum(entry["status"] == "PASS" for entry in regressions)
    regression_failed = len(regressions) - regression_passed
    failed_checks = [check["name"] for check in checks if not check["passed"]]
    failed_drift_checks = [
        check["name"]
        for check in repository_drift_checks
        if check["status"] == "FAIL"
    ]
    skipped_drift_checks = [
        check["name"]
        for check in repository_drift_checks
        if check["status"] == "SKIP"
    ]
    drift_status = (
        "FAIL"
        if failed_drift_checks
        else "SKIP"
        if skipped_drift_checks
        else "PASS"
    )
    git_drift["status"] = drift_status
    status = (
        "PASS"
        if not failed_checks
        and not failed_drift_checks
        and regression_failed == 0
        else "FAIL"
    )
    return {
        "case_set_version": CASE_SET_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": repository["source_commit"],
        "dirty": repository["dirty"],
        "status": status,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "capability": {
            "file_path": str(CAPABILITY_PATH),
            "version": load_capability_version(CAPABILITY_PATH),
            "content_sha256": content_sha256,
            "git_blob_oid": working_blob,
            "backend_count": len(raw_backends),
            "backend_ids": [backend["id"] for backend in raw_backends],
            "field_structure": schema,
        },
        "git_drift": git_drift,
        "contract_summary": {
            "passed": len(checks) - len(failed_checks),
            "failed": len(failed_checks),
            "total": len(checks),
            "failed_checks": failed_checks,
        },
        "contract_checks": checks,
        "repository_drift_summary": {
            "status": drift_status,
            "passed": len(repository_drift_checks)
            - len(failed_drift_checks)
            - len(skipped_drift_checks),
            "failed": len(failed_drift_checks),
            "skipped": len(skipped_drift_checks),
            "total": len(repository_drift_checks),
            "failed_checks": failed_drift_checks,
            "skipped_checks": skipped_drift_checks,
        },
        "repository_drift_checks": repository_drift_checks,
        "regression_summary": {
            "passed": regression_passed,
            "failed": regression_failed,
            "total": len(regressions),
        },
        "selector_regressions": regressions,
        "tests_executed": {
            "production_functions": [
                "load_backends",
                "load_capability_version",
                "select_backends",
            ],
            "contract_check_count": len(checks),
            "repository_drift_check_count": len(repository_drift_checks),
            "selector_case_ids": [case.case_id for case in REGRESSION_CASES],
            "network_requests": 0,
        },
        "remaining_risk": [
            "The upstream comparison uses the existing local upstream/main ref and does not fetch the network; a stale local ref cannot detect a newer remote commit.",
            "Repository drift checks are unavailable in Docker/archive environments without Git metadata and must also be run in a real checkout before release.",
            "The capability snapshot is an evaluator baseline, not live backend availability, price, or queue telemetry.",
            "Natural-language constraint extraction remains model-dependent; this preflight verifies the deterministic selector after structured constraints exist.",
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    report = build_report()
    payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    if args.json_out is not None:
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
