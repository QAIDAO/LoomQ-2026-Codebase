from __future__ import annotations

import math


def fidelity(observed: dict[str, float], expected: dict[str, float]) -> float:
    states = set(observed) | set(expected)
    distance = math.sqrt(sum(
        (math.sqrt(observed.get(s, 0.0)) - math.sqrt(expected.get(s, 0.0))) ** 2
        for s in states
    )) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - distance))

