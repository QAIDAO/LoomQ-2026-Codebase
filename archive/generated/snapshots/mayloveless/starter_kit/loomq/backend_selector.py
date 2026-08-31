"""Deterministic backend selection from the official capability snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping


_DEFAULT_CAPABILITIES_PATH = Path(__file__).resolve().parents[1] / "backend_capabilities.json"
_COST_POLICIES = {"free_only", "free_or_quota", "paid_allowed", "unspecified"}
_REQUIRED_BACKEND_FIELDS = {
    "id",
    "kind",
    "max_qubits",
    "queue",
    "cost",
    "requires_account",
    "name",
}


class BackendCapabilityError(RuntimeError):
    """Raised when the official backend capability data has an invalid schema."""


@dataclass(frozen=True)
class BackendConstraints:
    """Normalized constraints extracted by the model."""

    min_qubits: int | None
    require_qpu: bool | None
    require_no_queue: bool
    cost_policy: str
    allow_account_required: bool | None

    def __post_init__(self) -> None:
        if self.min_qubits is not None and (
            isinstance(self.min_qubits, bool)
            or not isinstance(self.min_qubits, int)
            or self.min_qubits <= 0
        ):
            raise ValueError("min_qubits must be a positive integer or null")
        if self.require_qpu is not None and not isinstance(self.require_qpu, bool):
            raise ValueError("require_qpu must be a boolean or null")
        if not isinstance(self.require_no_queue, bool):
            raise ValueError("require_no_queue must be a boolean")
        if self.cost_policy not in _COST_POLICIES:
            raise ValueError("cost_policy is invalid")
        if self.allow_account_required is not None and not isinstance(
            self.allow_account_required, bool
        ):
            raise ValueError("allow_account_required must be a boolean or null")


@dataclass(frozen=True)
class Backend:
    """Validated fields used by the deterministic selector."""

    id: str
    kind: str
    max_qubits: int
    queue: str
    cost: str
    requires_account: bool
    name: str


def _backend_from_mapping(value: Any, index: int) -> Backend:
    if not isinstance(value, Mapping):
        raise BackendCapabilityError(
            "backend capability entry %d must be an object" % index
        )
    missing = sorted(_REQUIRED_BACKEND_FIELDS.difference(value))
    if missing:
        raise BackendCapabilityError(
            "backend capability entry %d is missing field(s): %s"
            % (index, ", ".join(missing))
        )

    for field in ("id", "kind", "queue", "cost", "name"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise BackendCapabilityError(
                "backend capability field %s at entry %d must be a non-empty string"
                % (field, index)
            )
    max_qubits = value["max_qubits"]
    if isinstance(max_qubits, bool) or not isinstance(max_qubits, int) or max_qubits <= 0:
        raise BackendCapabilityError(
            "backend capability field max_qubits at entry %d must be a positive integer"
            % index
        )
    requires_account = value["requires_account"]
    if not isinstance(requires_account, bool):
        raise BackendCapabilityError(
            "backend capability field requires_account at entry %d must be a boolean"
            % index
        )
    return Backend(
        id=value["id"],
        kind=value["kind"],
        max_qubits=max_qubits,
        queue=value["queue"],
        cost=value["cost"],
        requires_account=requires_account,
        name=value["name"],
    )


def load_backends(path: str | Path | None = None) -> tuple[Backend, ...]:
    """Load and validate capabilities using a path independent of the CWD."""
    capabilities_path = Path(path) if path is not None else _DEFAULT_CAPABILITIES_PATH
    try:
        with capabilities_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        raise BackendCapabilityError("unable to load backend capabilities JSON") from None

    if not isinstance(payload, dict):
        raise BackendCapabilityError("backend capabilities JSON must be an object")
    raw_backends = payload.get("backends")
    if not isinstance(raw_backends, list):
        raise BackendCapabilityError("backend capabilities JSON must contain a backends array")

    backends = tuple(
        _backend_from_mapping(value, index)
        for index, value in enumerate(raw_backends)
    )
    seen_ids = set()
    for backend in backends:
        if backend.id in seen_ids:
            raise BackendCapabilityError(
                "backend capabilities JSON contains duplicate backend id"
            )
        seen_ids.add(backend.id)
    return backends


def load_capability_version(path: str | Path | None = None) -> str:
    """从同一份官方 JSON 事实源读取能力表快照版本。"""
    capabilities_path = Path(path) if path is not None else _DEFAULT_CAPABILITIES_PATH
    try:
        with capabilities_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        raise BackendCapabilityError("unable to load backend capabilities JSON") from None
    version = payload.get("version") if isinstance(payload, dict) else None
    if not isinstance(version, str) or not version.strip():
        raise BackendCapabilityError(
            "backend capabilities JSON must contain a non-empty version"
        )
    return version


def select_backends(
    constraints: BackendConstraints,
    *,
    capabilities_path: str | Path | None = None,
) -> tuple[Backend, ...]:
    """Return all matching backends in the official capability-table order."""
    matches = []
    for backend in load_backends(capabilities_path):
        if (
            constraints.min_qubits is not None
            and backend.max_qubits < constraints.min_qubits
        ):
            continue
        if constraints.require_qpu is True and backend.kind != "qpu":
            continue
        if constraints.require_no_queue and backend.queue != "none":
            continue
        if constraints.cost_policy == "free_only" and backend.cost != "free":
            continue
        if constraints.cost_policy == "free_or_quota" and backend.cost not in (
            "free",
            "free_quota",
        ):
            continue
        if constraints.allow_account_required is False and backend.requires_account:
            continue
        matches.append(backend)
    return tuple(matches)


__all__ = [
    "Backend",
    "BackendCapabilityError",
    "BackendConstraints",
    "load_backends",
    "load_capability_version",
    "select_backends",
]
