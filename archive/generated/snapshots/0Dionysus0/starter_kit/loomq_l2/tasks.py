"""Shared field-experience tasks for CLI and web L2 entry."""

from __future__ import annotations

from typing import List, Tuple

# (id, short title, full prompt sent to agent_chat)
STARTER_TASKS: List[Tuple[str, str, str]] = [
    (
        "1",
        "扔一枚「量子硬币」",
        "请做一个单比特均匀叠加态电路并测量。用普通人能懂的话先解释会看到什么，再给出完整 OpenQASM 2.0。",
    ),
    (
        "2",
        "看三比特纠缠长什么样",
        "生成一个 3 比特 GHZ 态并进行全测量。解释条形图上为什么几乎只有两种结果。",
    ),
    (
        "3",
        "不会选平台时问助手",
        "我需要运行一个 15 比特电路，且零排队等待、尽量免费，选哪个平台？请给出规范后端 id。",
    ),
]


def resolve_task_prompt(raw: str) -> str:
    text = raw.strip()
    for num, _title, prompt in STARTER_TASKS:
        if text == num:
            return prompt
    return text


def tasks_as_dicts() -> list:
    return [
        {"id": num, "title": title, "prompt": prompt}
        for num, title, prompt in STARTER_TASKS
    ]
