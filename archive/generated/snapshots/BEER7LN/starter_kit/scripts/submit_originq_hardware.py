#!/usr/bin/env python3
"""Submit exactly one Wukong 180 job and collect traceable evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Mapping


STARTER_KIT = Path(__file__).resolve().parents[1]
REPOSITORY = STARTER_KIT.parent
SCRIPTS = STARTER_KIT / "scripts"
for path in (STARTER_KIT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import adapter  # noqa: E402
import preflight_originq_hardware as preflight  # noqa: E402
from loomq.hardware import (  # noqa: E402
    assert_no_secret_values,
    extract_originq_counts,
    load_env_file,
    positive_int,
    redact_text,
    require_config,
    sha256_text,
    top_k_states,
)
from loomq.qasm import parse_openqasm2  # noqa: E402


CONFIRMATION = "ORIGINQ_WUKONG_180_REAL_QPU"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit one Wukong 180 Bell job and save raw evidence."
    )
    parser.add_argument("--confirm-submit", choices=(CONFIRMATION,), required=True)
    parser.add_argument(
        "--env-file", type=Path, default=REPOSITORY / ".env.hardware.local"
    )
    parser.add_argument(
        "--circuit", type=Path, default=STARTER_KIT / "circuits" / "bell.qasm"
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=REPOSITORY / "local_docs" / "hardware_runs" / "originq-current.json",
    )
    parser.add_argument(
        "--preflight-output",
        type=Path,
        default=REPOSITORY / "local_docs" / "hardware_preflight" / "originq-submit",
    )
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument("--timeout-seconds", type=float, default=7200.0)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def load_state(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value.get("job_id"):
        raise ValueError("existing OriginQ state file is invalid")
    return value


def normalize_counts(
    raw_counts: Mapping[str, object], shots: int, width: int
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw_state, raw_count in raw_counts.items():
        state = str(raw_state).replace(" ", "")
        if state.lower().startswith("0x"):
            state = format(int(state, 16), f"0{width}b")
        else:
            state = state.zfill(width)
        if set(state) - {"0", "1"} or len(state) != width:
            raise ValueError("OriginQ result contains an invalid bitstring")
        counts[state] = counts.get(state, 0) + int(raw_count)
    if counts and sum(counts.values()) != shots:
        raise ValueError("OriginQ counts do not sum to shots")
    return dict(sorted(counts.items()))


def result_timestamp(timing: Mapping[str, object], fallback: str) -> str:
    for key in ("startTime", "createTime", "submitTime", "endTime"):
        value = timing.get(key)
        if isinstance(value, str) and value:
            if value.isdigit():
                epoch = int(value)
                seconds = epoch / 1000 if epoch > 10_000_000_000 else epoch
                return datetime.fromtimestamp(seconds, timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                )
            return value
    return fallback


def main() -> int:
    args = parse_args()
    config: dict[str, str] = {}
    try:
        config = load_env_file(args.env_file)
        require_config(config, preflight.REQUIRED_CONFIG)
        shots = positive_int(config.get("LOOMQ_HARDWARE_SHOTS", "1024"), "shots")
        if args.poll_seconds <= 0 or args.timeout_seconds <= 0:
            raise ValueError("poll and timeout values must be positive")

        existing = load_state(args.state_file)
        if existing and existing.get("completed"):
            print(json.dumps(existing, ensure_ascii=False, indent=2))
            return 0

        preflight_plan = preflight.build_preflight(
            argparse.Namespace(
                env_file=args.env_file,
                circuit=args.circuit,
                output_dir=args.preflight_output,
            )
        )
        if preflight_plan.get("submitted") is not False:
            raise RuntimeError("preflight did not preserve the no-submit guarantee")

        from pyqpanda3.intermediate_compiler import convert_originir_string_to_qprog
        from pyqpanda3.qcloud import (
            DataBase,
            JobStatus,
            QCloudJob,
            QCloudOptions,
            QCloudService,
        )

        source_qasm = args.circuit.read_text(encoding="utf-8")
        executed_originir = adapter.transpile(source_qasm, "originq")
        program = parse_openqasm2(source_qasm)
        qprog = convert_originir_string_to_qprog(executed_originir)
        backend_name = config["LOOMQ_ORIGINQ_BACKEND"].strip()
        selected_block = list(preflight_plan["platform"]["selected_block"])

        service = QCloudService(config["LOOMQ_ORIGINQ_API_TOKEN"])
        backend = service.backend(backend_name)
        options = QCloudOptions()
        options.set_mapping(True)
        options.set_optimization(True)
        options.set_amend(True)
        options.set_specified_block(selected_block)

        state = existing
        if state is None:
            submitted_at = utc_now()
            job = backend.run(
                qprog,
                shots=shots,
                options=options,
                batch_id="LQ1-OQ-BELL",
            )
            job_id = job.job_id()
            if not job_id:
                raise RuntimeError("OriginQ submission returned no job ID")
            state = {
                "platform": "Origin Quantum Cloud",
                "backend": backend_name,
                "job_id": str(job_id),
                "submitted_at": submitted_at,
                "shots": shots,
                "selected_block": selected_block,
                "circuit_sha256": sha256_text(executed_originir),
                "completed": False,
            }
            write_json(args.state_file, state)
        else:
            job = QCloudJob(str(state["job_id"]))

        job_id = str(state["job_id"])
        run_dir = args.state_file.parent / "originq" / job_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "source.qasm").write_text(source_qasm, encoding="utf-8")
        (run_dir / "executed.originir").write_text(
            executed_originir, encoding="utf-8"
        )
        write_json(run_dir / "submission.json", state)

        deadline = time.monotonic() + args.timeout_seconds
        status = job.status()
        while status not in (JobStatus.FINISHED, JobStatus.FAILED):
            if time.monotonic() >= deadline:
                raise TimeoutError("OriginQ task did not finish before the local timeout")
            time.sleep(args.poll_seconds)
            status = job.status()
        if status == JobStatus.FAILED:
            failed = job.query()
            raw_failed = failed.origin_data()
            (run_dir / "failed-result-raw.json").write_text(
                raw_failed, encoding="utf-8"
            )
            raise RuntimeError("OriginQ real-hardware task failed: " + failed.error_message())

        requested_keys = [
            "mappingQprog",
            "mappingQubit",
            "probCount",
            "convertQProg",
            "srcQubits",
            "targetCbits",
            "measureQubits",
        ]
        try:
            result = job.result(keys=requested_keys)
        except (RuntimeError, TypeError):
            result = job.result()
        raw_result = result.origin_data()
        raw_payload = json.loads(raw_result)
        if not isinstance(raw_payload, dict):
            raise ValueError("OriginQ raw result is not a JSON object")

        raw_counts = dict(result.get_counts(base=DataBase.Binary))
        if raw_counts:
            counts = normalize_counts(
                raw_counts,
                shots=shots,
                width=program.classical_register.size,
            )
            counts_source = "platform_raw_counts"
        else:
            probabilities = dict(result.get_probs(base=DataBase.Binary))
            counts = extract_originq_counts(
                probabilities,
                shots=shots,
                width=program.classical_register.size,
            )
            counts_source = "derived_from_platform_raw_probabilities_using_shots"

        dominant = top_k_states(counts, 2)
        top_k_match = set(dominant) == {"00", "11"}
        timing = dict(result.timing_info())
        normalized = {
            "platform": "Origin Quantum Cloud",
            "backend": backend_name,
            "device": "Wukong 180 superconducting real QPU",
            "job_id": job_id,
            "timestamp": result_timestamp(timing, str(state["submitted_at"])),
            "task_status": int(status.value),
            "task_status_name": status.name,
            "shots": shots,
            "counts": counts,
            "counts_source": counts_source,
            "bit_order": "little",
            "selected_physical_qubits": selected_block,
            "timing_info": timing,
            "circuit": "starter_kit/evidence/files/originq-bell-executed.originir",
            "raw_result": "starter_kit/evidence/files/originq-bell-raw-result.json",
            "top_k_states": dominant,
            "expected_top_k_states": ["00", "11"],
            "top_k_match": top_k_match,
            "source": (
                "adapter.transpile(qasm, 'originq') -> OriginIR -> "
                "pyqpanda3 QProg -> QCloudService"
            ),
            "executed_originir_sha256": sha256_text(executed_originir),
            "raw_result_sha256": sha256_text(raw_result),
        }
        (run_dir / "result-raw.json").write_text(raw_result, encoding="utf-8")
        write_json(run_dir / "result-normalized.json", normalized)

        publication_text = "\n".join(
            (
                executed_originir,
                raw_result,
                json.dumps(normalized, ensure_ascii=False, sort_keys=True),
            )
        )
        assert_no_secret_values(publication_text, config, preflight.SECRET_CONFIG)
        evidence_dir = STARTER_KIT / "evidence" / "files"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "originq-bell-executed.originir").write_text(
            executed_originir, encoding="utf-8"
        )
        (evidence_dir / "originq-bell-raw-result.json").write_text(
            raw_result, encoding="utf-8"
        )
        write_json(evidence_dir / "originq-bell-result.json", normalized)

        state.update(
            {
                "completed": True,
                "completed_at": utc_now(),
                "task_status": status.name,
                "counts": counts,
                "top_k_states": dominant,
                "top_k_match": top_k_match,
                "evidence": {
                    "executed": str(
                        evidence_dir / "originq-bell-executed.originir"
                    ),
                    "raw": str(evidence_dir / "originq-bell-raw-result.json"),
                    "normalized": str(evidence_dir / "originq-bell-result.json"),
                },
            }
        )
        write_json(args.state_file, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            "OriginQ submission failed: "
            + redact_text(str(exc), config, preflight.SECRET_CONFIG),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
