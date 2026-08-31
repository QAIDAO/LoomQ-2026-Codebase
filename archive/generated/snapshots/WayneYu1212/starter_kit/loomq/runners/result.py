"""Cross-SDK count normalization and official result Schema construction."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from ..compiler.ir import Measurement


BACKEND_IDS = {
    "spinq": "spinq_taurus_simulator",
    "originq": "originq_local_simulator",
    "braket": "braket_local_simulator",
}


def _state_value(raw_key: object, width: int) -> int:
    if isinstance(raw_key, bool):
        raise ValueError("count state cannot be boolean")
    if isinstance(raw_key, int):
        value = raw_key
    elif isinstance(raw_key, str):
        compact = "".join(raw_key.strip().split())
        if compact.lower().startswith("0b"):
            digits = compact[2:]
            if not digits or set(digits) - {"0", "1"}:
                raise ValueError(f"invalid binary count state: {raw_key!r}")
            value = int(digits, 2)
        elif compact and not set(compact) - {"0", "1"}:
            value = int(compact, 2)
        elif compact.isdecimal():
            value = int(compact, 10)
        else:
            raise ValueError(f"invalid count state: {raw_key!r}")
    else:
        raise ValueError(f"unsupported count state type: {type(raw_key).__name__}")
    if value < 0 or value >= 1 << width:
        raise ValueError(f"count state {raw_key!r} does not fit width {width}")
    return value


def normalize_counts(
    raw: Mapping[Any, Any],
    *,
    width: int,
    reverse_bits: bool = False,
) -> dict[str, int]:
    """Normalize SDK result keys without guessing away width or bit order."""

    if isinstance(width, bool) or not isinstance(width, int) or width <= 0:
        raise ValueError("count width must be a positive integer")
    if not isinstance(raw, Mapping) or not raw:
        raise ValueError("counts must be a non-empty mapping")
    normalized: dict[str, int] = {}
    for raw_key, raw_count in raw.items():
        if isinstance(raw_count, bool) or not isinstance(raw_count, int) or raw_count < 0:
            raise ValueError("count values must be non-negative integers")
        key = f"{_state_value(raw_key, width):0{width}b}"
        if reverse_bits:
            key = key[::-1]
        normalized[key] = normalized.get(key, 0) + raw_count
    return dict(sorted(normalized.items()))


def remap_measured_qubits(
    raw: Mapping[Any, Any],
    *,
    measured_qubits: list[int] | tuple[int, ...],
    measurements: tuple[Measurement, ...],
    cbit_count: int,
) -> dict[str, int]:
    """Map SDK keys ordered by measured qubits into LoomQ classical-bit keys."""

    if not measured_qubits:
        raise ValueError("SDK returned no measured qubits")
    qubit_to_cbit: dict[int, int] = {}
    for measurement in measurements:
        if measurement.qubit in qubit_to_cbit:
            raise ValueError("measuring one qubit into multiple cbits is unsupported")
        qubit_to_cbit[measurement.qubit] = measurement.cbit
    if set(measured_qubits) != set(qubit_to_cbit):
        raise ValueError("SDK measured-qubit set does not match the circuit")

    native = normalize_counts(raw, width=len(measured_qubits))
    remapped: dict[str, int] = {}
    for native_key, count in native.items():
        classical = ["0"] * cbit_count
        for bit, qubit in zip(native_key, measured_qubits):
            classical[qubit_to_cbit[qubit]] = bit
        key = "".join(reversed(classical))
        remapped[key] = remapped.get(key, 0) + count
    return dict(sorted(remapped.items()))


def build_result(
    target: str,
    job_id: str,
    shots: int,
    counts: Mapping[Any, Any],
    width: int,
    meta: Mapping[str, Any],
    *,
    reverse_bits: bool = False,
) -> dict[str, Any]:
    """Build one result object that satisfies the LoomQ public contract."""

    try:
        backend = BACKEND_IDS[target]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unsupported target: {target}") from exc
    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("job_id must be a non-empty string")
    if isinstance(shots, bool) or not isinstance(shots, int) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    normalized = normalize_counts(counts, width=width, reverse_bits=reverse_bits)
    if sum(normalized.values()) != shots:
        raise ValueError("counts sum must equal shots exactly")
    metadata = dict(meta)
    if metadata.get("is_mock"):
        raise ValueError("mock metadata is forbidden")
    return {
        "backend": backend,
        "job_id": job_id.strip(),
        "shots": shots,
        "counts": normalized,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "meta": metadata,
    }
