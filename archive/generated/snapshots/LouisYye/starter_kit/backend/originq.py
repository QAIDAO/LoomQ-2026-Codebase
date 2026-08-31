import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4


def _configure_writable_caches() -> None:
    cache_root = Path(tempfile.gettempdir()) / "loomq-originq-cache"
    matplotlib_cache = cache_root / "matplotlib"
    xdg_cache = cache_root / "xdg"
    matplotlib_cache.mkdir(parents=True, exist_ok=True)
    xdg_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_cache))
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache))


def _normalize_counts(
    raw_counts: Dict[Any, int],
    num_bits: int,
) -> Dict[str, int]:
    normalized: Dict[str, int] = {}

    for raw_key, count in raw_counts.items():
        if isinstance(raw_key, int):
            key = format(raw_key, f"0{num_bits}b")
        else:
            text = str(raw_key)
            if text and not set(text) - {"0", "1"}:
                key = text.zfill(num_bits)
            elif text.isdigit():
                key = format(int(text), f"0{num_bits}b")
            else:
                raise ValueError(f"Unsupported OriginQ count key: {raw_key!r}")

        normalized[key] = normalized.get(key, 0) + int(count)

    return normalized


def run_originq(
    origin_ir: str,
    shots: int,
) -> Dict[str, Any]:
    if shots <= 0:
        raise ValueError("shots must be positive")

    _configure_writable_caches()
    import pyqpanda as pq

    machine = pq.CPUQVM()
    machine.init_qvm()

    try:
        program, _qubits, classical_bits = (
            pq.convert_originir_str_to_qprog(origin_ir, machine)
        )
        raw_counts = machine.run_with_configuration(
            program,
            classical_bits,
            shots,
        )
    finally:
        machine.finalize()

    counts = _normalize_counts(raw_counts, len(classical_bits))

    return {
        "backend": "originq_local_simulator",
        "job_id": f"originq-local-{uuid4()}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "is_mock": False,
        },
    }
