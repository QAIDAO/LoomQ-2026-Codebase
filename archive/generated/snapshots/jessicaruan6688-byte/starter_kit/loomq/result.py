"""Unified LoomQ result schema helpers.

Backends disagree about bit order, so normalisation lives here:

* SpinQ / Braket key counts by **qubit** index (leftmost = ``q[0]``) and ignore
  the measure map. Use ``remap_counts``.
* pyqpanda already returns **classical** little-endian keys that honour the
  measure map. Use ``normalize_classical_counts`` — remapping those keys a
  second time would corrupt them.

Bell and GHZ are symmetric under bit reversal, so this class of bug is invisible
on the public circuits; asymmetric and permuted-measure circuits expose it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_bitstring(key: Any, width: int) -> str:
    if isinstance(key, int) and not isinstance(key, bool):
        return format(key, f"0{width}b")
    text = str(key).strip()
    cleaned = "".join(ch for ch in text if ch in "01")
    if cleaned and len(cleaned) == len(text.replace(" ", "")):
        return cleaned
    if text.isdigit():
        return format(int(text), f"0{width}b")
    if not cleaned:
        raise ValueError(f"cannot interpret counts key: {key!r}")
    return cleaned


def normalize_classical_counts(
    counts: Mapping[Any, Any], n_bits: int
) -> Dict[str, int]:
    """Normalize keys that are already classical-bit little-endian."""
    out: Dict[str, int] = {}
    for key, value in counts.items():
        bits = _as_bitstring(key, n_bits).zfill(n_bits)[-n_bits:]
        if set(bits) - {"0", "1"}:
            raise ValueError(f"cannot interpret counts key: {key!r}")
        out[bits] = out.get(bits, 0) + int(value)
    return out


def remap_counts(
    counts: Mapping[Any, Any],
    *,
    n_bits: int,
    n_qubits: int,
    measured: Sequence[Tuple[int, int]],
) -> Dict[str, int]:
    """Rewrite qubit-indexed backend counts into little-endian classical bits."""
    qubit_to_cbit: Dict[int, int] = {}
    for qubit_index, cbit_index in measured:
        qubit_to_cbit[qubit_index] = cbit_index
    measured_qubits = sorted(qubit_to_cbit)

    out: Dict[str, int] = {}
    for key, value in counts.items():
        bits = _as_bitstring(key, n_qubits)
        if len(bits) == n_qubits:
            source = list(range(n_qubits))
        elif len(bits) == len(measured_qubits):
            source = measured_qubits
        else:
            raise ValueError(
                f"counts key {key!r} has width {len(bits)}, expected "
                f"{n_qubits} or {len(measured_qubits)}"
            )
        target = ["0"] * n_bits
        for position, qubit_index in enumerate(source):
            cbit = qubit_to_cbit.get(qubit_index)
            if cbit is None:
                continue
            target[n_bits - 1 - cbit] = bits[position]
        bitstring = "".join(target)
        out[bitstring] = out.get(bitstring, 0) + int(value)
    return out


def build_result(
    *,
    backend: str,
    job_id: str,
    shots: int,
    counts: Mapping[str, int],
    meta: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble the unified schema from counts already keyed by classical bit."""
    normalized = {str(key): int(value) for key, value in counts.items()}
    total = sum(normalized.values())
    if total == 0:
        raise ValueError("backend returned empty counts")
    if total != shots:
        raise ValueError(f"counts total {total} != shots {shots}")
    return {
        "backend": backend,
        "job_id": str(job_id),
        "shots": int(shots),
        "counts": normalized,
        "bit_order": "little",
        "timestamp": timestamp or utc_now(),
        "meta": meta or {},
    }
