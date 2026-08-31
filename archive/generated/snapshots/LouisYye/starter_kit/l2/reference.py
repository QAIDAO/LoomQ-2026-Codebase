from __future__ import annotations

import math


def _normalized_distribution(target: dict) -> dict[str, float] | None:
    """Validate an explicit distribution; invalid claims fall back to kind."""
    supplied = target.get("expected_distribution")
    if not isinstance(supplied, dict) or not supplied:
        return None
    try:
        values = {str(key): float(value) for key, value in supplied.items()}
    except (TypeError, ValueError):
        return None
    widths = {len(key) for key in values}
    if len(widths) != 1 or not widths or any(set(key) - {"0", "1"} for key in values):
        return None
    width = next(iter(widths))
    try:
        declared_n = int(target.get("n", 0))
    except (TypeError, ValueError):
        declared_n = 0
    if width <= 0 or (declared_n > 0 and width != declared_n):
        return None
    if any(not math.isfinite(value) or value < 0 for value in values.values()):
        return None
    total = sum(values.values())
    if not math.isfinite(total) or total <= 0:
        return None
    return {key: value / total for key, value in values.items()}


def reference_distribution(target: dict) -> dict[str, float] | None:
    if not isinstance(target, dict):
        return None
    explicit = _normalized_distribution(target)
    if explicit is not None:
        return explicit
    kind = str(target.get("kind", "")).lower()
    try:
        n = int(target.get("n", 0))
    except (TypeError, ValueError):
        n = 0
    if kind in {"bell", "epr"}:
        n = 2
        return {"0" * n: 0.5, "1" * n: 0.5}
    if kind == "ghz" and n > 0:
        return {"0" * n: 0.5, "1" * n: 0.5}
    if kind == "w" and n > 0:
        return {format(1 << bit, f"0{n}b"): 1.0 / n for bit in range(n)}
    if kind in {"plus", "uniform", "superposition"} and n > 0:
        return {format(i, f"0{n}b"): 1.0 / (1 << n) for i in range(1 << n)}
    if kind == "basis" and n > 0:
        state = str(target.get("state", "")).replace("|", "").replace(">", "")
        if len(state) == n and not set(state) - {"0", "1"}:
            return {state: 1.0}
    return None
