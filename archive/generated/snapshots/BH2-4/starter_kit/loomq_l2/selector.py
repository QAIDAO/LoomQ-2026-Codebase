"""智能选后端：backend_capabilities.json 确定性过滤，回复必含规范标识原文。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

_CAPS_PATH = Path(__file__).resolve().parent.parent / "backend_capabilities.json"

_QUEUE_NONE = {"none", "no", "零", "无"}


def _load() -> List[Dict]:
    with open(_CAPS_PATH, encoding="utf-8") as handle:
        data = json.load(handle)
    return data["backends"] if isinstance(data, dict) else data


def filter_backends(constraints: Dict) -> List[Dict]:
    """按约束过滤后端。constraints: max_qubits/queue_none/cost_free/kind。"""
    out = []
    for backend in _load():
        if constraints.get("max_qubits") and backend["max_qubits"] < constraints["max_qubits"]:
            continue
        if constraints.get("queue_none") and backend.get("queue") != "none":
            continue
        if constraints.get("cost_free") and backend.get("cost") not in ("free", "free_quota"):
            continue
        kind = constraints.get("kind") or "any"
        if kind in ("qpu", "simulator") and backend.get("kind") != kind:
            continue
        out.append(backend)
    return out


def _closest(constraints: Dict) -> List[Dict]:
    """无完全匹配时：按违反约束数最少排序，返回最接近的候选。"""

    def violations(backend: Dict) -> int:
        count = 0
        if constraints.get("max_qubits") and backend["max_qubits"] < constraints["max_qubits"]:
            count += 1
        if constraints.get("queue_none") and backend.get("queue") != "none":
            count += 1
        if constraints.get("cost_free") and backend.get("cost") not in ("free", "free_quota"):
            count += 1
        return count

    return sorted(_load(), key=violations)[:2]


def format_selection(user_prompt: str, constraints: Dict) -> str:
    matched = filter_backends(constraints)
    if matched:
        ids = ", ".join(b["id"] for b in matched)
        lines = ["根据你的需求，合适的后端有：", ""]
        for backend in matched:
            lines.append("- %s（%s，%d 比特上限，排队 %s，%s）"
                         % (backend["id"], backend["name"], backend["max_qubits"],
                            backend.get("queue", "未知"),
                            "免费" if backend.get("cost") in ("free", "free_quota")
                            else backend.get("cost", "")))
        lines.append("")
        lines.append("推荐首选 %s。可以直接把它的规范标识填进任务配置。" % matched[0]["id"])
        return "\n".join(lines)
    closest = _closest(constraints)
    lines = ["你的全部约束没有完全满足的后端（例如比特数 %s 超出现有能力）。"
             % constraints.get("max_qubits"), "最接近的替代方案：", ""]
    for backend in closest:
        lines.append("- %s（%s，%d 比特上限）"
                     % (backend["id"], backend["name"], backend["max_qubits"]))
    lines.append("")
    lines.append("可以考虑缩减电路规模后使用 %s。" % closest[0]["id"])
    return "\n".join(lines)
