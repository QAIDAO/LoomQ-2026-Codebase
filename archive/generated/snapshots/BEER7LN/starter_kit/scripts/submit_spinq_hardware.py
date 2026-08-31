#!/usr/bin/env python3
"""Submit exactly one SpinQ real-QPU job and collect traceable evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time


STARTER_KIT = Path(__file__).resolve().parents[1]
REPOSITORY = STARTER_KIT.parent
SCRIPTS = STARTER_KIT / "scripts"
for path in (STARTER_KIT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import adapter  # noqa: E402
import preflight_spinq_hardware as preflight  # noqa: E402
from loomq.hardware import (  # noqa: E402
    assert_no_secret_values,
    extract_spinq_counts,
    load_env_file,
    positive_int,
    prepare_spinq_cloud_qasm,
    redact_text,
    require_config,
    sha256_text,
    top_k_states,
)
from loomq.qasm import parse_openqasm2  # noqa: E402


CONFIRMATION = "SPINQ_REAL_QPU"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit one SpinQ real-QPU Bell job and save raw evidence."
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
        default=REPOSITORY / "local_docs" / "hardware_runs" / "spinq-current.json",
    )
    parser.add_argument(
        "--preflight-output",
        type=Path,
        default=REPOSITORY / "local_docs" / "hardware_preflight" / "spinq-submit",
    )
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
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
        raise ValueError("existing SpinQ state file is invalid")
    return value


def get_task_timestamp(task_payload: object, fallback: str) -> str:
    if isinstance(task_payload, dict):
        task = task_payload.get("task")
        if isinstance(task, dict):
            value = task.get("createdTime") or task.get("created_time")
            if isinstance(value, str) and value:
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

        preflight_args = argparse.Namespace(
            env_file=args.env_file,
            circuit=args.circuit,
            output_dir=args.preflight_output,
        )
        preflight_manifest = preflight.build_preflight(preflight_args)
        if preflight_manifest.get("submitted") is not False:
            raise RuntimeError("preflight did not preserve the no-submit guarantee")

        from spinqit import SpinQCloudConfig, get_spinq_cloud

        source_qasm = args.circuit.read_text(encoding="utf-8")
        transpiled_qasm = adapter.transpile(source_qasm, "spinq")
        executed_qasm = prepare_spinq_cloud_qasm(transpiled_qasm)
        program = parse_openqasm2(transpiled_qasm)
        ir = preflight.compile_spinq_ir(executed_qasm)

        backend = get_spinq_cloud(
            config["LOOMQ_SPINQ_USERNAME"],
            config["LOOMQ_SPINQ_KEYFILE"],
            config["LOOMQ_SPINQ_HOST"],
        )
        platform = backend.get_platform(config["LOOMQ_SPINQ_PLATFORM_CODE"])
        if platform.simu:
            raise ValueError("configured SpinQ platform is not real hardware")
        if not platform.available():
            raise RuntimeError("configured SpinQ real platform is currently offline")

        state = existing
        if state is None:
            submitted_at = utc_now()
            task_prefix = config.get("LOOMQ_HARDWARE_TASK_PREFIX", "LoomQ-L1")
            task_name = f"{task_prefix}-spinq-bell-{submitted_at[:19].replace(':', '')}Z"
            cloud_config = SpinQCloudConfig()
            cloud_config.configure_platform(platform.code)
            cloud_config.configure_shots(shots)
            cloud_config.configure_task(task_name, "LoomQ L1 Bell real-hardware evidence")
            status, message, job_id = backend.submit_task(ir, cloud_config, debug=False)
            if not job_id:
                raise RuntimeError(f"SpinQ submission returned no job ID (status {status})")
            state = {
                "platform": "SpinQ Cloud",
                "platform_code": platform.code,
                "job_id": str(job_id),
                "submitted_at": submitted_at,
                "submit_status": status,
                "submit_message": str(message),
                "shots": shots,
                "circuit_sha256": sha256_text(executed_qasm),
                "completed": False,
            }
            write_json(args.state_file, state)

        job_id = str(state["job_id"])
        run_dir = args.state_file.parent / "spinq" / job_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "source.qasm").write_text(source_qasm, encoding="utf-8")
        (run_dir / "transpiled.qasm").write_text(transpiled_qasm, encoding="utf-8")
        (run_dir / "executed.qasm").write_text(executed_qasm, encoding="utf-8")

        task_response = backend._api_client.get_task_by_code(job_id)
        task_raw = bytes(task_response.content)
        (run_dir / "task-raw.json").write_bytes(task_raw)
        task_payload = json.loads(task_raw.decode("utf-8"))

        deadline = time.monotonic() + args.timeout_seconds
        result_response = None
        result_payload = None
        while time.monotonic() < deadline:
            response = backend._api_client.task_result(job_id)
            (run_dir / "latest-result-response.json").write_bytes(bytes(response.content))
            if response.status_code == 412:
                time.sleep(args.poll_seconds)
                continue
            if response.status_code not in (200, 202):
                raise RuntimeError(f"SpinQ result query failed with HTTP {response.status_code}")
            payload = json.loads(response.content)
            if payload.get("taskStatus") == "F":
                raise RuntimeError("SpinQ real-hardware task failed")
            run = payload.get("run")
            if isinstance(run, dict) and (run.get("count") or run.get("module")):
                result_response = response
                result_payload = payload
                break
            time.sleep(args.poll_seconds)
        if result_response is None or result_payload is None:
            raise TimeoutError("SpinQ task did not finish before the local timeout")

        raw_result = bytes(result_response.content)
        (run_dir / "result-raw.json").write_bytes(raw_result)
        counts = extract_spinq_counts(
            result_payload, shots=shots, width=program.classical_register.size
        )
        dominant = top_k_states(counts, 2)
        top_k_match = set(dominant) == {"00", "11"}
        timestamp = get_task_timestamp(task_payload, str(state["submitted_at"]))
        normalized = {
            "platform": "SpinQ Cloud",
            "backend": platform.code,
            "job_id": job_id,
            "timestamp": timestamp,
            "task_status": (
                task_payload.get("task", {}).get("tstatus")
                if isinstance(task_payload.get("task"), dict)
                else None
            ),
            "start_time": (
                task_payload.get("task", {}).get("startTime")
                if isinstance(task_payload.get("task"), dict)
                else None
            ),
            "end_time": (
                task_payload.get("task", {}).get("endTime")
                if isinstance(task_payload.get("task"), dict)
                else None
            ),
            "shots": shots,
            "counts": counts,
            "counts_source": (
                "platform_raw_counts"
                if isinstance(result_payload.get("run", {}).get("count"), dict)
                else "derived_from_raw_probabilities_using_shots"
            ),
            "bit_order": "little",
            "circuit": "starter_kit/evidence/files/spinq-bell-executed.qasm",
            "raw_result": "starter_kit/evidence/files/spinq-bell-raw-result.json",
            "top_k_states": dominant,
            "expected_top_k_states": ["00", "11"],
            "top_k_match": top_k_match,
            "source": "adapter.transpile(qasm, 'spinq') plus SpinQ automatic measurement",
            "executed_qasm_sha256": sha256_text(executed_qasm),
            "raw_result_sha256": sha256_text(raw_result.decode("utf-8")),
        }
        write_json(run_dir / "result-normalized.json", normalized)

        publication_text = "\n".join(
            (
                executed_qasm,
                raw_result.decode("utf-8"),
                json.dumps(normalized, ensure_ascii=False, sort_keys=True),
            )
        )
        assert_no_secret_values(publication_text, config, preflight.SECRET_CONFIG)
        evidence_dir = STARTER_KIT / "evidence" / "files"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "spinq-bell-executed.qasm").write_text(
            executed_qasm, encoding="utf-8"
        )
        (evidence_dir / "spinq-bell-raw-result.json").write_bytes(raw_result)
        write_json(evidence_dir / "spinq-bell-result.json", normalized)

        state.update(
            {
                "completed": True,
                "completed_at": utc_now(),
                "timestamp": timestamp,
                "counts": counts,
                "top_k_states": dominant,
                "top_k_match": top_k_match,
                "local_run_dir": str(run_dir.relative_to(REPOSITORY)),
                "evidence_ready": True,
            }
        )
        write_json(args.state_file, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0 if top_k_match else 2
    except Exception as exc:
        message = redact_text(str(exc), config, preflight.SECRET_CONFIG)
        print(f"SpinQ submission failed: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
