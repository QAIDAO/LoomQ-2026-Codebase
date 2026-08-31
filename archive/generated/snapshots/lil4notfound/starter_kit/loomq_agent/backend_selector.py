"""Deterministic constraint filtering for the official backend capability data."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class BackendSelection:
    constraints: Tuple[str, ...]
    candidates: Tuple[Dict[str, Any], ...]
    alternatives: Tuple[Dict[str, Any], ...]


def select_backends(prompt: str) -> Optional[BackendSelection]:
    lowered = prompt.lower()
    if not re.search(r"后端|平台|模拟器|真机|量子硬件|backend|simulator|qpu", lowered):
        return None
    backends = tuple(
        json.loads((_ROOT / "backend_capabilities.json").read_text(encoding="utf-8"))["backends"]
    )
    width = _requested_width(prompt)
    requires_no_queue = bool(
        re.search(r"零排队|不排队|无需排队|无排队|立即运行|zero[- ]?queue|no queue|without waiting", lowered)
    )
    requires_non_paid = bool(
        re.search(r"免费|不.{0,3}(?:付费|花钱)|不能付费|零费用|零成本|free|no cost", lowered)
    )
    requires_no_account = bool(
        re.search(r"无需.{0,3}账号|不.{0,3}注册|不要账号|无账号|no account|without.{0,8}account", lowered)
    )
    requires_qpu = bool(re.search(r"真实量子|真机|\bqpu\b|real quantum", lowered))
    requires_simulator = not requires_qpu and bool(
        re.search(r"本地|模拟器|\blocal\b|simulator", lowered)
    )
    constraints = []
    if width is not None:
        constraints.append(f"max_qubits>={width}")
    if requires_no_queue:
        constraints.append("queue=none")
    if requires_non_paid:
        constraints.append("cost!=paid")
    if requires_no_account:
        constraints.append("requires_account=false")
    if requires_qpu:
        constraints.append("kind=qpu")
    elif requires_simulator:
        constraints.append("kind=simulator")
    if not constraints:
        return None

    def matches(item: Dict[str, Any], relax_queue: bool = False) -> bool:
        return all(
            (
                width is None or item["max_qubits"] >= width,
                relax_queue or not requires_no_queue or item["queue"] == "none",
                not requires_non_paid or item["cost"] != "paid",
                not requires_no_account or not item["requires_account"],
                not requires_qpu or item["kind"] == "qpu",
                not requires_simulator or item["kind"] == "simulator",
            )
        )

    candidates = tuple(item for item in backends if matches(item))
    alternatives = ()
    if not candidates and requires_no_queue:
        alternatives = tuple(item for item in backends if matches(item, relax_queue=True))
    if not candidates and not alternatives and width is not None:
        compatible = tuple(
            item
            for item in backends
            if (not requires_qpu or item["kind"] == "qpu")
            and (not requires_simulator or item["kind"] == "simulator")
        )
        if compatible:
            maximum = max(item["max_qubits"] for item in compatible)
            alternatives = tuple(item for item in compatible if item["max_qubits"] == maximum)
    return BackendSelection(tuple(constraints), candidates, alternatives)


def selection_context(selection: Optional[BackendSelection]) -> str:
    if selection is None:
        return ""
    ids = [item["id"] for item in selection.candidates]
    return (
        "官方能力表确定性筛选结果：约束="
        + json.dumps(selection.constraints, ensure_ascii=False)
        + "；满足全部约束的规范后端 id="
        + json.dumps(ids, ensure_ascii=False)
        + "。free_quota 属于非付费选项。回答不得违背此筛选结果。"
    )


def format_selection(prompt: str, selection: BackendSelection) -> str:
    chinese = bool(re.search(r"[\u4e00-\u9fff]", prompt))
    if selection.candidates:
        ids = "、".join(f"`{item['id']}`" for item in selection.candidates)
        constraints = "，".join(selection.constraints)
        if chinese:
            return f"满足全部约束（{constraints}）的后端：{ids}。"
        return f"Backends satisfying every constraint ({constraints}): {ids}."
    alternatives = "、".join(f"`{item['id']}`" for item in selection.alternatives)
    if chinese:
        answer = "没有后端满足全部约束。"
        return answer + (f" 放宽一项约束后的替代方案：{alternatives}。" if alternatives else "")
    answer = "No backend satisfies every constraint."
    return answer + (f" Alternatives after relaxing one constraint: {alternatives}." if alternatives else "")


def _requested_width(prompt: str) -> Optional[int]:
    match = re.search(r"(\d+)\s*(?:个\s*)?(?:量子)?比特|(?:\b)(\d+)\s*[- ]?qubits?", prompt, re.I)
    if not match:
        return None
    return int(match.group(1) or match.group(2))
