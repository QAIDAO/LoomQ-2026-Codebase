"""Backend selection helpers for LoomQ Lab."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_backends() -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parents[2] / "backend_capabilities.json"
    return json.loads(path.read_text(encoding="utf-8"))["backends"]


def recommend(prompt: str) -> list[dict[str, Any]]:
    qubits = 1
    for token in prompt.replace("，", " ").replace(",", " ").split():
        if token.isdigit():
            qubits = int(token)
            break

    wants_no_queue = any(word in prompt for word in ("零排队", "无排队", "不用排队", "不要排队", "不排队", "不想排队"))
    wants_free = any(word in prompt for word in ("免费", "不花钱", "不要付费", "不想付费"))
    wants_qpu = any(word in prompt for word in ("真机", "真实硬件", "真实量子"))
    wants_no_account = any(word in prompt for word in ("不注册", "不用注册", "无需注册", "不要账号", "不用账号", "不想注册"))

    matches = []
    for backend in load_backends():
        if backend["max_qubits"] < qubits:
            continue
        if wants_no_queue and backend["queue"] != "none":
            continue
        if wants_free and backend["cost"] == "paid":
            continue
        if wants_qpu and backend["kind"] != "qpu":
            continue
        if wants_no_account and backend["requires_account"]:
            continue
        matches.append(backend)
    return matches
