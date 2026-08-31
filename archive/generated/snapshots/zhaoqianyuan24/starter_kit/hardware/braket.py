"""Amazon Braket remote-device adapter."""

from __future__ import annotations

import os
from typing import Any, Dict, Tuple

from .common import (
    HardwareInterfaceError,
    measured_width,
    normalize_counts,
    positive_shots,
    required_env,
    standard_result,
)


def _s3_location() -> tuple[str, str]:
    uri = os.environ.get("LOOMQ_BRAKET_S3_URI", "").strip()
    if uri:
        if not uri.startswith("s3://") or "/" not in uri[5:]:
            raise HardwareInterfaceError(
                "LOOMQ_BRAKET_S3_URI must look like s3://bucket/prefix"
            )
        bucket, prefix = uri[5:].split("/", 1)
        if bucket and prefix:
            return bucket, prefix
    bucket = required_env("LOOMQ_BRAKET_S3_BUCKET")
    prefix = required_env("LOOMQ_BRAKET_S3_PREFIX")
    return bucket, prefix


def _normalize_measurements(result: Any, circuit: Any, shots: int) -> Dict[str, int]:
    measurements = getattr(result, "measurements", None)
    measured_qubits = getattr(result, "measured_qubits", None)
    if measurements is None or measured_qubits is None:
        raise HardwareInterfaceError(
            "Braket result does not contain measurements/measured_qubits"
        )

    measurement_ops = [
        operation
        for operation in circuit.operations
        if operation.__class__.__name__ == "Measurement"
    ]
    if not measurement_ops:
        raise HardwareInterfaceError("circuit contains no measurement operations")
    positions = {int(qubit): index for index, qubit in enumerate(measured_qubits)}
    raw_counts: Dict[str, int] = {}
    for row in measurements:
        bits = ["0"] * circuit.num_clbits
        for operation in measurement_ops:
            qubit_idx = int(operation.qubit_idx)
            cbit_idx = int(operation.cbit_idx)
            if qubit_idx not in positions:
                raise HardwareInterfaceError(
                    f"Braket result omitted measured qubit q[{qubit_idx}]"
                )
            bits[cbit_idx] = str(int(row[positions[qubit_idx]]))
        key = "".join(reversed(bits))
        raw_counts[key] = raw_counts.get(key, 0) + 1
    return normalize_counts(
        raw_counts,
        width=measured_width(circuit),
        shots=shots,
    )


def run_braket_cloud(
    qasm_str: str,
    shots: int,
    *,
    task_name: str = "LoomQ experiment",
) -> Dict[str, Any]:
    """Submit OpenQASM 3 to an AWS Braket device and wait for its result."""

    positive_shots(shots)
    device_arn = required_env("LOOMQ_BRAKET_DEVICE_ARN")
    bucket, prefix = _s3_location()
    try:
        from braket.aws import AwsDevice
        from braket.ir.openqasm import Program
    except ImportError as exc:
        raise HardwareInterfaceError(
            "Braket remote support requires amazon-braket-sdk and its "
            "default simulator dependencies"
        ) from exc
    try:
        from ..l1.emitters import emit_braket
        from ..l1.parser import parse_qasm2
    except ImportError:
        # Product Service may import adapter from inside starter_kit/.
        from l1.emitters import emit_braket
        from l1.parser import parse_qasm2

    circuit = parse_qasm2(qasm_str)
    program = Program(source=emit_braket(circuit, include_stdgates=False))
    device = AwsDevice(device_arn)

    try:
        timeout = float(os.environ.get("LOOMQ_BRAKET_POLL_TIMEOUT_SECONDS", "3600"))
        interval = float(os.environ.get("LOOMQ_BRAKET_POLL_INTERVAL_SECONDS", "10"))
        task = device.run(
            program,
            (bucket, prefix),
            shots=shots,
            poll_timeout_seconds=max(1.0, timeout),
            poll_interval_seconds=max(0.1, interval),
        )
        result = task.result()
        counts = _normalize_measurements(result, circuit, shots)
        job_id = str(getattr(task, "id", "")).strip()
        if not job_id:
            raise HardwareInterfaceError("Braket task did not expose a task ARN")
        return standard_result(
            backend="braket_aws_device",
            job_id=job_id,
            shots=shots,
            counts=counts,
            meta={
                "provider": "braket",
                "device_arn": device_arn,
                "s3_uri": f"s3://{bucket}/{prefix}",
                "task_name": task_name,
            },
        )
    except HardwareInterfaceError:
        raise
    except Exception as exc:
        raise HardwareInterfaceError(f"Braket remote task failed: {exc}") from exc
