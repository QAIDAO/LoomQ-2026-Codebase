#!/usr/bin/env python3
"""Explicit CLI for OriginQ real-hardware smoke and evidence runs."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from l1_originq_hardware import (
    ENVIRONMENT_FIELDS,
    SUBMISSION_CONFIRMATION,
    OriginQHardwareConfig,
    OriginQHardwareError,
    OriginQHardwareRun,
    resume_originq_hardware,
    run_pyqpanda3_cpuqvm,
    run_originq_hardware,
    sanitize_for_json,
    write_json,
)
from loomq_l1 import normalize_counts, parse_qasm


HERE = Path(__file__).resolve().parent
CIRCUITS = {
    "bell": HERE / "circuits" / "bell.qasm",
    "bit_order": HERE / "circuits" / "bit_order.qasm",
    "ghz3": HERE / "circuits" / "ghz3.qasm",
}
CONFIRMATION = SUBMISSION_CONFIRMATION
MIN_HARDWARE_SUPPORT_PROBABILITY = 0.5


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_originq_hardware.py",
        description=(
            "Plan or explicitly submit OriginQ QCloud real-hardware jobs. "
            "No command submits without --confirm-submit %s."
            % CONFIRMATION
        )
    )
    parser.add_argument(
        "mode",
        choices=("plan", "smoke", "formal", "submit-one", "resume"),
        help=(
            "plan is offline; smoke runs low-shot Bell and bit-order probe; "
            "formal runs Bell and GHZ-3; submit-one submits exactly one explicit "
            "circuit; resume only polls an existing job"
        ),
    )
    parser.add_argument(
        "--confirm-submit",
        metavar="SUBMIT",
        help="required literal confirmation for smoke, formal, and submit-one",
    )
    parser.add_argument(
        "--shots",
        type=int,
        help=(
            "defaults to 100 for smoke and 8192 for formal; explicit for "
            "submit-one and resume"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=HERE / "evidence" / "files" / "originq",
        help="directory for sanitized evidence artifacts",
    )
    parser.add_argument(
        "--task-prefix",
        default="LoomQ-L1",
        help="non-secret QCloud task-name prefix",
    )
    parser.add_argument(
        "--job-id",
        help="existing QCloud job ID; required only for resume",
    )
    parser.add_argument(
        "--circuit",
        choices=tuple(CIRCUITS),
        help="explicit circuit; required for submit-one and resume",
    )
    return parser


def _validate_args(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> Tuple[int, List[str]]:
    if args.mode == "plan":
        if args.confirm_submit is not None:
            parser.error("plan mode does not accept --confirm-submit")
        if args.job_id is not None or args.circuit is not None:
            parser.error("plan mode does not accept --job-id or --circuit")
        if args.shots is not None and args.shots <= 0:
            parser.error("--shots must be positive")
        return 100 if args.shots is None else args.shots, ["bell", "bit_order"]
    if args.mode == "resume":
        if args.confirm_submit is not None:
            parser.error("resume never accepts --confirm-submit")
        if not args.job_id or not args.job_id.strip():
            parser.error("resume requires --job-id")
        if args.circuit is None:
            parser.error("resume requires --circuit")
        if args.shots is None or args.shots <= 0:
            parser.error("resume requires a positive explicit --shots")
        return args.shots, [args.circuit]
    if args.mode == "submit-one":
        if args.confirm_submit != CONFIRMATION:
            parser.error(
                "submit-one requires the exact flag --confirm-submit %s"
                % CONFIRMATION
            )
        if args.job_id is not None:
            parser.error("submit-one does not accept --job-id; use resume")
        if args.circuit is None:
            parser.error("submit-one requires --circuit")
        if args.shots is None or args.shots <= 0:
            parser.error("submit-one requires a positive explicit --shots")
        maximum = 256 if args.circuit == "bit_order" else 8192
        if args.shots > maximum:
            parser.error(
                "submit-one %s is limited to at most %d shots"
                % (args.circuit, maximum)
            )
        if not args.task_prefix.strip():
            parser.error("--task-prefix must be non-empty")
        return args.shots, [args.circuit]
    if args.job_id is not None or args.circuit is not None:
        parser.error("smoke/formal do not accept --job-id or --circuit")
    if args.confirm_submit != CONFIRMATION:
        parser.error(
            "%s mode requires the exact flag --confirm-submit %s"
            % (args.mode, CONFIRMATION)
        )
    if args.shots is None:
        shots = 100 if args.mode == "smoke" else 8192
    else:
        shots = args.shots
    if shots <= 0:
        parser.error("--shots must be positive")
    if args.mode == "smoke" and shots > 256:
        parser.error("smoke mode is limited to at most 256 shots")
    if not args.task_prefix.strip():
        parser.error("--task-prefix must be non-empty")
    return (
        shots,
        ["bell", "bit_order"] if args.mode == "smoke" else ["bell", "ghz3"],
    )


def _safe_job_id(job_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", job_id).strip(".-")
    return safe[:80] or "job"


def _expected_support(name: str) -> Tuple[str, ...]:
    if name == "bell":
        return ("00", "11")
    if name == "bit_order":
        return ("011",)
    return ("000", "111")


def _dominance_summary(name: str, counts: Dict[str, int], shots: int) -> Dict[str, object]:
    expected = _expected_support(name)
    ranked = sorted(
        (key for key, value in counts.items() if value > 0),
        key=lambda key: (-counts[key], key),
    )
    dominant = ranked[: min(len(expected), len(ranked))]
    expected_mass = sum(counts.get(key, 0) for key in expected) / shots
    dominant_states_match = (
        len(dominant) == len(expected) and set(dominant) == set(expected)
    )
    return {
        "expected_support": list(expected),
        "observed_dominant_states": dominant,
        "dominant_states_match": dominant_states_match,
        "expected_support_probability": expected_mass,
        "expected_support_threshold": MIN_HARDWARE_SUPPORT_PROBABILITY,
        "hardware_validation_passed": (
            dominant_states_match
            and expected_mass >= MIN_HARDWARE_SUPPORT_PROBABILITY
        ),
    }


def _run_local_preflight(name: str, circuit, shots: int) -> Dict[str, object]:
    raw, backend, _job_id, _meta = run_pyqpanda3_cpuqvm(circuit, shots)
    counts = normalize_counts(raw, shots, circuit.classical_count)
    dominance = _dominance_summary(name, counts, shots)
    if dominance["expected_support_probability"] < 0.97:
        raise RuntimeError("OriginQ local preflight failed for %s" % name)
    return {"backend": backend, "counts": counts, **dominance}


def _write_text_exclusive(path: Path, text: str) -> None:
    """Write one evidence file exclusively and remove only our partial file."""

    handle = None
    try:
        handle = path.open("x", encoding="utf-8", newline="\n")
        with handle:
            handle.write(text)
    except Exception:
        if handle is not None:
            path.unlink(missing_ok=True)
        raise


def _write_bundle(
    output_dir: Path,
    name: str,
    qasm: str,
    run: OriginQHardwareRun,
) -> Dict[str, Path]:
    stem = "originq-%s-%s" % (name, _safe_job_id(run.summary["job_id"]))
    qasm_path = output_dir / (stem + ".qasm")
    origin_ir_path = output_dir / (stem + ".originir")
    raw_path = output_dir / (stem + "-raw.json")
    summary_path = output_dir / (stem + "-summary.json")
    output_dir.mkdir(parents=True, exist_ok=True)
    created: List[Path] = []
    try:
        _write_text_exclusive(qasm_path, qasm)
        created.append(qasm_path)
        _write_text_exclusive(origin_ir_path, run.origin_ir)
        created.append(origin_ir_path)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    raw_record = sanitize_for_json(dict(run.raw_record))
    raw_record["circuit"] = name
    raw_record["qasm_file"] = qasm_path.name
    raw_record["origin_ir_file"] = origin_ir_path.name
    summary = sanitize_for_json(dict(run.summary))
    counts = summary["counts"]
    summary["circuit"] = name
    summary.update(_dominance_summary(name, counts, summary["shots"]))
    summary["raw_result_file"] = raw_path.name
    summary["qasm_file"] = qasm_path.name
    summary["origin_ir_file"] = origin_ir_path.name
    try:
        write_json(raw_path, raw_record, exclusive=True)
        created.append(raw_path)
        write_json(summary_path, summary, exclusive=True)
        created.append(summary_path)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return {
        "qasm": qasm_path,
        "origin_ir": origin_ir_path,
        "raw": raw_path,
        "summary": summary_path,
    }


def _resume_command(name: str, job_id: str, shots: int) -> str:
    return (
        "python run_originq_hardware.py resume --job-id %s "
        "--circuit %s --shots %d" % (job_id, name, shots)
    )


def _write_failure_record(
    output_dir: Path, name: str, raw_record: Dict[str, object]
) -> Path:
    """Preserve each sanitized failure observation without overwriting one."""

    job_id = _safe_job_id(str(raw_record.get("job_id", "job")))
    base = "originq-%s-failed-%s" % (name, job_id)
    for index in range(1, 101):
        suffix = "" if index == 1 else "-%d" % index
        path = output_dir / (base + suffix + ".json")
        try:
            write_json(path, sanitize_for_json(raw_record), exclusive=True)
            return path
        except FileExistsError:
            continue
    raise OSError("too many existing OriginQ failure records for this job")


def _print_plan(shots: int) -> None:
    print("OriginQ hardware plan (no job submitted)")
    print("  smoke: Bell and bit-order probe, %d shots each, maximum 256" % shots)
    print("  formal: Bell and GHZ-3, default 8192 shots each")
    print("  total default hardware workload: 4 tasks, 16584 shots")
    print("  required environment fields:")
    for field in ENVIRONMENT_FIELDS:
        suffix = " (required)" if field.endswith(("TOKEN", "CHIP_ID")) else " (optional)"
        print("    %s%s" % (field, suffix))
    print("  submission confirmation: --confirm-submit %s" % CONFIRMATION)
    print("  recovery: resume requires job ID, circuit, and original shots; it never submits")


def _execute(
    names: Sequence[str],
    shots: int,
    output_dir: Path,
    task_prefix: str,
    resume_job_id: Optional[str] = None,
) -> int:
    if resume_job_id is not None and len(names) != 1:
        raise ValueError("resume accepts exactly one circuit")
    config = OriginQHardwareConfig.from_env()
    prepared = []
    for name in names:
        qasm = CIRCUITS[name].read_text(encoding="utf-8")
        circuit = parse_qasm(qasm)
        prepared.append((name, qasm, circuit))
    preflights = {
        name: _run_local_preflight(name, circuit, shots)
        for name, _qasm, circuit in prepared
    }
    mismatches = []
    for name, qasm, circuit in prepared:
        task_name = "%s-%s" % (task_prefix.strip(), name)
        known_job_id = resume_job_id

        def report_job(job_id: str) -> None:
            nonlocal known_job_id
            known_job_id = job_id
            action = "Attached to" if resume_job_id is not None else "Submitted"
            print(
                "%s %s job %s; polling..." % (action, name, job_id),
                flush=True,
            )

        try:
            if resume_job_id is None:
                run = run_originq_hardware(
                    circuit,
                    shots,
                    config,
                    confirmation=CONFIRMATION,
                    task_name=task_name,
                    on_submitted=report_job,
                )
            else:
                run = resume_originq_hardware(
                    circuit,
                    shots,
                    config,
                    job_id=resume_job_id,
                    task_name=task_name,
                    on_attached=report_job,
                )
            run.summary.update(
                _dominance_summary(name, run.summary["counts"], run.summary["shots"])
            )
            run.summary["local_preflight"] = preflights[name]
            paths = _write_bundle(output_dir, name, qasm, run)
        except KeyboardInterrupt:
            if known_job_id:
                print(
                    "Interrupted after job %s became known. Do not rerun smoke/formal; "
                    "recover only with:\n  %s"
                    % (known_job_id, _resume_command(name, known_job_id, shots)),
                    file=sys.stderr,
                )
            else:
                print(
                    "Interrupted while submission outcome may be unknown. Inspect the "
                    "OriginQ console before any rerun; if a job exists, use resume.",
                    file=sys.stderr,
                )
            raise
        except OriginQHardwareError as exc:
            if exc.raw_record:
                try:
                    failed_path = _write_failure_record(
                        output_dir, name, exc.raw_record
                    )
                except Exception:
                    print(
                        "Could not write the sanitized OriginQ failure record; "
                        "details suppressed",
                        file=sys.stderr,
                    )
                else:
                    print(
                        "Sanitized failure record: %s" % failed_path,
                        file=sys.stderr,
                    )
            print("OriginQ hardware error: %s" % exc, file=sys.stderr)
            job_id = (
                str(exc.raw_record.get("job_id", ""))
                if exc.raw_record
                else known_job_id or ""
            )
            if job_id:
                print(
                    "Do not rerun smoke/formal for this task; recover only with:\n  %s"
                    % _resume_command(name, job_id, shots),
                    file=sys.stderr,
                )
            else:
                print(
                    "Submission outcome is not proven. Inspect the OriginQ console "
                    "before any rerun.",
                    file=sys.stderr,
                )
            return 1
        except OSError:
            print(
                "OriginQ evidence write failed; partial new files were rolled back.",
                file=sys.stderr,
            )
            if known_job_id:
                print(
                    "The remote job must not be resubmitted. Recover it with:\n  %s"
                    % _resume_command(name, known_job_id, shots),
                    file=sys.stderr,
                )
            return 2
        summary = run.summary
        print("Completed %s job %s" % (name, run.summary["job_id"]))
        print("  raw: %s" % paths["raw"])
        print("  summary: %s" % paths["summary"])
        if not summary["hardware_validation_passed"]:
            mismatches.append(name)
        known_job_id = None
    if mismatches:
        print(
            "OriginQ hardware dominant-state validation failed for: "
            + ", ".join(mismatches),
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    shots, names = _validate_args(parser, args)
    if args.mode == "plan":
        _print_plan(shots)
        return 0
    try:
        return _execute(
            names,
            shots,
            args.output_dir.resolve(),
            args.task_prefix,
            resume_job_id=(args.job_id.strip() if args.mode == "resume" else None),
        )
    except KeyboardInterrupt:
        print(
            "OriginQ workflow interrupted. No automatic resubmission was attempted.",
            file=sys.stderr,
        )
        return 130
    except (OSError, ValueError) as exc:
        print("OriginQ hardware configuration error: %s" % exc, file=sys.stderr)
        return 2
    except OriginQHardwareError as exc:
        print("OriginQ hardware error: %s" % exc, file=sys.stderr)
        return 1
    except Exception:
        print("OriginQ hardware workflow failed; details suppressed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
