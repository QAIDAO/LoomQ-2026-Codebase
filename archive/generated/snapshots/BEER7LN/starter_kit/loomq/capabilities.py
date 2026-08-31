"""Validated backend capability matrix and normalized selection constraints."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping


CAPABILITIES_FILE = Path(__file__).resolve().parents[1] / "backend_capabilities.json"
_KINDS = {"simulator", "qpu", "cloud"}
_QUEUES = {"none", "minutes_to_hours", "hours"}
_COSTS = {"free", "free_quota", "paid"}


@dataclass(frozen=True)
class BackendCapability:
    id: str
    platform: str
    name: str
    kind: str
    max_qubits: int
    queue: str
    cost: str
    requires_account: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_constraint_spec(source: Mapping[str, Any]) -> dict[str, Any]:
    """Map common model field aliases into one strict internal schema."""

    if not isinstance(source, Mapping):
        raise ValueError("constraints must be an object")
    minimum = _first(source, "min_qubits", "minimum_qubits", "qubits", default=1)
    if isinstance(minimum, str) and minimum.strip().isdigit():
        minimum = int(minimum)
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum <= 0:
        raise ValueError("min_qubits must be a positive integer")

    required_kind = _first(
        source, "required_kind", "backend_kind", "kind", default=None
    )
    if isinstance(required_kind, str):
        required_kind = {
            "hardware": "qpu",
            "real": "qpu",
            "real_hardware": "qpu",
            "local": "simulator",
        }.get(required_kind.strip().lower(), required_kind.strip().lower())
    if required_kind not in {None, *_KINDS}:
        raise ValueError("required_kind is invalid")

    real_hardware = _bool_value(
        _first(
            source,
            "require_real_hardware",
            "real_hardware",
            "needs_qpu",
            default=False,
        ),
        "require_real_hardware",
    )
    zero_queue = _bool_value(
        _first(source, "require_zero_queue", "zero_queue", default=False),
        "require_zero_queue",
    )
    avoid_paid = _bool_value(
        _first(source, "avoid_paid", "free_only", default=False),
        "avoid_paid",
    )
    no_account = _bool_value(
        _first(source, "require_no_account", "no_account", default=False),
        "require_no_account",
    )

    allowed = _first(
        source, "allowed_platforms", "platforms", "platform", default=[]
    )
    if allowed is None:
        allowed = []
    if isinstance(allowed, str):
        allowed = [allowed]
    if not isinstance(allowed, (list, tuple)) or not all(
        isinstance(item, str) and item.strip() for item in allowed
    ):
        raise ValueError("allowed_platforms must be a string list")
    return {
        "min_qubits": minimum,
        "required_kind": "qpu" if real_hardware else required_kind,
        "require_zero_queue": zero_queue,
        "avoid_paid": avoid_paid,
        "require_no_account": no_account,
        "allowed_platforms": tuple(
            sorted({item.strip().lower() for item in allowed})
        ),
    }


def load_capability_matrix(
    path: Path = CAPABILITIES_FILE,
) -> tuple[BackendCapability, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("backends")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("backend_capabilities.json has no backends")
    capabilities = tuple(_validated_capability(row) for row in rows)
    identifiers = [item.id for item in capabilities]
    if len(identifiers) != len(set(identifiers)):
        raise RuntimeError("backend capability IDs must be unique")
    return capabilities


def compatible_backends(
    constraints: Mapping[str, Any],
    capabilities: tuple[BackendCapability, ...] | None = None,
) -> tuple[BackendCapability, ...]:
    normalized = normalize_constraint_spec(constraints)
    available = capabilities or load_capability_matrix()
    matches = [item for item in available if capability_matches(item, normalized)]
    return tuple(sorted(matches, key=lambda item: capability_rank(item, normalized)))


def capability_matches(
    backend: BackendCapability, constraints: Mapping[str, Any]
) -> bool:
    if backend.max_qubits < int(constraints["min_qubits"]):
        return False
    if constraints["required_kind"] and backend.kind != constraints["required_kind"]:
        return False
    if constraints["require_zero_queue"] and backend.queue != "none":
        return False
    if constraints["avoid_paid"] and backend.cost == "paid":
        return False
    if constraints["require_no_account"] and backend.requires_account:
        return False
    if (
        constraints["allowed_platforms"]
        and backend.platform.lower() not in constraints["allowed_platforms"]
    ):
        return False
    return True


def capability_rank(
    backend: BackendCapability, constraints: Mapping[str, Any]
) -> tuple[Any, ...]:
    return (
        {"free": 0, "free_quota": 1, "paid": 2}.get(backend.cost, 9),
        {"none": 0, "minutes_to_hours": 1, "hours": 2}.get(backend.queue, 9),
        {"simulator": 0, "qpu": 1, "cloud": 2}.get(backend.kind, 9),
        backend.max_qubits - int(constraints["min_qubits"]),
        backend.id,
    )


def _validated_capability(source: Any) -> BackendCapability:
    if not isinstance(source, Mapping):
        raise RuntimeError("each backend capability must be an object")
    required = {
        "id",
        "platform",
        "name",
        "kind",
        "max_qubits",
        "queue",
        "cost",
        "requires_account",
        "notes",
    }
    missing = sorted(required - set(source))
    if missing:
        raise RuntimeError("backend capability is missing: " + ", ".join(missing))
    if source["kind"] not in _KINDS:
        raise RuntimeError(f"invalid backend kind: {source['kind']}")
    if source["queue"] not in _QUEUES:
        raise RuntimeError(f"invalid backend queue: {source['queue']}")
    if source["cost"] not in _COSTS:
        raise RuntimeError(f"invalid backend cost: {source['cost']}")
    maximum = source["max_qubits"]
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise RuntimeError("backend max_qubits must be a positive integer")
    if not isinstance(source["requires_account"], bool):
        raise RuntimeError("backend requires_account must be boolean")
    text_fields = ("id", "platform", "name", "notes")
    if any(
        not isinstance(source[field], str) or not source[field].strip()
        for field in text_fields
    ):
        raise RuntimeError("backend text fields must be non-empty strings")
    return BackendCapability(
        id=source["id"],
        platform=source["platform"],
        name=source["name"],
        kind=source["kind"],
        max_qubits=maximum,
        queue=source["queue"],
        cost=source["cost"],
        requires_account=source["requires_account"],
        notes=source["notes"],
    )


def _first(
    source: Mapping[str, Any], *names: str, default: Any
) -> Any:
    for name in names:
        if name in source and source[name] is not None:
            return source[name]
    return default


def _bool_value(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0", ""}:
            return False
    raise ValueError(f"{field} must be boolean")
