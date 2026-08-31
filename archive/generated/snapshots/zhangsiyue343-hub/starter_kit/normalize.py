#!/usr/bin/env python3
"""Pure count-normalization functions.

Every backend plugin converts its raw sampling output into the unified
schema here: keys are clbit strings ordered c[n-1]..c[0] ("little" bit
order, rightmost character = c[0]).

A raw key describes measured *qubit* values. Plugins declare how a raw key
maps qubit index -> bit (endianness) plus the measure map; this module does
the arithmetic once, identically, for all backends.
"""

from __future__ import annotations

from typing import Iterable, Mapping


def raw_key_to_clbit_key(raw_key: str,
                         big_endian: bool,
                         measures: Iterable[tuple[int, int]],
                         n_clbits: int,
                         n_qubits: int | None = None) -> str:
    """Translate one backend key into the unified little-endian clbit key.

    big_endian=True  -> raw_key[0] is qubit 0 (leftmost), Qiskit/Braket style;
    big_endian=False -> raw_key[0] is qubit n-1 (little-endian), pyqpanda style.
    Unmeasured clbits read as 0.
    """
    length = len(raw_key)
    if n_qubits is not None and length != n_qubits:
        raise ValueError("counts key %r has length %d, expected %d"
                         % (raw_key, length, n_qubits))

    def bit_of(qubit: int) -> int:
        position = qubit if big_endian else length - 1 - qubit
        if not 0 <= position < length:
            raise ValueError("qubit %d missing from counts key %r" % (qubit, raw_key))
        return 1 if raw_key[position] == "1" else 0

    bits = ["0"] * n_clbits
    for qubit, clbit in measures:
        if not 0 <= clbit < n_clbits:
            raise ValueError("measure target c[%d] out of range" % clbit)
        bits[clbit] = str(bit_of(qubit))
    return "".join(reversed(bits))


def normalize_counts(raw_counts: Mapping[str, int],
                     big_endian: bool,
                     measures: Iterable[tuple[int, int]],
                     n_clbits: int,
                     n_qubits: int | None = None) -> dict[str, int]:
    """Fold normalize_counts over every raw key; zero-count keys are dropped."""
    normalized: dict[str, int] = {}
    measure_pairs = list(measures)
    for raw_key, hits in raw_counts.items():
        if hits <= 0:
            continue
        key = raw_key_to_clbit_key(raw_key, big_endian, measure_pairs,
                                   n_clbits, n_qubits)
        normalized[key] = normalized.get(key, 0) + hits
    return normalized


def merge_counts(*count_maps: Mapping[str, int]) -> dict[str, int]:
    """Aggregate several result sets (async fan-out/fan-in helper)."""
    merged: dict[str, int] = {}
    for counts in count_maps:
        for key, hits in counts.items():
            merged[key] = merged.get(key, 0) + hits
    return merged


def top_states(counts: Mapping[str, int], k: int = 4) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:k]
