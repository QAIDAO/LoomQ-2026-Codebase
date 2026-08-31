#!/usr/bin/env python3
"""Submit and preserve a traceable, explicitly confirmed AWS Braket QPU Bell task."""

from __future__ import annotations

import argparse
import os
import time
from typing import Any

from starter_kit.hardware.common import (
    BELL_QASM3, json_safe, normalize_distribution, normalized_result,
    package_version, save_completed_evidence, utc_now,
)


def configuration() -> dict[str, Any]:
    estimate = os.environ.get("LOOMQ_BRAKET_MAX_ESTIMATED_USD")
    return {
        "device_arn": os.environ.get("LOOMQ_BRAKET_DEVICE_ARN", ""),
        "region": os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-1",
        "s3_bucket": os.environ.get("LOOMQ_BRAKET_S3_BUCKET", ""),
        "s3_prefix": os.environ.get("LOOMQ_BRAKET_S3_PREFIX", "loomq-2026-hardware"),
        "max_estimated_usd": float(estimate) if estimate else None,
    }


def _session(region: str):
    import boto3
    from braket.aws import AwsSession
    return boto3.Session(region_name=region), AwsSession(boto_session=boto3.Session(region_name=region))


def _gate_qpu(device: object) -> bool:
    arn = str(getattr(device, "arn", ""))
    if "/device/qpu/" not in arn:
        return False
    properties = getattr(device, "properties", None)
    action = getattr(properties, "action", {}) if properties is not None else {}
    return any("openqasm" in str(key).lower() or "jaqcd" in str(key).lower() for key in action)


def resolve_device(config: dict[str, Any]):
    from braket.aws import AwsDevice, AwsDeviceType
    boto_session, aws_session = _session(config["region"])
    if boto_session.get_credentials() is None:
        raise RuntimeError("AWS standard credential chain is not configured")
    if config["device_arn"]:
        device = AwsDevice(config["device_arn"], aws_session=aws_session)
        if not _gate_qpu(device):
            raise RuntimeError("LOOMQ_BRAKET_DEVICE_ARN is not a gate-based QPU")
        return device
    devices = AwsDevice.get_devices(
        types=[AwsDeviceType.QPU], statuses=["ONLINE"], aws_session=aws_session,
    )
    candidates = sorted((device for device in devices if _gate_qpu(device)), key=lambda item: item.arn)
    if not candidates:
        raise RuntimeError("no online gate-based Braket QPU was discovered")
    return candidates[0]


def doctor() -> int:
    config = configuration()
    print(f"amazon-braket-sdk={package_version('amazon-braket-sdk')}")
    print(f"region={config['region']}")
    print(f"s3_bucket_configured={str(bool(config['s3_bucket'])).lower()}")
    try:
        device = resolve_device(config)
    except Exception as exc:
        print(f"ready=false\nreason={type(exc).__name__}: {exc}")
        return 2
    print(f"ready=true\ndevice_arn={device.arn}\ndevice_name={device.name}\nstatus={device.status}")
    return 0


def submit(*, shots: int, timeout: int, poll_interval: int, confirm: bool, max_estimated_usd: float | None) -> dict[str, str]:
    config = configuration()
    if not confirm:
        raise RuntimeError("paid QPU submission requires --confirm-paid-hardware")
    if max_estimated_usd is None or max_estimated_usd <= 0:
        raise RuntimeError("set --max-estimated-usd or LOOMQ_BRAKET_MAX_ESTIMATED_USD before paid submission")
    if not config["s3_bucket"]:
        raise RuntimeError("LOOMQ_BRAKET_S3_BUCKET is required")
    from braket.ir.openqasm import Program

    device = resolve_device(config)
    print(f"device={device.name}\ndevice_arn={device.arn}\nregion={config['region']}\nshots={shots}\nmaximum_estimated_usd={max_estimated_usd:.2f}")
    submitted_at = utc_now()
    task = device.run(
        Program(source=BELL_QASM3),
        (config["s3_bucket"], config["s3_prefix"]),
        shots=shots,
        poll_timeout_seconds=timeout,
        poll_interval_seconds=poll_interval,
    )
    task_arn = str(task.id)
    if not task_arn or ":quantum-task/" not in task_arn:
        raise RuntimeError("AWS Braket returned no traceable quantum task ARN")
    print(f"task_arn={task_arn}")
    deadline = time.monotonic() + timeout
    terminal = {"COMPLETED", "FAILED", "CANCELLED"}
    state = str(task.state())
    while state not in terminal and time.monotonic() < deadline:
        time.sleep(poll_interval)
        state = str(task.state())
    if state != "COMPLETED":
        raise RuntimeError(f"Braket task ended in state {state}: {task_arn}")
    result_object = task.result()
    raw_counts = dict(result_object.measurement_counts)
    counts, source_kind = normalize_distribution(raw_counts, shots)
    completed_at = utc_now()
    result = normalized_result(
        provider="braket", backend="braket_real_qpu", job_id=task_arn, shots=shots,
        counts=counts, submitted_at=submitted_at, completed_at=completed_at,
        device=f"{device.name} ({device.arn})", source_kind=source_kind,
    )
    return save_completed_evidence(
        provider="braket", qasm=BELL_QASM3,
        raw={"task_arn": task_arn, "task_metadata": json_safe(task.metadata()), "measurement_counts": raw_counts},
        result=result,
        metadata={
            "provider": "braket", "platform": "AWS Braket", "device": device.name,
            "device_arn": device.arn, "region": config["region"], "job_id": task_arn,
            "shots": shots, "submitted_at": submitted_at, "completed_at": completed_at,
            "maximum_estimated_usd": max_estimated_usd,
            "sdk_versions": {"amazon-braket-sdk": package_version("amazon-braket-sdk")},
            "command": "python -m starter_kit.hardware.braket_qpu --confirm-paid-hardware --max-estimated-usd <CAP>",
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="AWS Braket real-QPU Bell evidence runner")
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-paid-hardware", action="store_true")
    parser.add_argument("--max-estimated-usd", type=float)
    parser.add_argument("--shots", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--poll-interval", type=int, default=15)
    args = parser.parse_args()
    if args.doctor:
        return doctor()
    if args.shots <= 0 or args.timeout <= 0 or args.poll_interval <= 0:
        raise SystemExit("shots, timeout, and poll interval must be positive")
    config = configuration()
    estimate = args.max_estimated_usd if args.max_estimated_usd is not None else config["max_estimated_usd"]
    if args.dry_run:
        print(f"provider=braket\nregion={config['region']}\ndevice_arn={config['device_arn'] or '<auto-discover>'}\nshots={args.shots}\nmaximum_estimated_usd={estimate if estimate is not None else '<required-before-submit>'}\nwill_submit=false")
        return 0
    paths = submit(
        shots=args.shots, timeout=args.timeout, poll_interval=args.poll_interval,
        confirm=args.confirm_paid_hardware, max_estimated_usd=estimate,
    )
    for name, path in paths.items():
        print(f"{name}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
