#!/usr/bin/env python3
"""提交 OriginQ 真机任务并保存 L1 证据。

默认仅执行不联网的 dry-run。真实提交必须显式指定 ``--submit``，且 Token
只从 ORIGINQ_API_TOKEN 环境变量读取，绝不会写入标准输出或证据文件。
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any, Mapping, Sequence


STARTER_KIT_ROOT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT_ROOT))

import adapter  # noqa: E402  # 脚本必须复用官方入口的转译链路。


DEFAULT_INPUT = STARTER_KIT_ROOT / "circuits" / "bell.qasm"
DEFAULT_OUTPUT_DIRECTORY = STARTER_KIT_ROOT / "evidence" / "files"
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class OriginQEvidenceError(RuntimeError):
    """表示证据提交或保存无法安全完成。"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_sdk() -> Any:
    try:
        sdk = importlib.import_module("pyqpanda")
    except (ImportError, ModuleNotFoundError) as exc:
        raise OriginQEvidenceError(
            "pyqpanda SDK is unavailable; install requirements-originq.txt first"
        ) from exc
    required = ("CPUQVM", "convert_originir_to_qprog")
    missing = [name for name in required if not hasattr(sdk, name)]
    if missing:
        raise OriginQEvidenceError("pyqpanda SDK lacks required OriginQ cloud APIs")
    cloud_client = _cloud_client_type(sdk)
    cloud_methods = (
        "init_qvm",
        "async_batch_real_chip_measure",
        "finalize",
    )
    missing_methods = [
        name for name in cloud_methods if not hasattr(cloud_client, name)
    ]
    has_batch_query = any(
        hasattr(cloud_client, name)
        for name in ("query_batch_task_state_result", "query_batch_state_result")
    )
    if missing_methods or not has_batch_query:
        raise OriginQEvidenceError("pyqpanda SDK lacks required cloud task methods")
    return sdk


def _cloud_client_type(sdk: Any) -> Any:
    """适配 pyQPanda 3.8.5 的 QCloud 与旧文档中的 QCloudMachine 名称。"""
    for name in ("QCloud", "QCloudMachine"):
        candidate = getattr(sdk, name, None)
        if candidate is not None and hasattr(candidate, "init_qvm"):
            return candidate
    raise OriginQEvidenceError("pyqpanda SDK lacks a usable cloud client")


def _convert_originir(sdk: Any, originir: str) -> Any:
    """本地转换 OriginIR，dry-run 不初始化或访问量子云。"""
    machine = sdk.CPUQVM()
    initialized = False
    try:
        machine.init_qvm()
        initialized = True
        return _convert_originir_on_machine(sdk, originir, machine)
    finally:
        if initialized:
            machine.finalize()


def _convert_originir_on_machine(sdk: Any, originir: str, machine: Any) -> Any:
    """在目标 QVM 存活期间转换，避免跨 QVM 传递原生 QProg。"""
    with tempfile.TemporaryDirectory(prefix="loomq-originq-") as directory:
        temporary_path = Path(directory) / "program.originir"
        temporary_path.write_text(originir, encoding="utf-8")
        converted = sdk.convert_originir_to_qprog(str(temporary_path), machine)
    if not isinstance(converted, (tuple, list)) or len(converted) != 3:
        raise OriginQEvidenceError("OriginIR conversion returned an unexpected value")
    return converted[0]


def validate_dry_run(qasm_path: Path) -> tuple[Any, str]:
    """检查 Token、SDK 与 OriginIR→QProg 转换，绝不提交网络任务。"""
    token = os.environ.get("ORIGINQ_API_TOKEN")
    if not token or not token.strip():
        raise OriginQEvidenceError("ORIGINQ_API_TOKEN is not set")
    try:
        qasm = qasm_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OriginQEvidenceError("unable to read input QASM") from exc
    originir = adapter.transpile(qasm, "originq")
    qprog = _convert_originir(_load_sdk(), originir)
    return qprog, originir


def _resolve_chip(sdk: Any, name: str) -> Any:
    """兼容 pyQPanda 导出的 RealChipType 枚举命名。"""
    enum = getattr(sdk, "RealChipType", None) or getattr(sdk, "real_chip_type", None)
    if enum is None:
        return name
    normalized = name.lower()
    for candidate in (name, normalized, name.upper()):
        if hasattr(enum, candidate):
            return getattr(enum, candidate)
    raise OriginQEvidenceError("requested OriginQ real-chip backend is unavailable")


def _json_value(value: Any) -> Any:
    """将 SDK 容器转成 JSON，不修改其中的测量概率数值。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise OriginQEvidenceError("SDK result is not safely JSON serializable")


def _safe_job_id(task_id: str) -> str:
    safe = _SAFE_FILENAME.sub("_", task_id).strip("._")
    if not safe:
        raise OriginQEvidenceError("SDK returned an unsafe task identifier")
    return safe


def _write_evidence(
    *,
    output_directory: Path,
    job_id: str,
    qasm: str,
    originir: str,
    raw_result: Any,
    backend: str,
    submitted_at: str,
    shots: int,
) -> None:
    """保存输入、实际 OriginIR、原始返回值及可追溯元数据。"""
    output_directory.mkdir(parents=True, exist_ok=True)
    stem = _safe_job_id(job_id)
    input_file = output_directory / (stem + "-input.qasm")
    originir_file = output_directory / (stem + "-submitted.originir")
    raw_result_file = output_directory / (stem + "-raw-result.json")
    metadata_file = output_directory / (stem + "-metadata.json")

    # 先保存平台返回的未归一化数据，再写引用它的元数据。
    input_file.write_text(qasm, encoding="utf-8")
    originir_file.write_text(originir, encoding="utf-8")
    raw_result_file.write_text(
        json.dumps(_json_value(raw_result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    metadata = {
        "platform": "Origin Quantum Cloud",
        "backend": backend,
        "job_id": job_id,
        "submitted_at": submitted_at,
        "shots": shots,
        "input_file": str(input_file.relative_to(STARTER_KIT_ROOT.parent)),
        "originir_file": str(originir_file.relative_to(STARTER_KIT_ROOT.parent)),
        "raw_result_file": str(raw_result_file.relative_to(STARTER_KIT_ROOT.parent)),
    }
    metadata_file.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write_submission_record(
    *, output_directory: Path, job_id: str, qasm: str, originir: str,
    backend: str, submitted_at: str, shots: int,
) -> None:
    """任务已受理即保存 ID，避免轮询阶段异常丢失控制台追溯线索。"""
    output_directory.mkdir(parents=True, exist_ok=True)
    stem = _safe_job_id(job_id)
    input_file = output_directory / (stem + "-input.qasm")
    originir_file = output_directory / (stem + "-submitted.originir")
    record_file = output_directory / (stem + "-submission.json")
    input_file.write_text(qasm, encoding="utf-8")
    originir_file.write_text(originir, encoding="utf-8")
    record_file.write_text(
        json.dumps(
            {
                "platform": "Origin Quantum Cloud",
                "backend": backend,
                "job_id": job_id,
                "submitted_at": submitted_at,
                "shots": shots,
                "status": "submitted",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def submit_real_chip(
    *, qasm: str, originir: str, backend: str, shots: int,
    output_directory: Path, poll_interval: float, timeout: float,
) -> None:
    """显式提交单元素批任务，以获得可在控制台追溯的 task ID。"""
    token = os.environ["ORIGINQ_API_TOKEN"]
    sdk = _load_sdk()
    machine = _cloud_client_type(sdk)()
    initialized = False
    try:
        machine.init_qvm(token)
        initialized = True
        # QProg 必须在提交用 QCloud 存活期间构造；不能复用 dry-run 的 CPUQVM 对象。
        qprog = _convert_originir_on_machine(sdk, originir, machine)
        submitted_at = _utc_now()
        chip = _resolve_chip(sdk, backend)
        task_id = str(
            machine.async_batch_real_chip_measure([qprog], shots, chip)
        )
        _write_submission_record(
            output_directory=output_directory,
            job_id=task_id,
            qasm=qasm,
            originir=originir,
            backend=backend,
            submitted_at=submitted_at,
            shots=shots,
        )
        deadline = time.monotonic() + timeout
        result: Any = []
        while not result:
            if time.monotonic() >= deadline:
                raise OriginQEvidenceError("OriginQ cloud task timed out while polling")
            time.sleep(poll_interval)
            query = getattr(machine, "query_batch_task_state_result", None)
            if query is None:
                query = machine.query_batch_state_result
            result = query(task_id)
        _write_evidence(
            output_directory=output_directory,
            job_id=task_id,
            qasm=qasm,
            originir=originir,
            raw_result=result,
            backend=backend,
            submitted_at=submitted_at,
            shots=shots,
        )
    finally:
        if initialized:
            machine.finalize()


def _parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--backend", default="ORIGIN_72")
    parser.add_argument("--shots", type=int, default=1000)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=7200.0)
    parser.add_argument(
        "--submit", action="store_true", help="explicitly submit a real cloud task"
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_arguments(argv)
    if args.shots <= 0 or args.poll_interval <= 0 or args.timeout <= 0:
        raise OriginQEvidenceError("shots, poll interval and timeout must be positive")
    _qprog, originir = validate_dry_run(args.input)
    if not args.submit:
        return 0
    qasm = args.input.read_text(encoding="utf-8")
    submit_real_chip(
        qasm=qasm,
        originir=originir,
        backend=args.backend,
        shots=args.shots,
        output_directory=args.output_dir,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OriginQEvidenceError as exc:
        # 错误消息不包含 Token 或 SDK 原始异常，以避免终端意外泄密。
        raise SystemExit("OriginQ evidence operation failed: %s" % exc) from None
