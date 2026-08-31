"""Deterministic backend selection using the official capability snapshot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from ..models import BackendSelection


SUPPORTED_CONSTRAINTS = frozenset(
    {"min_qubits", "kind", "queue", "cost", "requires_account", "platform"}
)
SUPPORTED_KINDS = frozenset({"simulator", "qpu", "cloud", "any"})
SUPPORTED_QUEUES = frozenset({"none", "minutes_to_hours", "hours", "any"})
SUPPORTED_COSTS = frozenset({"free", "free_quota", "not_paid", "paid", "any"})


class CapabilityBackendSelector:
    """Filter and rank backends without asking the language model to decide."""

    def __init__(self, capabilities_path: str | Path | None = None) -> None:
        if capabilities_path is None:
            capabilities_path = Path(__file__).resolve().parents[2] / "backend_capabilities.json"
        self._path = Path(capabilities_path)
        self._backends = self._load_backends(self._path)

    def select(
        self, constraints: Dict[str, Any], response_language: str = "zh"
    ) -> BackendSelection:
        if response_language not in {"zh", "en"}:
            raise ValueError("response_language must be zh or en")
        normalized = self._validate_constraints(constraints)
        matches = [
            backend
            for backend in self._backends
            if self._matches(backend, normalized)
        ]
        matches.sort(key=lambda backend: self._rank(backend, normalized))

        if not matches:
            return BackendSelection(
                selected_id=None,
                explanation=(
                    "No backend in the official capability table satisfies all constraints."
                    if response_language == "en"
                    else "官方能力表中没有满足全部约束的后端。"
                ),
                alternatives=self._nearest_alternatives(normalized),
            )

        selected = matches[0]
        return BackendSelection(
            selected_id=selected["id"],
            explanation=self._explain(selected, normalized, response_language),
            alternatives=[backend["id"] for backend in matches[1:]],
        )

    @staticmethod
    def _load_backends(path: Path) -> List[Dict[str, Any]]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("unable to load LoomQ backend capabilities") from exc
        backends = payload.get("backends")
        if not isinstance(backends, list) or not backends:
            raise RuntimeError("LoomQ backend capability list is empty")
        required = {"id", "platform", "kind", "max_qubits", "queue", "cost", "requires_account"}
        for backend in backends:
            if not isinstance(backend, dict) or required - backend.keys():
                raise RuntimeError("invalid LoomQ backend capability entry")
        return backends

    @staticmethod
    def _validate_constraints(constraints: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(constraints, dict):
            raise ValueError("backend constraints must be an object")
        unknown = set(constraints) - SUPPORTED_CONSTRAINTS
        if unknown:
            raise ValueError(
                "unsupported backend constraint(s): " + ", ".join(sorted(unknown))
            )

        normalized = {
            key: value for key, value in constraints.items() if value is not None
        }
        min_qubits = normalized.get("min_qubits")
        if min_qubits is not None:
            if isinstance(min_qubits, bool) or not isinstance(min_qubits, int) or min_qubits <= 0:
                raise ValueError("min_qubits must be a positive integer")

        CapabilityBackendSelector._validate_choice(
            normalized, "kind", SUPPORTED_KINDS
        )
        CapabilityBackendSelector._validate_choice(
            normalized, "queue", SUPPORTED_QUEUES
        )
        CapabilityBackendSelector._validate_choice(
            normalized, "cost", SUPPORTED_COSTS
        )

        requires_account = normalized.get("requires_account")
        if requires_account is not None and not isinstance(requires_account, bool):
            raise ValueError("requires_account must be a boolean")
        platform = normalized.get("platform")
        if platform is not None and (
            not isinstance(platform, str) or not platform.strip()
        ):
            raise ValueError("platform must be a non-empty string")
        if isinstance(platform, str):
            normalized["platform"] = platform.strip().lower()
        return normalized

    @staticmethod
    def _validate_choice(
        constraints: Dict[str, Any], key: str, allowed: Iterable[str]
    ) -> None:
        value = constraints.get(key)
        if value is not None and value not in allowed:
            raise ValueError(
                "%s must be one of: %s" % (key, ", ".join(sorted(allowed)))
            )

    @staticmethod
    def _matches(backend: Dict[str, Any], constraints: Dict[str, Any]) -> bool:
        if backend["max_qubits"] < constraints.get("min_qubits", 0):
            return False
        kind = constraints.get("kind")
        if kind and kind != "any" and backend["kind"] != kind:
            return False
        queue = constraints.get("queue")
        if queue and queue != "any" and backend["queue"] != queue:
            return False
        cost = constraints.get("cost")
        if cost in {"free", "not_paid"} and backend["cost"] not in {"free", "free_quota"}:
            return False
        if cost not in {None, "any", "free", "not_paid"} and backend["cost"] != cost:
            return False
        requires_account = constraints.get("requires_account")
        if requires_account is not None and backend["requires_account"] is not requires_account:
            return False
        platform = constraints.get("platform")
        if platform and backend["platform"].lower() != platform:
            return False
        return True

    @staticmethod
    def _rank(backend: Dict[str, Any], constraints: Dict[str, Any]):
        account_rank = 1 if backend["requires_account"] else 0
        cost_rank = {"free": 0, "free_quota": 1, "paid": 2}.get(backend["cost"], 3)
        queue_rank = {"none": 0, "minutes_to_hours": 1, "hours": 2}.get(backend["queue"], 3)
        headroom = backend["max_qubits"] - constraints.get("min_qubits", 0)
        return account_rank, cost_rank, queue_rank, headroom, backend["id"]

    def _nearest_alternatives(self, constraints: Dict[str, Any]) -> List[str]:
        min_qubits = constraints.get("min_qubits", 0)
        ranked = sorted(
            self._backends,
            key=lambda backend: (
                abs(backend["max_qubits"] - min_qubits),
                -backend["max_qubits"],
                backend["id"],
            ),
        )
        return [backend["id"] for backend in ranked[:2]]

    @staticmethod
    def _explain(
        backend: Dict[str, Any], constraints: Dict[str, Any], language: str
    ) -> str:
        if language == "en":
            facts = ["supports up to %s qubits" % backend["max_qubits"]]
            if constraints.get("kind") not in {None, "any"}:
                facts.append("type is %s" % backend["kind"])
            if constraints.get("queue") not in {None, "any"}:
                facts.append("queue is %s" % backend["queue"])
            if constraints.get("cost") not in {None, "any"}:
                facts.append("cost is %s" % backend["cost"])
            if constraints.get("requires_account") is not None:
                facts.append(
                    "requires an account"
                    if backend["requires_account"]
                    else "does not require an account"
                )
            return "%s satisfies all constraints: %s." % (
                backend["id"],
                ", ".join(facts),
            )
        facts = ["最多支持 %s 比特" % backend["max_qubits"]]
        if constraints.get("kind") not in {None, "any"}:
            facts.append("类型为 %s" % backend["kind"])
        if constraints.get("queue") not in {None, "any"}:
            facts.append("排队属性为 %s" % backend["queue"])
        if constraints.get("cost") not in {None, "any"}:
            facts.append("费用属性为 %s" % backend["cost"])
        if constraints.get("requires_account") is not None:
            facts.append("%s账号" % ("需要" if backend["requires_account"] else "不需要"))
        return "%s（%s）满足全部约束：%s。" % (
            backend.get("name", backend["id"]),
            backend["id"],
            "、".join(facts),
        )
