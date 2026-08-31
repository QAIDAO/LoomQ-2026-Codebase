"""Turn backend capability records into localized, view-ready facts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


QUEUE_LABELS = {
    "zh": {
        "none": "无需排队",
        "minutes_to_hours": "可能等待几分钟到几小时",
        "hours": "通常需要等待数小时",
    },
    "en": {
        "none": "No queue",
        "minutes_to_hours": "May wait minutes to hours",
        "hours": "Usually waits several hours",
    },
}
COST_LABELS = {
    "zh": {"free": "免费", "free_quota": "提供免费额度", "paid": "需要付费"},
    "en": {"free": "Free", "free_quota": "Free quota available", "paid": "Paid"},
}
KIND_LABELS = {
    "zh": {"simulator": "本地模拟器", "qpu": "量子真机", "cloud": "云端服务"},
    "en": {"simulator": "Local simulator", "qpu": "Quantum hardware", "cloud": "Cloud service"},
}


class BackendPresenter:
    """Read the authoritative capability snapshot and localize selected facts."""

    def __init__(self, capabilities_path: Optional[Path] = None):
        self.path = capabilities_path or (
            Path(__file__).resolve().parent.parent / "backend_capabilities.json"
        )
        self.backends = self._load()

    def describe(self, backend_id: str, language: str = "zh") -> Dict[str, Any]:
        record = self.backends.get(backend_id)
        if record is None:
            return {"id": backend_id, "name": backend_id}
        locale = language if language in {"zh", "en"} else "zh"
        requires_account = record["requires_account"]
        return {
            "id": record["id"],
            "name": record.get("name", record["id"]),
            "platform": record["platform"],
            "kind": KIND_LABELS[locale].get(record["kind"], record["kind"]),
            "max_qubits": record["max_qubits"],
            "queue": QUEUE_LABELS[locale].get(record["queue"], record["queue"]),
            "cost": COST_LABELS[locale].get(record["cost"], record["cost"]),
            "account": (
                "需要注册账号"
                if locale == "zh" and requires_account
                else "无需注册账号"
                if locale == "zh"
                else "Account required"
                if requires_account
                else "No account required"
            ),
            "notes": record.get("notes", ""),
        }

    def _load(self) -> Dict[str, Dict[str, Any]]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("unable to load LoomQ backend presentation data") from exc
        return {
            backend["id"]: backend
            for backend in payload.get("backends", [])
            if isinstance(backend, dict) and backend.get("id")
        }
