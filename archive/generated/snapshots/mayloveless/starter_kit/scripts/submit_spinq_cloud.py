#!/usr/bin/env python3
"""使用 SpinQ 官方 Cloud 工具提交真实硬件任务并保存 L1 证据。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Mapping, Sequence


STARTER_KIT_ROOT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT_ROOT))

import adapter  # noqa: E402  # 复用 LoomQ 的标准转译入口。


DEFAULT_INPUT = STARTER_KIT_ROOT / "circuits" / "bell.qasm"
DEFAULT_OUTPUT = STARTER_KIT_ROOT / "evidence" / "files"
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class SpinQCloudError(RuntimeError):
    """表示 SpinQ Cloud 证据操作无法安全完成。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _environment() -> tuple[str, Path, str]:
    """读取官方 Cloud 工具使用的凭据环境变量，绝不返回私钥内容。"""
    # 保留原 CLI 变量，并接受 Web 服务更易读的同义变量名。
    username = os.environ.get("SPINQ_USERNAME") or os.environ.get("SPINQCLOUDUSERNAME")
    key_path = os.environ.get("SPINQ_KEY_PATH") or os.environ.get("PRIVATEKEYPATH")
    host = os.environ.get("SPINQCLOUDHOST", "http://cloud.spinq.cn:6060")
    if not username or not username.strip():
        raise SpinQCloudError("SPINQCLOUDUSERNAME is not set")
    if not key_path:
        raise SpinQCloudError("PRIVATEKEYPATH is not set")
    path = Path(key_path).expanduser()
    if not path.is_file():
        raise SpinQCloudError("PRIVATEKEYPATH does not identify a readable private-key file")
    if not host.startswith(("http://", "https://")):
        raise SpinQCloudError("SPINQCLOUDHOST must be an HTTP(S) URL")
    return username.strip(), path, host.rstrip("/")


def _load_cloud_sdk() -> dict[str, Any]:
    """延迟导入官方 spinqit_mcp_tools，避免影响本地 SpinQ Runner。"""
    try:
        from Crypto.Hash import SHA256
        from Crypto.PublicKey import RSA
        from Crypto.Signature import PKCS1_v1_5
        from spinqit_mcp_tools.backend import get_spinq_cloud
        from spinqit_mcp_tools.backend.client import spinq_cloud_client
        from spinqit_mcp_tools.backend.client.spinq_cloud_client import SpinQCloudClient
        from spinqit_mcp_tools.compiler import get_compiler
        from spinqit_mcp_tools.model.spinqCloud.circuit import graph_to_circuit
        from spinqit_mcp_tools.model.spinqCloud.task import Task
    except (ImportError, ModuleNotFoundError) as exc:
        raise SpinQCloudError(
            "SpinQ Cloud SDK is unavailable; install requirements-spinq-cloud.txt"
        ) from exc
    return {
        "SHA256": SHA256, "RSA": RSA, "Signature": PKCS1_v1_5,
        "get_spinq_cloud": get_spinq_cloud, "client_module": spinq_cloud_client,
        "Client": SpinQCloudClient, "get_compiler": get_compiler,
        "graph_to_circuit": graph_to_circuit, "Task": Task,
    }


def _sign_username(username: str, key_path: Path, sdk: Mapping[str, Any]) -> str:
    """按官方 MCP 工具的 RSA-SHA256 签名流程认证。"""
    try:
        private_key = key_path.read_text(encoding="utf-8")
        key = sdk["RSA"].import_key(private_key)
        digest = sdk["SHA256"].new(username.encode("utf-8"))
        signature = sdk["Signature"].new(key).sign(digest)
    except Exception as exc:
        raise SpinQCloudError("unable to sign SpinQ Cloud authentication request") from exc
    import base64
    return base64.b64encode(signature).decode("ascii")


def _remove_measurements(qasm: str) -> str:
    """官方 qasm_submit 接口不接受 measure；云端返回的是概率原始结果。"""
    statements = [item.strip() for item in qasm.split(";") if item.strip()]
    retained = [item for item in statements if not re.match(r"^measure\b", item, re.I)]
    if len(retained) == len(statements):
        raise SpinQCloudError("input circuit must contain final measurement statements")
    return ";\n".join(retained) + ";\n"


def _prepare(input_path: Path) -> tuple[str, str]:
    try:
        source = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpinQCloudError("unable to read input circuit") from exc
    # 公开 SpinQ target 仍为完整 OpenQASM 2.0；仅 Cloud API 副本去除 measure。
    transpiled = adapter.transpile(source, "spinq")
    return source, _remove_measurements(transpiled)


def _json_response(response: Any) -> dict[str, Any]:
    try:
        value = json.loads(response.content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SpinQCloudError("SpinQ Cloud returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise SpinQCloudError("SpinQ Cloud returned a non-object response")
    return value


def _task_code(value: Mapping[str, Any]) -> str:
    """兼容服务端将任务标识放在顶层或 data/result 容器中的响应。"""
    pending: list[Mapping[str, Any]] = [value]
    while pending:
        item = pending.pop()
        for key in ("taskCode", "tcode", "task_id", "taskId", "id"):
            candidate = item.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
        pending.extend(child for child in item.values() if isinstance(child, Mapping))
    raise SpinQCloudError("SpinQ Cloud accepted no recoverable task identifier")


def _task_status(value: Mapping[str, Any]) -> str:
    """兼容状态字段位于服务响应的 data 容器中。"""
    pending: list[Mapping[str, Any]] = [value]
    while pending:
        item = pending.pop()
        for key in ("taskStatus", "status"):
            candidate = item.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
        pending.extend(child for child in item.values() if isinstance(child, Mapping))
    return "UNKNOWN"


def _safe_stem(task_code: str) -> str:
    stem = _SAFE_FILENAME.sub("_", task_code).strip("._")
    if not stem:
        raise SpinQCloudError("SpinQ Cloud returned an unsafe task identifier")
    return stem


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _paths(output: Path, task_code: str) -> tuple[Path, Path, Path, Path, Path]:
    stem = _safe_stem(task_code)
    return (
        output / (stem + "-input.qasm"), output / (stem + "-submitted.qasm"),
        output / (stem + "-metadata.json"), output / (stem + "-raw-result.json"),
        output / (stem + "-parsed-result.json"),
    )


def _record_submission(
    output: Path, task_code: str, source: str, submitted: str, backend: str,
    submitted_at: str, shots: int, source_file: str,
) -> tuple[Path, Path, Path, Path, Path]:
    """取得 task ID 后立即保存输入与 metadata，防止轮询中断丢失证据。"""
    output.mkdir(parents=True, exist_ok=True)
    input_file, submitted_file, metadata_file, raw_file, parsed_file = _paths(output, task_code)
    input_file.write_text(source, encoding="utf-8")
    submitted_file.write_text(submitted, encoding="utf-8")
    _write_json(metadata_file, {
        "platform": "SpinQ Cloud", "backend": backend, "job_id": task_code,
        "submitted_at": submitted_at, "shots": shots, "source_file": source_file,
    })
    return input_file, submitted_file, metadata_file, raw_file, parsed_file


def _parse_result(raw: Mapping[str, Any]) -> dict[str, Any]:
    """保留原始响应，并仅提取平台返回的概率数组作为易读副本。"""
    payload = raw.get("data") if isinstance(raw.get("data"), Mapping) else raw
    run = payload.get("run")
    modules = run.get("module") if isinstance(run, Mapping) else None
    if not isinstance(modules, list):
        return {"raw_result": raw}
    width = max(1, math.ceil(math.log2(max(1, len(modules)))))
    return {"probabilities": {format(index, "0%db" % width): value
                               for index, value in enumerate(modules)}}


def dry_run(input_path: Path) -> tuple[str, str]:
    """检查凭据、官方 SDK 与 SpinQ 格式编译，绝不创建任务。"""
    username, key_path, _host = _environment()
    sdk = _load_cloud_sdk()
    _sign_username(username, key_path, sdk)
    source, submitted = _prepare(input_path)
    try:
        sdk["get_compiler"]("qasm").compile(submitted, 0)
    except Exception as exc:
        raise SpinQCloudError("SpinQ Cloud SDK cannot compile submitted QASM") from exc
    return source, submitted


def _authenticated_client() -> tuple[dict[str, Any], Any]:
    """创建已认证客户端；调用方只接收客户端对象，避免传播凭据。"""
    username, key_path, host = _environment()
    sdk = _load_cloud_sdk()
    # 官方客户端常量默认指向 Cloud；环境变量允许显式覆盖测试/正式域名。
    sdk["client_module"].HOST = host
    client = sdk["Client"](username, _sign_username(username, key_path, sdk))
    client.login()
    return sdk, client


def submit_task(
    source: str, submitted: str, backend: str, shots: int, output: Path,
    source_file: str,
) -> str:
    """创建任务并立即落盘提交证据，但不等待量子任务完成。"""
    sdk, client = _authenticated_client()
    executable = sdk["get_compiler"]("qasm").compile(submitted, 0)
    username, key_path, _host = _environment()
    cloud_backend = sdk["get_spinq_cloud"](username, str(key_path))
    platform = cloud_backend.get_platform(backend)
    mapping = {index: index for index in range(executable.qnum)}
    circuit = sdk["graph_to_circuit"](executable, mapping, platform, None, None)
    task = sdk["Task"](
        "LoomQ-L1-%s" % _now().replace(":", ""), backend, circuit, mapping,
        calc_matrix=False, shots=shots, process_now=True, description="LoomQ L1 evidence",
        api_client=client,
    )
    submitted_at = _now()
    create_raw = _json_response(client.create_task(task.to_request()))
    task_code = _task_code(create_raw)
    _record_submission(
        output, task_code, source, submitted, backend, submitted_at, shots, source_file
    )
    return task_code


def query_task(task_code: str, output: Path = DEFAULT_OUTPUT) -> tuple[str, dict[str, Any]]:
    """查询任务；完成时保存原始及解析后的结果文件。"""
    sdk, client = _authenticated_client()
    status_raw = _json_response(client.task_status(task_code))
    status = _task_status(status_raw).upper()
    if status in {"S", "SUCCESS", "SUCCEEDED", "FINISHED", "COMPLETED"}:
        raw = _json_response(client.task_result(task_code))
        _input, _submitted, _metadata, raw_file, parsed_file = _paths(output, task_code)
        output.mkdir(parents=True, exist_ok=True)
        _write_json(raw_file, raw)
        parsed = _parse_result(raw)
        _write_json(parsed_file, parsed)
        return "completed", parsed
    if status in {"F", "FAILED", "DELETED", "CANCELLED"}:
        return "failed", {}
    return "running", {}


def submit(
    source: str, submitted: str, backend: str, shots: int, output: Path,
    source_file: str, poll_interval: float, timeout: float,
) -> tuple[str, str, Path]:
    task_code = submit_task(source, submitted, backend, shots, output, source_file)
    deadline = time.monotonic() + timeout
    while True:
        status, _result = query_task(task_code, output)
        if status == "completed":
            return task_code, status, _paths(output, task_code)[4]
        if status == "failed":
            raise SpinQCloudError("SpinQ Cloud task completed without a successful result")
        if time.monotonic() >= deadline:
            raise SpinQCloudError("SpinQ Cloud task timed out while polling")
        time.sleep(poll_interval)


def list_platforms() -> dict[str, Any]:
    """登录后查询账号可见的平台；该操作不会创建量子任务。"""
    _sdk, client = _authenticated_client()
    return _json_response(client.retrieve_remote_platforms())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--backend", help="hardware platform code from SpinQ Cloud")
    parser.add_argument("--shots", type=int, default=1000)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=7200.0)
    parser.add_argument(
        "--web-action", choices=("submit", "query"), help=argparse.SUPPRESS,
    )
    parser.add_argument("--job-id", help=argparse.SUPPRESS)
    parser.add_argument(
        "--list-platforms", action="store_true",
        help="list account-visible SpinQ Cloud platforms without creating a task",
    )
    parser.add_argument("--submit", action="store_true", help="explicitly create a hardware task")
    args = parser.parse_args(argv)
    if args.shots <= 0 or args.poll_interval <= 0 or args.timeout <= 0:
        raise SpinQCloudError("shots, poll interval and timeout must be positive")
    # Web 服务通过专用 Cloud Python 调用本脚本，避免 Cloud SDK 污染 Braket 环境。
    if args.web_action == "query":
        if not args.job_id:
            raise SpinQCloudError("--job-id is required for query")
        status, result = query_task(args.job_id, args.output_dir)
        print(json.dumps({"status": status, "result": result}, ensure_ascii=False))
        return 0

    source, submitted = dry_run(args.input)
    if args.web_action == "submit":
        if not args.backend:
            raise SpinQCloudError("--backend is required for submit")
        try:
            source_file = str(args.input.resolve().relative_to(STARTER_KIT_ROOT.parent))
        except ValueError:
            source_file = str(args.input.resolve())
        task_code = submit_task(
            source, submitted, args.backend, args.shots, args.output_dir, source_file
        )
        print(json.dumps({"job_id": task_code}, ensure_ascii=False))
        return 0
    if args.list_platforms:
        if args.submit:
            raise SpinQCloudError("--list-platforms cannot be combined with --submit")
        print(json.dumps(list_platforms(), ensure_ascii=False, indent=2))
        return 0
    if not args.submit:
        print("status: DRY_RUN_OK")
        return 0
    if not args.backend:
        raise SpinQCloudError("--backend is required with --submit; obtain it from SpinQ Cloud")
    try:
        source_file = str(args.input.resolve().relative_to(STARTER_KIT_ROOT.parent))
    except ValueError:
        source_file = str(args.input.resolve())
    task_code, status, result_file = submit(
        source, submitted, args.backend, args.shots, args.output_dir, source_file,
        args.poll_interval, args.timeout,
    )
    print("job id: %s" % task_code)
    print("status: %s" % status)
    print("result file: %s" % result_file)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SpinQCloudError as exc:
        raise SystemExit("SpinQ Cloud evidence operation failed: %s" % exc) from None
