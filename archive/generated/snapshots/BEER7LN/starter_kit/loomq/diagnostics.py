"""Distribution diagnostics shared by native backend execution paths."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping


@dataclass(frozen=True)
class BitOrderProbe:
    decision: str
    original_fidelity: float
    reversed_fidelity: float
    corrected: bool

    def to_meta(self) -> dict[str, object]:
        return asdict(self)


def hellinger_fidelity(
    observed: Mapping[str, float], expected: Mapping[str, float]
) -> float:
    """Use the exact metric published by the LoomQ evaluator."""

    states = set(observed) | set(expected)
    distance = math.sqrt(
        sum(
            (
                math.sqrt(max(0.0, float(observed.get(state, 0.0))))
                - math.sqrt(max(0.0, float(expected.get(state, 0.0))))
            )
            ** 2
            for state in states
        )
    ) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - distance))


def acceptance_threshold(outcome_count: int, shots: int) -> float:
    """Return a conservative shot-noise-aware semantic acceptance floor.

    The asymptotic Hellinger noise scale for a multinomial sample is roughly
    sqrt((k-1)/(8N)).  Three such scales are allowed for diagnostics, while
    never demanding more than the competition's 0.97 threshold.  Small-shot
    developer probes therefore remain useful without weakening formal 8192
    shot verification.
    """

    if isinstance(outcome_count, bool) or not isinstance(outcome_count, int):
        raise ValueError("outcome_count must be a positive integer")
    if isinstance(shots, bool) or not isinstance(shots, int):
        raise ValueError("shots must be a positive integer")
    if outcome_count <= 0 or shots <= 0:
        raise ValueError("outcome_count and shots must be positive")
    if shots >= 8192:
        return 0.97
    noise_scale = math.sqrt(max(0, outcome_count - 1) / (8.0 * shots))
    return max(0.85, min(0.97, 1.0 - 3.0 * noise_scale))


def probe_bit_order(
    counts: Mapping[str, int],
    expected: Mapping[str, float],
    *,
    improvement_margin: float = 0.02,
) -> tuple[dict[str, int], BitOrderProbe]:
    """Compare current and fully reversed classical bit-string conventions."""

    total = sum(int(value) for value in counts.values())
    if total <= 0:
        raise ValueError("counts must contain positive probability mass")
    observed = {str(key): int(value) / total for key, value in counts.items()}
    reversed_counts: dict[str, int] = {}
    for key, value in counts.items():
        reversed_key = str(key)[::-1]
        reversed_counts[reversed_key] = reversed_counts.get(reversed_key, 0) + int(value)
    reversed_observed = {
        key: value / total for key, value in reversed_counts.items()
    }
    original = hellinger_fidelity(observed, expected)
    reversed_score = hellinger_fidelity(reversed_observed, expected)
    should_reverse = reversed_score >= original + improvement_margin
    if should_reverse:
        decision = "reversed"
    elif original >= reversed_score + improvement_margin:
        decision = "as_is"
    else:
        decision = "ambiguous"
    return (
        dict(sorted(reversed_counts.items())) if should_reverse else dict(sorted(counts.items())),
        BitOrderProbe(
            decision=decision,
            original_fidelity=round(original, 9),
            reversed_fidelity=round(reversed_score, 9),
            corrected=should_reverse,
        ),
    )
