"""SpinQ Cloud adapter.

SpinQ's public cloud submitter is distributed as ``spinqit_mcp_tools``.  The
package exposes Python functions as well as an MCP stdio server; calling the
functions directly keeps this adapter usable from the LoomQ CLI while using
the same official authentication and task APIs.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import time
from typing import Any, Dict

from .common import (
    HardwareInterfaceError,
    extract_counts,
    extract_job_id,
    measured_width,
    normalize_counts,
    positive_shots,
    required_env,
    standard_result,
)


def _load_submitter() -> Any:
    try:
        return importlib.import_module("spinqit_mcp_tools.qasm_submitter")
    except ImportError as exc:
        raise HardwareInterfaceError(
            "SpinQ remote support requires spinqit-mcp-tools; "
            "install starter_kit/requirements-hardware.txt"
        ) from exc


def _decode_json(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _remove_measurements(qasm_str: str) -> str:
    # SpinQ's official QASM submitter builds the measurement layer itself and
    # explicitly rejects a QASM string containing the word "measure".
    cleaned = re.sub(
        r"(?im)^\s*measure\b[^;]*;\s*$",
        "",
        qasm_str,
    )
    if re.search(r"(?i)\bmeasure\b", cleaned):
        raise HardwareInterfaceError(
            "SpinQ cloud submission accepts gate QASM only; "
            "remove measurement text from comments or declarations"
        )
    return cleaned


def _job_id_from_submission(payload: Any) -> str | None:
    decoded = _decode_json(payload)
    found = extract_job_id(decoded)
    if found:
        return found
    if isinstance(decoded, str) and decoded.strip():
        # Some releases return the raw task identifier instead of a JSON
        # object.  Do not treat arbitrary JSON text as an identifier.
        if " " not in decoded.strip() and "{" not in decoded:
            return decoded.strip()
    return None


def run_spinq_cloud(
    qasm_str: str,
    shots: int,
    *,
    task_name: str = "LoomQ experiment",
    require_qpu: bool = False,
) -> Dict[str, Any]:
    """Submit to SpinQ Cloud and wait for the provider result.

    The official SpinQ submitter currently fixes the shot count at 1000, so
    this adapter refuses to label another requested value as the actual shot
    count.
    """

    positive_shots(shots)
    if shots != 1000:
        raise HardwareInterfaceError(
            "SpinQ's official qasm_submitter currently uses shots=1000; "
            "call this adapter with --shots 1000"
        )

    required_env("PRIVATEKEYPATH")
    required_env("SPINQCLOUDUSERNAME")
    host = os.environ.get("SPINQCLOUDHOST", "http://cloud.spinq.cn:6060").strip()
    platform_code = os.environ.get("LOOMQ_SPINQ_PLATFORM", "simulator").strip()
    if not platform_code:
        raise HardwareInterfaceError("LOOMQ_SPINQ_PLATFORM cannot be empty")
    if require_qpu and platform_code.lower() == "simulator":
        raise HardwareInterfaceError(
            "spinq_cloud_qpu requires LOOMQ_SPINQ_PLATFORM to be a real SpinQ "
            "Cloud platform code, not simulator"
        )

    submitter = _load_submitter()
    submit = getattr(submitter, "qasm_submit", None)
    get_result = getattr(submitter, "get_task_result_by_id", None)
    if not callable(submit) or not callable(get_result):
        raise HardwareInterfaceError(
            "installed spinqit_mcp_tools does not expose qasm_submit and "
            "get_task_result_by_id"
        )

    submission = _decode_json(
        submit(
            _remove_measurements(qasm_str),
            task_name,
            platform_code,
        )
    )
    task_id = _job_id_from_submission(submission)
    if not task_id:
        try:
            counts = extract_counts(submission)
        except HardwareInterfaceError as exc:
            raise HardwareInterfaceError(
                "SpinQ did not return a task ID or a measurement result"
            ) from exc
        result_payload = submission
    else:
        poll_timeout = float(os.environ.get("LOOMQ_SPINQ_POLL_TIMEOUT", "180"))
        poll_interval = float(os.environ.get("LOOMQ_SPINQ_POLL_INTERVAL", "2"))
        if poll_timeout <= 0 or poll_interval <= 0:
            raise HardwareInterfaceError(
                "LOOMQ_SPINQ_POLL_TIMEOUT and LOOMQ_SPINQ_POLL_INTERVAL must be positive"
            )

        deadline = time.monotonic() + poll_timeout
        last_error: HardwareInterfaceError | None = None
        while True:
            result_payload = _decode_json(get_result(task_id))
            try:
                counts = extract_counts(result_payload)
                break
            except HardwareInterfaceError as exc:
                last_error = exc
                if time.monotonic() >= deadline:
                    raise HardwareInterfaceError(
                        f"SpinQ task {task_id} did not return measurement counts before timeout"
                    ) from last_error
                time.sleep(poll_interval)

    # SpinQ returns one bit per allocated qubit.  LoomQ's standard result uses
    # the classical register width; public circuits measure all allocated bits.
    try:
        try:
            from ..l1.parser import parse_qasm2
        except ImportError:
            # Product Service may import adapter from inside starter_kit/.
            from l1.parser import parse_qasm2
        width = measured_width(parse_qasm2(qasm_str))
    except Exception:
        width = max(1, max((len(str(key)) for key in counts), default=1))

    normalized = normalize_counts(counts, width=width, shots=shots)
    if not task_id:
        task_id = extract_job_id(result_payload)
    if not task_id:
        raise HardwareInterfaceError(
            "SpinQ returned measurement counts without a traceable task ID"
        )
    return standard_result(
        backend=(
            "spinq_cloud_qpu"
            if platform_code != "simulator"
            else "spinq_cloud_simulator"
        ),
        job_id=task_id,
        shots=shots,
        counts=normalized,
        meta={
            "provider": "spinq",
            "platform_code": platform_code,
            "cloud_host": host,
            "job_id_traceable": bool(task_id),
        },
    )
