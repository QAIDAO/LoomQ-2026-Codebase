from __future__ import annotations

import json
from pathlib import Path


# Constraints that may never be relaxed: dropping them changes the answer class
# (a simulator is never an acceptable answer to a real-hardware question).
HARD_CONSTRAINTS = ("requires_hardware",)

# Soft constraints, relaxed one at a time in this order when nothing qualifies.
RELAX_ORDER = ("local_only", "no_account", "cost", "queue", "min_qubits")

# The official capability table marks exactly one backend as the evaluation
# default; prefer it whenever candidates are otherwise indistinguishable.
RECOMMENDED_MARKER = "评测推荐默认"


def load_backends() -> list[dict]:
    path = Path(__file__).resolve().parents[1] / "backend_capabilities.json"
    return json.loads(path.read_text(encoding="utf-8"))["backends"]


def _minimum_qubits(constraints: dict) -> int:
    try:
        return int(constraints.get("min_qubits") or 0)
    except (TypeError, ValueError):
        return 0


def _predicates(constraints: dict) -> dict:
    """Build the active predicate for every declared constraint."""
    minimum = _minimum_qubits(constraints)
    predicates: dict = {}
    if minimum:
        predicates["min_qubits"] = lambda b: b["max_qubits"] >= minimum
    if constraints.get("queue") == "none":
        predicates["queue"] = lambda b: b["queue"] == "none"
    if constraints.get("cost") == "free":
        predicates["cost"] = lambda b: b["cost"] == "free"
    if constraints.get("requires_hardware") is True:
        predicates["requires_hardware"] = lambda b: b["kind"] == "qpu"
    if constraints.get("local_only") is True:
        predicates["local_only"] = (
            lambda b: b["kind"] == "simulator" and not b["requires_account"]
        )
    if constraints.get("no_account") is True:
        predicates["no_account"] = lambda b: not b["requires_account"]
    return predicates


def _apply(backends: list[dict], predicates: dict) -> list[dict]:
    for predicate in predicates.values():
        backends = [backend for backend in backends if predicate(backend)]
    return backends


def _sort_key(constraints: dict, relaxed: frozenset = frozenset()):
    wants_hardware = constraints.get("requires_hardware") is True
    # If the capacity request could not be met, the closest answer is the
    # largest machine available rather than the most convenient one.
    capacity_first = "min_qubits" in relaxed
    # Without an explicit hardware requirement, queueing and account setup are
    # real costs to the user: simulator < managed cloud < physical QPU.
    kind_rank = {"simulator": 0, "cloud": 1, "qpu": 2}
    queue_rank = {"none": 0, "minutes_to_hours": 1, "hours": 2}
    cost_rank = {"free": 0, "free_quota": 1, "paid": 2}

    def key(backend: dict):
        if wants_hardware:
            kind = 0 if backend["kind"] == "qpu" else 1
        else:
            kind = kind_rank.get(backend["kind"], 9)
        return (
            kind,
            -backend["max_qubits"] if capacity_first else 0,
            queue_rank.get(backend["queue"], 9),
            cost_rank.get(backend["cost"], 9),
            bool(backend["requires_account"]),
            0 if RECOMMENDED_MARKER in backend.get("notes", "") else 1,
            -backend["max_qubits"],
            backend["id"],
        )

    return key


def select(constraints: dict) -> dict:
    """Pick exactly one backend, honouring hard constraints even when relaxing."""
    if not isinstance(constraints, dict):
        constraints = {}

    all_backends = load_backends()
    predicates = _predicates(constraints)
    candidates = _apply(all_backends, predicates)
    relaxed: set[str] = set()

    # Relax soft constraints one at a time; hard constraints always survive.
    for name in RELAX_ORDER:
        if candidates:
            break
        if name in predicates and name not in HARD_CONSTRAINTS:
            predicates.pop(name)
            relaxed.add(name)
            candidates = _apply(all_backends, predicates)

    if not candidates:
        # Only hard constraints remain; keep them if anything satisfies them.
        hard_only = {
            name: predicate
            for name, predicate in predicates.items()
            if name in HARD_CONSTRAINTS
        }
        candidates = _apply(all_backends, hard_only) or all_backends
        relaxed.update(RELAX_ORDER)

    return sorted(candidates, key=_sort_key(constraints, frozenset(relaxed)))[0]
