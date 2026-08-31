"""三平台厂商 artifact 的独立 SDK 执行入口。"""

import importlib
import importlib.metadata
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from loomq.results import validate_shots


_WORKER_TIMEOUT_SECONDS = 120


def _package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _execute_braket(artifact: str, shots: int) -> Dict[str, Any]:
    """把调用方提供的 OQ3 交给 Braket Program 与 LocalSimulator。"""
    devices = importlib.import_module("braket.devices")
    openqasm = importlib.import_module("braket.ir.openqasm")
    program = openqasm.Program(source=artifact)
    result = devices.LocalSimulator("braket_sv").run(program, shots=shots).result()
    counts = getattr(result, "measurement_counts", None)
    if not isinstance(counts, Mapping) or not counts:
        raise RuntimeError("Braket native execution returned no measurement_counts")
    measured_qubits = getattr(result, "measured_qubits", None)
    measurements = getattr(result, "measurements", None)
    if measured_qubits is None or measurements is None:
        raise RuntimeError("Braket native result exposes no measurement matrix")
    return {
        "counts": {str(key): int(value) for key, value in counts.items()},
        "measured_qubits": [int(value) for value in measured_qubits],
        "measurements": [
            [int(value) for value in row] for row in measurements
        ],
        "sdk_version": _package_version("amazon-braket-sdk"),
    }


def normalized_native_counts(payload: Dict[str, Any], shots: int) -> Dict[str, int]:
    """将厂商直测结果归一为 c[n-1]...c[0]；不调用 LoomQ Parser。"""
    measured_qubits = payload.get("measured_qubits")
    measurements = payload.get("measurements")
    if isinstance(measured_qubits, list) and isinstance(measurements, list):
        if not measured_qubits:
            raise ValueError("native measured_qubits must not be empty")
        width = max(int(qubit) for qubit in measured_qubits) + 1
        normalized: Counter[str] = Counter()
        for row in measurements:
            if not isinstance(row, Sequence) or len(row) != len(measured_qubits):
                raise ValueError("native measurement row width is invalid")
            values = {
                int(qubit): int(value)
                for qubit, value in zip(measured_qubits, row)
            }
            key = "".join(str(values.get(index, 0)) for index in reversed(range(width)))
            normalized[key] += 1
        counts = dict(normalized)
    else:
        raw_counts = payload.get("counts")
        if not isinstance(raw_counts, dict) or not raw_counts:
            raise ValueError("native payload must contain non-empty counts")
        counts = {str(key): int(value) for key, value in raw_counts.items()}
        if payload.get("count_key_order") == "q0_to_qn":
            counts = {key[::-1]: value for key, value in counts.items()}
    if sum(counts.values()) != shots:
        raise ValueError("native counts total must equal shots")
    return counts


def _isolated_python(target: str) -> Path:
    if target == "spinq":
        from loomq.runners.spinq import _find_spinq_python

        return _find_spinq_python()
    if target == "originq":
        from loomq.runners.originq import _find_originq_python

        return _find_originq_python()
    raise ValueError("isolated native target must be spinq or originq")


def _execute_isolated(
    target: str, artifact: str, shots: int
) -> Dict[str, Any]:
    python_path = _isolated_python(target)
    request = json.dumps(
        {"target": target, "artifact": artifact, "shots": shots},
        ensure_ascii=False,
    )
    completed = subprocess.run(
        [str(python_path), "-m", "scripts.l1_native_worker"],
        input=request,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=_WORKER_TIMEOUT_SECONDS,
        check=False,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    if completed.returncode != 0:
        details = completed.stderr.strip()
        raise RuntimeError(
            "%s native worker failed with exit code %d%s"
            % (
                target,
                completed.returncode,
                ": %s" % details[-4000:] if details else "",
            )
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("%s native worker returned invalid JSON" % target) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("counts"), dict):
        raise RuntimeError("%s native worker returned an invalid payload" % target)
    return payload


def execute_native_artifact(
    target: str, artifact: str, shots: int
) -> Dict[str, Any]:
    """执行调用方提供的厂商 artifact；具体独立性边界由调用方记录。"""
    validate_shots(shots)
    if not isinstance(artifact, str) or not artifact.strip():
        raise ValueError("native artifact must be a non-empty string")
    if target == "braket":
        return _execute_braket(artifact, shots)
    if target in ("spinq", "originq"):
        return _execute_isolated(target, artifact, shots)
    raise ValueError("unsupported native target %r" % target)
