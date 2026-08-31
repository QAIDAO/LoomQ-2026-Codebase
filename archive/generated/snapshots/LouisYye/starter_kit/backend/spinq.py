import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4


RESULT_PREFIX = "LOOMQ_SPINQ_RESULT="


def _find_spinq_python() -> Path:
    configured = os.environ.get("LOOMQ_SPINQ_PYTHON")
    candidates = []

    if configured:
        candidates.append(Path(configured))

    candidates.extend(
        [
            Path("/opt/spinq-venv/bin/python"),
            Path(__file__).resolve().parents[2]
            / ".spinq-venv"
            / "bin"
            / "python",
        ]
    )

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise RuntimeError(
        "SpinQ Python environment not found. Set LOOMQ_SPINQ_PYTHON "
        "or create .spinq-venv with spinqit==0.2.4"
    )


def _worker_environment(python_path: Path) -> Dict[str, str]:
    environment = os.environ.copy()
    cache_root = Path(tempfile.gettempdir()) / "loomq-spinq-cache"
    environment.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
    environment.setdefault("XDG_CACHE_HOME", str(cache_root / "xdg"))

    environment_root = python_path.parent.parent
    library_paths = [str(environment_root / "lib")]
    library_paths.extend(
        str(path)
        for path in environment_root.glob(
            "lib/python*/site-packages/spinqit"
        )
    )

    for variable in ("DYLD_LIBRARY_PATH", "LD_LIBRARY_PATH"):
        existing = environment.get(variable)
        values = library_paths + ([existing] if existing else [])
        environment[variable] = os.pathsep.join(values)

    return environment


def _parse_worker_result(stdout: str) -> Dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX) :])

    raise RuntimeError("SpinQ worker returned no structured result")


def _normalize_counts(
    raw_counts: Dict[str, int],
    measurement_map: Dict[int, int],
    num_bits: int,
) -> Dict[str, int]:
    normalized: Dict[str, int] = {}

    for raw_key, count in raw_counts.items():
        classical_bits = ["0"] * num_bits

        for qubit, classical_bit in measurement_map.items():
            if qubit >= len(raw_key):
                raise ValueError(
                    f"SpinQ count key {raw_key!r} has no qubit {qubit}"
                )
            classical_bits[classical_bit] = raw_key[qubit]

        key = "".join(reversed(classical_bits))
        normalized[key] = normalized.get(key, 0) + int(count)

    return normalized


def run_spinq(
    qasm2: str,
    shots: int,
    measurement_map: Dict[int, int],
    num_bits: int,
) -> Dict[str, Any]:
    if shots <= 0:
        raise ValueError("shots must be positive")

    python_path = _find_spinq_python()
    worker_path = Path(__file__).resolve().parents[1] / "spinq_worker.py"
    request = json.dumps({"qasm": qasm2, "shots": shots})

    process = subprocess.run(
        [str(python_path), str(worker_path)],
        input=request,
        text=True,
        capture_output=True,
        env=_worker_environment(python_path),
        timeout=120,
        check=False,
    )
    payload = _parse_worker_result(process.stdout)

    if process.returncode != 0 or "error" in payload:
        message = payload.get("error", process.stderr.strip())
        error_type = payload.get("error_type", "WorkerError")
        raise RuntimeError(f"SpinQ {error_type}: {message}")

    counts = _normalize_counts(
        raw_counts=payload["counts"],
        measurement_map=measurement_map,
        num_bits=num_bits,
    )

    return {
        "backend": "spinq_basic_simulator",
        "job_id": f"spinq-local-{uuid4()}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "is_mock": False,
            "qubits_count": payload["num_qubits"],
        },
    }
