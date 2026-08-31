"""SpinQ 真机 Web API 的独立服务层。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from scripts import submit_spinq_cloud


_TASK_ID = re.compile(r"^[A-Za-z0-9._-]+$")
# Learn 中的临时体验记录不能混入比赛提交使用的 evidence/files。
RUNTIME_OUTPUT = Path(__file__).resolve().parents[1] / "runtime" / "real-hardware"
STARTER_KIT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_SCRIPT = STARTER_KIT_ROOT / "scripts" / "submit_spinq_cloud.py"


class RealHardwareNotConfigured(RuntimeError):
    """表示真机凭据或真机后端尚未配置。"""


class RealHardwareOperationError(RuntimeError):
    """表示已配置真机，但本次云端操作没有完成。"""


def _backend() -> str:
    """默认使用已确认在线的 Gemini NMR 真机，也允许环境覆盖。"""
    backend = os.environ.get("SPINQ_BACKEND", "gemini_vp").strip()
    if not backend:
        raise RealHardwareNotConfigured("SpinQ real-hardware backend is not configured")
    return backend


def _cloud_python() -> Path:
    """返回隔离的 SpinQ Cloud SDK 解释器，防止与 Braket 的 ANTLR 冲突。"""
    configured = os.environ.get("LOOMQ_SPINQ_CLOUD_PYTHON")
    path = Path(configured) if configured else Path(sys.executable)
    if not path.is_file():
        raise RealHardwareNotConfigured("SpinQ Cloud Python is not configured")
    return path


def _configured() -> tuple[bool, str]:
    """只检查凭据存在性和私钥文件，不发出网络请求。"""
    try:
        submit_spinq_cloud._environment()
        _backend()
        _cloud_python()
    except submit_spinq_cloud.SpinQCloudError:
        return False, "真实量子设备未配置"
    except RealHardwareNotConfigured:
        return False, "真实量子设备未配置"
    return True, ""


def capability_status() -> dict[str, Any]:
    """返回不含账号、私钥路径或令牌的能力状态。"""
    available, reason = _configured()
    return {"spinq": {"available": available, "reason": reason}}


def _require_configured() -> str:
    available, _reason = _configured()
    if not available:
        raise RealHardwareNotConfigured("SpinQ real hardware is not configured")
    return _backend()


def _run_cloud_worker(action: str, output_dir: Path, *arguments: str) -> dict[str, Any]:
    """在隔离 SDK 环境中运行既有脚本，并只接收其结构化安全输出。"""
    command = [
        str(_cloud_python()), str(CLOUD_SCRIPT), "--web-action", action,
        "--output-dir", str(output_dir), *arguments,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=STARTER_KIT_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RealHardwareOperationError("SpinQ Cloud worker did not complete") from exc
    if completed.returncode != 0:
        raise RealHardwareOperationError("SpinQ Cloud worker did not complete")
    # 官方 SDK 在创建任务时可能向 stdout 写入提示；脚本最后一行始终是本服务要求的 JSON。
    for line in reversed(completed.stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise RealHardwareOperationError("SpinQ Cloud worker returned invalid data")


def submit_bell(output_dir: Path = RUNTIME_OUTPUT) -> dict[str, str]:
    """提交固定 Bell 电路并立即返回云端任务 ID，不在 HTTP 请求内轮询。"""
    backend = _require_configured()
    try:
        value = _run_cloud_worker(
            "submit", output_dir, "--input", str(submit_spinq_cloud.DEFAULT_INPUT),
            "--backend", backend, "--shots", "1000",
        )
        job_id = value.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise RealHardwareOperationError("SpinQ Cloud worker returned no job identifier")
    except (submit_spinq_cloud.SpinQCloudError, RealHardwareOperationError) as exc:
        raise RealHardwareOperationError("SpinQ Cloud submit failed") from exc
    return {"job_id": job_id, "status": "submitted", "platform": "spinq"}


def get_job(job_id: str, output_dir: Path = RUNTIME_OUTPUT) -> dict[str, Any]:
    """查询单个 SpinQ 任务；完成时复用 evidence 落盘逻辑保存结果。"""
    if not isinstance(job_id, str) or not _TASK_ID.fullmatch(job_id):
        raise RealHardwareOperationError("invalid SpinQ task identifier")
    _require_configured()
    try:
        value = _run_cloud_worker("query", output_dir, "--job-id", job_id)
        status = value.get("status")
        result = value.get("result")
        if status not in {"running", "completed", "failed"} or not isinstance(result, dict):
            raise RealHardwareOperationError("SpinQ Cloud worker returned invalid task status")
    except (submit_spinq_cloud.SpinQCloudError, RealHardwareOperationError) as exc:
        raise RealHardwareOperationError("SpinQ Cloud status query failed") from exc
    return {"job_id": job_id, "status": status, "result": result}


__all__ = [
    "RealHardwareNotConfigured",
    "RealHardwareOperationError",
    "RUNTIME_OUTPUT",
    "capability_status",
    "get_job",
    "submit_bell",
]
