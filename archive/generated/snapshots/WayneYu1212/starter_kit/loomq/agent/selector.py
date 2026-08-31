"""Deterministic backend selection from the organizer's canonical table."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .response import BackendConstraints


CAPABILITIES_PATH = Path(__file__).resolve().parents[2] / "backend_capabilities.json"


def _load_backends() -> list[dict[str, Any]]:
    payload = json.loads(CAPABILITIES_PATH.read_text(encoding="utf-8"))
    backends = payload.get("backends")
    if not isinstance(backends, list) or not all(isinstance(item, dict) for item in backends):
        raise RuntimeError("backend_capabilities.json has an invalid backends list")
    return backends


def select_backends(constraints: BackendConstraints) -> list[dict[str, Any]]:
    """Return canonical backend records satisfying every explicit constraint."""

    if not isinstance(constraints, BackendConstraints):
        raise TypeError("constraints must be BackendConstraints")
    selected: list[dict[str, Any]] = []
    for backend in _load_backends():
        if constraints.qubits is not None and backend["max_qubits"] < constraints.qubits:
            continue
        if constraints.kind is not None and backend["kind"] != constraints.kind:
            continue
        if constraints.zero_queue is True and backend["queue"] != "none":
            continue
        if constraints.avoid_paid is True and backend["cost"] == "paid":
            continue
        if constraints.accountless is True and backend["requires_account"]:
            continue
        selected.append(dict(backend))
    return selected
