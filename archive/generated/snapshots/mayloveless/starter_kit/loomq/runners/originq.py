"""pyQPanda CPUQVM 隔离 Runner 与 OriginQ counts 校验。"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple
from uuid import uuid4

from ..ir import Circuit, GateOperation, MeasureOperation
from ..measurements import classical_bit_count, measurement_mapping
from ..results import create_result, validate_shots
from ..serializers.originq import serialize_originq


_WORKER_TIMEOUT_SECONDS = 120
_STDERR_LIMIT = 4000


def _validate_final_measurements(circuit: Circuit) -> Tuple[Tuple[int, int], ...]:
    """校验 CPUQVM Runner 只接收末尾测量，并返回统一映射。"""
    measurement_seen = False
    for operation in circuit.operations:
        if isinstance(operation, MeasureOperation):
            measurement_seen = True
        elif isinstance(operation, GateOperation) and measurement_seen:
            raise ValueError("OriginQ runner supports final measurements only")

    mapping = tuple(measurement_mapping(circuit))
    if not mapping:
        raise ValueError("OriginQ runner requires at least one measurement")
    return mapping


def normalize_originq_counts(
    circuit: Circuit, raw_counts: Mapping[str, int], shots: int
) -> Dict[str, int]:
    """校验 pyQPanda 已按 c[n-1]...c[0] 返回的完整经典寄存器 key。"""
    validate_shots(shots)
    _validate_final_measurements(circuit)
    if not isinstance(raw_counts, dict) or not raw_counts:
        raise ValueError("OriginQ counts must be a non-empty dict")

    width = classical_bit_count(circuit)
    normalized: Dict[str, int] = {}
    total = 0
    for key, count in raw_counts.items():
        if not isinstance(key, str) or set(key) - {"0", "1"}:
            raise ValueError("OriginQ count keys must be binary strings")
        if len(key) != width:
            raise ValueError("OriginQ count key width must match all classical bits")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("OriginQ count values must be non-negative integers")
        normalized[key] = count
        total += count

    if total != shots:
        raise ValueError("OriginQ counts total must equal shots exactly")
    # 3.8.5 实测 raw key 已是 LoomQ 位序，不进行无依据的二次翻转。
    return normalized


def _starter_kit_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _find_originq_python() -> Path:
    configured = os.environ.get("LOOMQ_ORIGINQ_PYTHON")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return path
        raise RuntimeError(
            "OriginQ isolated Python was not found; set LOOMQ_ORIGINQ_PYTHON"
        )

    root = _starter_kit_root()
    candidates = (
        root / ".venv-originq" / "bin" / "python",
        root / ".venv-originq" / "Scripts" / "python.exe",
        Path("/opt/originq-venv/bin/python"),
    )
    for path in candidates:
        if path.is_file():
            return path
    raise RuntimeError(
        "OriginQ isolated Python was not found; set LOOMQ_ORIGINQ_PYTHON"
    )


def _stderr_excerpt(stderr: str) -> str:
    message = stderr.strip()
    if len(message) <= _STDERR_LIMIT:
        return message
    return "..." + message[-_STDERR_LIMIT:]


def run_originq(circuit: Circuit, shots: int) -> Dict[str, Any]:
    """通过独立 Python Worker 调用 pyQPanda，避免原生库污染主解释器。"""
    validate_shots(shots)
    _validate_final_measurements(circuit)
    python_path = _find_originq_python()
    request = json.dumps(
        {
            "originir": serialize_originq(circuit, execution_mode=True),
            "shots": shots,
        },
        ensure_ascii=False,
    )
    command = [str(python_path), "-m", "loomq.workers.originq_worker"]

    try:
        completed = subprocess.run(
            command,
            input=request,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=_WORKER_TIMEOUT_SECONDS,
            check=False,
            cwd=str(_starter_kit_root()),
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "OriginQ worker timed out after %d seconds" % _WORKER_TIMEOUT_SECONDS
        ) from exc

    if completed.returncode != 0:
        details = _stderr_excerpt(completed.stderr)
        suffix = ": %s" % details if details else ""
        raise RuntimeError(
            "OriginQ worker failed with exit code %d%s"
            % (completed.returncode, suffix)
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OriginQ worker returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("OriginQ worker result must be a JSON object")
    raw_counts = payload.get("counts")
    counts = normalize_originq_counts(circuit, raw_counts, shots)
    return create_result(
        backend="originq_cpuqvm",
        job_id="originq-local-%s" % uuid4(),
        shots=shots,
        counts=counts,
        meta={"simulator": "CPUQVM", "sdk": "pyqpanda"},
    )
