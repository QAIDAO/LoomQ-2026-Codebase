#!/usr/bin/env python3
"""使用 pyqpanda3 向 OriginQ WK_C180 提交 L1 真机证据任务。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Sequence


STARTER_KIT_ROOT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT_ROOT))

import adapter  # noqa: E402  # 复用正式 Parser 与 OriginIR Serializer。


DEFAULT_INPUT = STARTER_KIT_ROOT / "circuits" / "bell.qasm"
DEFAULT_OUTPUT = STARTER_KIT_ROOT / "evidence" / "files"
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class OriginQCloudV3Error(RuntimeError):
    """表示云端证据操作无法安全完成。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_sdk() -> tuple[Any, Any, Any, Any]:
    try:
        from pyqpanda3.intermediate_compiler import convert_originir_string_to_qprog
        from pyqpanda3.qcloud import JobStatus, QCloudOptions, QCloudService
    except (ImportError, ModuleNotFoundError) as exc:
        raise OriginQCloudV3Error(
            "pyqpanda3 is unavailable; install requirements-originq-cloud.txt"
        ) from exc
    return convert_originir_string_to_qprog, QCloudService, QCloudOptions, JobStatus


def _read_and_convert(input_path: Path) -> tuple[str, str, Any]:
    try:
        qasm = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OriginQCloudV3Error("unable to read input QASM") from exc
    originir = adapter.transpile(qasm, "originq")
    converter, _service, _options, _status = _load_sdk()
    try:
        qprog = converter(originir)
    except Exception as exc:
        raise OriginQCloudV3Error("pyqpanda3 cannot convert generated OriginIR") from exc
    return qasm, originir, qprog


def _token() -> str:
    value = os.environ.get("ORIGINQ_API_TOKEN")
    if not value or not value.strip():
        raise OriginQCloudV3Error("ORIGINQ_API_TOKEN is not set")
    return value


def dry_run(input_path: Path) -> tuple[str, str, Any]:
    """仅校验 Token、SDK 与 OriginIR 转换；不创建云端任务。"""
    _token()
    return _read_and_convert(input_path)


def _job_id(job: Any) -> str:
    for name in ("id", "job_id", "task_id"):
        value = getattr(job, name, None)
        # pyqpanda3 的 QCloudJob 将 job_id 暴露为零参数方法。
        if callable(value):
            value = value()
        if isinstance(value, str) and value:
            return value
    raise OriginQCloudV3Error("cloud SDK returned no job identifier")


def _safe_stem(job_id: str) -> str:
    value = _SAFE_FILENAME.sub("_", job_id).strip("._")
    if not value:
        raise OriginQCloudV3Error("cloud SDK returned an unsafe job identifier")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _paths(output: Path, job_id: str) -> tuple[Path, Path, Path, Path, Path]:
    stem = _safe_stem(job_id)
    return (
        output / (stem + "-input.qasm"),
        output / (stem + "-submitted.originir"),
        output / (stem + "-submission.json"),
        output / (stem + "-raw-result.json"),
        output / (stem + "-metadata.json"),
    )


def _record_submission(
    output: Path, job_id: str, qasm: str, originir: str, backend: str,
    submitted_at: str, shots: int,
) -> None:
    """先保存 job ID，防止轮询过程被中断时失去可追溯性。"""
    output.mkdir(parents=True, exist_ok=True)
    input_file, originir_file, record_file, _raw_file, _metadata_file = _paths(output, job_id)
    input_file.write_text(qasm, encoding="utf-8")
    originir_file.write_text(originir, encoding="utf-8")
    _write_json(record_file, {
        "platform": "Origin Quantum Cloud", "backend": backend, "job_id": job_id,
        "submitted_at": submitted_at, "shots": shots, "status": "submitted",
    })


def _record_result(
    output: Path, job_id: str, backend: str, submitted_at: str, shots: int,
    raw_result: Any,
) -> None:
    input_file, originir_file, _record_file, raw_file, metadata_file = _paths(output, job_id)
    _write_json(raw_file, raw_result)
    _write_json(metadata_file, {
        "platform": "Origin Quantum Cloud", "backend": backend, "job_id": job_id,
        "submitted_at": submitted_at, "shots": shots,
        "input_file": str(input_file.relative_to(STARTER_KIT_ROOT.parent)),
        "originir_file": str(originir_file.relative_to(STARTER_KIT_ROOT.parent)),
        "raw_result_file": str(raw_file.relative_to(STARTER_KIT_ROOT.parent)),
    })


def submit(
    qasm: str, originir: str, qprog: Any, output: Path, backend_name: str,
    shots: int, poll_interval: float, timeout: float,
) -> None:
    _converter, Service, Options, Finished = _load_sdk()
    service = Service(api_key=_token())
    backend = service.backend(backend_name)
    options = Options()
    # 明确沿用比赛证据所需的映射、优化与读出修正设置。
    options.set_amend(True)
    options.set_mapping(True)
    options.set_optimization(True)
    submitted_at = _now()
    job = backend.run([qprog], shots, options)
    job_id = _job_id(job)
    _record_submission(output, job_id, qasm, originir, backend_name, submitted_at, shots)
    deadline = time.monotonic() + timeout
    while True:
        status = job.status()
        if status == Finished.FINISHED or str(status).upper().endswith("FINISHED"):
            break
        if time.monotonic() >= deadline:
            raise OriginQCloudV3Error("cloud task timed out while polling")
        time.sleep(poll_interval)
    result = job.result()
    probs = result.get_probs_list()
    _record_result(output, job_id, backend_name, submitted_at, shots, {
        "job_id": job_id, "backend": backend_name, "probabilities": probs,
    })


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--backend", default="WK_C180")
    parser.add_argument("--shots", type=int, default=1000)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=7200.0)
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args(argv)
    if args.shots <= 0 or args.poll_interval <= 0 or args.timeout <= 0:
        raise OriginQCloudV3Error("shots, poll interval and timeout must be positive")
    qasm, originir, qprog = dry_run(args.input)
    if args.submit:
        submit(qasm, originir, qprog, args.output_dir, args.backend, args.shots,
               args.poll_interval, args.timeout)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OriginQCloudV3Error as exc:
        raise SystemExit("OriginQ v3 evidence operation failed: %s" % exc) from None
