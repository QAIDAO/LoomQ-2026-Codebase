#!/usr/bin/env python3
"""L2 agent helpers: task routing, backend selection, QASM verify loop."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple


def load_backends(base_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    root = base_dir or os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(root, "backend_capabilities.json")
    with open(path, encoding="utf-8") as handle:
        return list(json.load(handle).get("backends", []))


def classify_task(prompt: str) -> str:
    text = prompt.lower()
    if any(k in text for k in ("选哪个", "选哪", "推荐", "哪个平台", "哪个后端", "which backend", "which platform", "recommend")):
        return "recommend"
    if any(k in text for k in ("修好", "修复", "报错", "错误", "fix", "debug", "broken", "帮我改")):
        return "fix"
    if any(k in text for k in ("生成", "制备", "电路", "ghz", "bell", "grover", "qft", "纠缠", "generate", "create", "prepare")):
        return "generate"
    return "general"


def extract_constraints(prompt: str) -> Dict[str, Any]:
    """Heuristic constraint extraction for backend recommendation."""
    text = prompt.lower()
    constraints: Dict[str, Any] = {}

    m = re.search(r"(\d+)\s*比[特特]", prompt)
    if not m:
        m = re.search(r"(\d+)\s*-?\s*qubit", text)
    if m:
        constraints["min_qubits"] = int(m.group(1))

    if any(k in text for k in ("零排队", "无排队", "不要排队", "no queue", "queue=none", "立即", "马上跑", "不等待")):
        constraints["queue"] = "none"
    if any(k in text for k in ("免费", "零成本", "不想花钱", "不花钱", "free", "no cost", "without paying")):
        constraints["cost_not"] = {"paid"}
    if any(k in text for k in ("真机", "硬件", "qpu", "real chip", "real hardware", "超导")):
        constraints["kind"] = "qpu"
    if any(k in text for k in ("模拟器", "simulator", "本地模拟")):
        constraints["kind_in"] = {"simulator", "cloud"}
        # local preference often implied by zero queue + free
    if any(k in text for k in ("无需账号", "不要账号", "无账号", "no account", "without account")):
        constraints["requires_account"] = False
    return constraints


def filter_backends(backends: List[Dict[str, Any]], constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
    selected = []
    for item in backends:
        if "min_qubits" in constraints and int(item.get("max_qubits", 0)) < int(constraints["min_qubits"]):
            continue
        if constraints.get("queue") == "none" and item.get("queue") != "none":
            continue
        if "cost_not" in constraints and item.get("cost") in constraints["cost_not"]:
            continue
        if "kind" in constraints and item.get("kind") != constraints["kind"]:
            continue
        if "kind_in" in constraints and item.get("kind") not in constraints["kind_in"]:
            continue
        if "requires_account" in constraints and bool(item.get("requires_account")) != bool(constraints["requires_account"]):
            continue
        selected.append(item)
    return selected


def recommend_reply(prompt: str, backends: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    constraints = extract_constraints(prompt)
    matched = filter_backends(backends, constraints)
    ids = [b["id"] for b in matched]
    if not ids:
        # Closest fallback: largest simulator that is free / no queue if possible.
        sims = [b for b in backends if b.get("kind") == "simulator"]
        sims.sort(key=lambda b: int(b.get("max_qubits", 0)), reverse=True)
        tip = sims[0]["id"] if sims else backends[0]["id"]
        text = (
            "按当前约束，官方能力表中没有同时满足全部条件的后端。"
            "建议放宽排队/费用约束，或拆分电路。最接近的替代是 `%s`。"
            % tip
        )
        return text, [tip]
    lines = [
        "根据 LoomQ 官方 backend_capabilities 筛选，满足约束的规范后端标识：",
    ]
    for item in matched:
        lines.append(
            "- `%s`（%s，max_qubits=%s，queue=%s，cost=%s）"
            % (item["id"], item.get("name"), item.get("max_qubits"), item.get("queue"), item.get("cost"))
        )
    lines.append("推荐优先使用：`%s`" % ids[0])
    return "\n".join(lines), ids


def system_prompt_for(task: str) -> str:
    common = (
        "You are LoomQ, a quantum accessibility assistant for non-physicists. "
        "Allowed OpenQASM 2.0 gates only: h,x,s,sdg,t,tdg,rz,ry,cx,cu1,swap,ccx, plus measure. "
        "Always emit complete programs with OPENQASM 2.0;, include \"qelib1.inc\";, qreg, creg, and measurements "
        "inside a ```qasm fence when producing circuits. "
        "Never invent backend ids; only use ids from the provided capability table."
    )
    if task == "recommend":
        return (
            common
            + " For backend selection: include at least one exact backend id string from the table "
            "(e.g. braket_local_simulator). Prefer deterministic matches to constraints."
        )
    if task == "fix":
        return (
            common
            + " The user states a target state/intent. Preserve that intent while fixing syntax "
            "(registers, gate names like h/cx lowercase, measure). Return corrected full QASM."
        )
    if task == "generate":
        return (
            common
            + " Generate a correct circuit for the requested state. "
            "Bell: H q[0]; CX q[0],q[1]; measure. "
            "n-qubit GHZ: H q[0]; CX q[i],q[i+1] for i=0..n-2; measure all."
        )
    return common


def extract_qasm(text: str) -> str:
    if not isinstance(text, str):
        return ""
    fenced = re.search(
        r"```(?:qasm|openqasm)?\s*(OPENQASM\s+2\.0;.*?)```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        return fenced.group(1).strip()
    match = re.search(r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", text, re.DOTALL | re.MULTILINE)
    return match.group(0).strip() if match else ""


def ensure_backend_ids(text: str, ids: List[str]) -> str:
    missing = [i for i in ids if i not in text]
    if not missing:
        return text
    return text.rstrip() + "\n\n规范后端标识: " + ", ".join("`%s`" % i for i in ids) + "\n"
