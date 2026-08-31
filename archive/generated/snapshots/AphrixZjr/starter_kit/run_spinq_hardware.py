#!/usr/bin/env python3
"""Explicit SpinQ Cloud smoke/formal runner and evidence writer.

Dry-run is the default and never initializes a cloud client. A smoke or formal
run requires the literal ``--confirm-submit SPINQ_HARDWARE`` confirmation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from l1_spinq import run_spinq
from l1_spinq_hardware import (
    OPTIONAL_ENVIRONMENT_DEFAULTS,
    REQUIRED_ENVIRONMENT,
    SUBMISSION_CONFIRMATION,
    SpinQHardwareError,
    SpinQHardwareSettings,
    build_dry_run_manifest,
    emit_spinq_cloud,
    execute_spinq_hardware,
    recover_spinq_hardware,
)
from evaluator import validate_schema
from loomq_l1 import Circuit, normalize_counts, parse_qasm


ROOT = Path(__file__).resolve().parent
CIRCUIT_PATHS = {
    "bell": ROOT / "circuits" / "bell.qasm",
    "bit_order": ROOT / "circuits" / "bit_order.qasm",
    "bit_order_direction": ROOT / "circuits" / "bit_order_direction.qasm",
    "ghz3": ROOT / "circuits" / "ghz3.qasm",
}
MODE_CIRCUITS = {
    "plan": (),
    "dry-run": ("bell", "bit_order", "ghz3"),
    "smoke": ("bell", "bit_order"),
    "formal": ("bell", "ghz3"),
    "submit-one": (),
    "resume": (),
}
DEFAULT_SHOTS = {"dry-run": 8192, "smoke": 100, "formal": 8192}
MAX_SINGLE_TASK_SHOTS = {
    "bell": 8192,
    "bit_order": 256,
    "bit_order_direction": 256,
    "ghz3": 8192,
}
EXPECTED_STATES = {
    "bell": {"00", "11"},
    "bit_order": {"011"},
    "bit_order_direction": {"100"},
    "ghz3": {"000", "111"},
}
MIN_HARDWARE_SUPPORT_PROBABILITY = 0.5
SUMMARY_SCHEMA_VERSION = "loomq-spinq-hardware-summary-v1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or explicitly submit SpinQ Cloud L1 hardware tasks."
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=tuple(MODE_CIRCUITS),
        default="dry-run",
        help=(
            "dry-run never contacts the cloud; smoke submits Bell and a "
            "mapping probe; formal submits Bell and GHZ-3; submit-one is "
            "the explicit opt-in path for one bounded task"
        ),
    )
    parser.add_argument(
        "--confirm-submit",
        metavar="PHRASE",
        help="required literal for hardware runs: %s" % SUBMISSION_CONFIRMATION,
    )
    parser.add_argument("--shots", type=int, help="override the mode's shot count")
    parser.add_argument(
        "--job-id", help="existing SpinQ task code; accepted only in resume mode"
    )
    parser.add_argument(
        "--circuit",
        choices=tuple(CIRCUIT_PATHS),
        help="circuit identity for an existing task; required in resume mode",
    )
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=5.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "evidence" / "files" / "hardware" / "spinq",
        help="destination for completed, redacted evidence bundles",
    )
    return parser


def _load_circuits(names: Iterable[str]) -> Tuple[Tuple[str, Circuit], ...]:
    return tuple(
        (name, parse_qasm(CIRCUIT_PATHS[name].read_text(encoding="utf-8")))
        for name in names
    )


def _dominance_summary(name: str, counts: Mapping[str, int], shots: int) -> Dict[str, Any]:
    expected = EXPECTED_STATES[name]
    ranked = sorted(
        (key for key, value in counts.items() if value > 0),
        key=lambda key: (-counts[key], key),
    )
    dominant = ranked[: min(len(expected), len(ranked))]
    expected_mass = sum(counts.get(key, 0) for key in expected) / shots
    dominant_states_match = (
        len(dominant) == len(expected) and set(dominant) == expected
    )
    return {
        "expected_dominant_states": sorted(expected),
        "observed_dominant_states": dominant,
        "dominant_states_match": dominant_states_match,
        "expected_state_mass": expected_mass,
        "expected_state_threshold": MIN_HARDWARE_SUPPORT_PROBABILITY,
        "hardware_validation_passed": (
            dominant_states_match
            and expected_mass >= MIN_HARDWARE_SUPPORT_PROBABILITY
        ),
    }


def _run_local_preflight(name: str, circuit: Circuit, shots: int) -> Dict[str, Any]:
    raw, backend, _job_id, _meta = run_spinq(circuit, shots)
    counts = normalize_counts(raw, shots, circuit.classical_count)
    summary = _dominance_summary(name, counts, shots)
    if summary["expected_state_mass"] < 0.97:
        raise RuntimeError("SpinQ local preflight failed for %s" % name)
    return {"backend": backend, "counts": counts, **summary}


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.")
    return (stem or "task")[:120]


def _write_evidence_bundle(
    output_dir: Path,
    mode: str,
    name: str,
    circuit: Circuit,
    source_qasm: str,
    result: Mapping[str, Any],
) -> Tuple[Path, Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = "spinq-%s-%s-%s" % (
        mode,
        name,
        _safe_stem(str(result["job_id"])),
    )
    source_path = output_dir / (stem + "-source.qasm")
    submitted_path = output_dir / (stem + "-submitted.qasm")
    request_path = output_dir / (stem + "-request.json")
    raw_path = output_dir / (stem + "-raw.json")
    summary_path = output_dir / (stem + "-summary.json")
    submitted_qasm = emit_spinq_cloud(circuit)
    source_hash = hashlib.sha256(source_qasm.encode("utf-8")).hexdigest()
    submitted_hash = hashlib.sha256(submitted_qasm.encode("utf-8")).hexdigest()

    valid, reason = validate_schema(dict(result))
    if not valid:
        raise ValueError("SpinQ result schema is invalid: " + reason)
    meta = result.get("meta")
    request = result.get("request")
    if not isinstance(meta, Mapping) or not isinstance(request, Mapping):
        raise ValueError("SpinQ evidence is missing meta or request data")
    for field, expected in (
        ("source_qasm_sha256", source_hash),
        ("submitted_qasm_sha256", submitted_hash),
    ):
        if meta.get(field) != expected or request.get(field) != expected:
            raise ValueError("SpinQ evidence %s does not match its artifact" % field)

    raw_payload = json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
    raw_payload["meta"]["raw_evidence_file"] = raw_path.name
    request_payload = dict(raw_payload["request"])
    request_payload.update(
        {
            "job_id": str(result["job_id"]),
            "source_qasm_file": source_path.name,
            "submitted_qasm_file": submitted_path.name,
        }
    )
    summary_keys = (
        "schema_version",
        "sdk_api",
        "backend",
        "device_code",
        "job_id",
        "shots",
        "counts",
        "counts_normalization",
        "bit_order",
        "timestamp",
        "meta",
        "submitted_at",
        "completed_at",
        "recovered_at",
        "recovered_existing_job",
        "submission_status",
        "poll_count",
        "mode",
        "circuit",
        "expected_dominant_states",
        "observed_dominant_states",
        "dominant_states_match",
        "expected_state_mass",
        "expected_state_threshold",
        "hardware_validation_passed",
    )
    summary_payload = {
        key: raw_payload[key] for key in summary_keys if key in raw_payload
    }
    summary_payload.update(
        {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "source_qasm_file": source_path.name,
            "submitted_qasm_file": submitted_path.name,
            "request_file": request_path.name,
        }
    )

    # Avoid silently replacing evidence from an earlier hardware job.
    created = []
    try:
        for path, content in (
            (source_path, source_qasm),
            (submitted_path, submitted_qasm),
        ):
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
            created.append(path)
        for path, payload in (
            (request_path, request_payload),
            (raw_path, raw_payload),
            (summary_path, summary_payload),
        ):
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.write("\n")
            created.append(path)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return source_path, submitted_path, request_path, raw_path, summary_path


def _print_event(event: str, fields: Mapping[str, Any]) -> None:
    print(json.dumps({"event": event, **fields}, ensure_ascii=False), flush=True)


def _print_plan() -> None:
    print("SpinQ Cloud hardware plan (offline; no cloud call made)")
    print("1. smoke bell: 100 shots")
    print("2. smoke bit_order: 100 shots")
    print("3. formal bell: 8192 shots")
    print("4. formal ghz3: 8192 shots")
    print("total: 4 hardware tasks, 16584 shots")
    print("recommended quota with one full rerun: 8 tasks, 33168 shots")
    print(
        "optional direction probe: one separate bit_order_direction task, "
        "100 shots recommended (not included above)"
    )
    print("required environment fields (values are never printed):")
    for name in REQUIRED_ENVIRONMENT:
        print("- %s" % name)
    print("optional routing overrides (SDK defaults are used when unset):")
    for name, value in OPTIONAL_ENVIRONMENT_DEFAULTS.items():
        print("- %s=%s" % (name, value))
    print("submission confirmation: --confirm-submit %s" % SUBMISSION_CONFIRMATION)


def main(
    argv: Optional[Sequence[str]] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.mode == "plan":
        if (
            args.confirm_submit is not None
            or args.shots is not None
            or args.job_id is not None
            or args.circuit is not None
        ):
            parser.error("plan mode does not accept submission or shot overrides")
        _print_plan()
        return 0
    if args.mode == "resume":
        if args.confirm_submit is not None:
            parser.error("resume is read-only and does not accept submission confirmation")
        if args.job_id is None or args.circuit is None or args.shots is None:
            parser.error("resume requires --job-id, --circuit, and --shots")
        shots = args.shots
        circuits = _load_circuits((args.circuit,))
    elif args.mode == "submit-one":
        if args.job_id is not None:
            parser.error("submit-one does not accept --job-id")
        if args.circuit is None or args.shots is None:
            parser.error("submit-one requires --circuit and --shots")
        shots = args.shots
        circuits = _load_circuits((args.circuit,))
    else:
        if args.job_id is not None or args.circuit is not None:
            parser.error("--job-id and --circuit are accepted only in resume mode")
        shots = DEFAULT_SHOTS[args.mode] if args.shots is None else args.shots
        circuits = _load_circuits(MODE_CIRCUITS[args.mode])
    if shots <= 0:
        parser.error("--shots must be positive")
    if args.mode == "smoke" and shots > 256:
        parser.error("smoke mode is limited to at most 256 shots")
    if args.mode == "submit-one" and shots > MAX_SINGLE_TASK_SHOTS[args.circuit]:
        parser.error(
            "submit-one %s is limited to at most %d shots"
            % (args.circuit, MAX_SINGLE_TASK_SHOTS[args.circuit])
        )

    if args.mode == "dry-run":
        manifests = [
            build_dry_run_manifest(circuit, shots, name)
            for name, circuit in circuits
        ]
        print(json.dumps(manifests, ensure_ascii=False, indent=2))
        return 0

    if args.mode != "resume" and args.confirm_submit != SUBMISSION_CONFIRMATION:
        print(
            "error: hardware submission is locked; pass --confirm-submit %s"
            % SUBMISSION_CONFIRMATION,
            file=sys.stderr,
        )
        return 2

    try:
        settings = SpinQHardwareSettings.from_environment(environ)
        # Complete every local check before the first paid/queued cloud task.
        preflights = {
            name: _run_local_preflight(name, circuit, shots)
            for name, circuit in circuits
        }
        _print_event(
            "local-preflight-complete",
            {"mode": args.mode, "circuits": list(preflights)},
        )

        mismatches = []
        for name, circuit in circuits:
            source_qasm = CIRCUIT_PATHS[name].read_text(encoding="utf-8")
            if args.mode == "resume":
                _print_event(
                    "recovery-started",
                    {"job_id": args.job_id, "circuit": name, "will_submit": False},
                )
                result = recover_spinq_hardware(
                    circuit,
                    shots,
                    settings,
                    args.job_id,
                    source_qasm=source_qasm,
                    timeout_seconds=args.timeout_seconds,
                    poll_interval_seconds=args.poll_interval_seconds,
                    event_handler=_print_event,
                )
            else:
                result = execute_spinq_hardware(
                    circuit,
                    shots,
                    settings,
                    confirmation=args.confirm_submit,
                    source_qasm=source_qasm,
                    timeout_seconds=args.timeout_seconds,
                    poll_interval_seconds=args.poll_interval_seconds,
                    task_name="LoomQ L1 %s %s" % (args.mode, name),
                    task_description="LoomQ L1 hardware evidence; %s" % name,
                    event_handler=_print_event,
                )
            result["mode"] = args.mode
            result["circuit"] = name
            result["local_preflight"] = preflights[name]
            result.update(_dominance_summary(name, result["counts"], shots))
            (
                source_path,
                submitted_path,
                request_path,
                raw_path,
                summary_path,
            ) = _write_evidence_bundle(
                args.output_dir,
                args.mode,
                name,
                circuit,
                source_qasm,
                result,
            )
            _print_event(
                "evidence-written",
                {
                    "job_id": result["job_id"],
                    "source_qasm": str(source_path),
                    "submitted_qasm": str(submitted_path),
                    "request": str(request_path),
                    "raw": str(raw_path),
                    "summary": str(summary_path),
                    "dominant_states_match": result["dominant_states_match"],
                    "hardware_validation_passed": result[
                        "hardware_validation_passed"
                    ],
                },
            )
            if not result["hardware_validation_passed"]:
                mismatches.append(name)
        if mismatches:
            print(
                "error: hardware dominant-state validation failed for: "
                + ", ".join(mismatches),
                file=sys.stderr,
            )
            return 1
        return 0
    except SpinQHardwareError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except Exception:
        # Never print tracebacks from SDK/network exceptions: they may contain
        # request fields or the configured private-key path.
        print("error: hardware workflow failed; details suppressed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
