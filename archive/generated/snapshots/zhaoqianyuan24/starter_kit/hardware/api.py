"""Public dispatcher for optional SpinQ, OriginQ, and Braket remote runs."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .common import HardwareInterfaceError


def run_hardware(
    qasm_str: str,
    target: str,
    shots: int,
    *,
    task_name: str = "LoomQ experiment",
) -> Dict[str, Any]:
    """Submit one circuit to a remote provider and wait for its result.

    This is the provider layer behind ``adapter.run`` when the caller passes a
    canonical remote backend ID.  It requires provider credentials and may
    incur queue time or cloud charges; the public platform targets still keep
    their deterministic local L1 behavior.
    """

    normalized = str(target).strip().lower()
    if normalized in {"spinq", "spinq_cloud", "spinq_cloud_qpu"}:
        from .spinq import run_spinq_cloud

        return run_spinq_cloud(
            qasm_str,
            shots,
            task_name=task_name,
            require_qpu=normalized == "spinq_cloud_qpu",
        )
    if normalized in {"originq", "originq_wukong"}:
        from .originq import run_originq_wukong

        return run_originq_wukong(qasm_str, shots, task_name=task_name)
    if normalized in {"braket", "braket_cloud", "braket_qpu"}:
        from .braket import run_braket_cloud

        return run_braket_cloud(qasm_str, shots, task_name=task_name)
    raise HardwareInterfaceError(
        "unsupported hardware target; use spinq, originq, or braket"
    )


def list_spinq_platforms() -> Any:
    """Return the platform catalogue from the official SpinQ submitter."""

    try:
        from spinqit_mcp_tools.qasm_submitter import get_platforms
    except ImportError as exc:
        raise HardwareInterfaceError(
            "SpinQ remote support requires spinqit-mcp-tools; "
            "install starter_kit/requirements-hardware.txt"
        ) from exc
    if not callable(get_platforms):
        raise HardwareInterfaceError(
            "installed spinqit_mcp_tools does not expose get_platforms"
        )
    return get_platforms()
