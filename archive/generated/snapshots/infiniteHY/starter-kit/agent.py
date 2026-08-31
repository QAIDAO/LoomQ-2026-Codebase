#!/usr/bin/env python3
"""LoomQ L2 — Agent 实现。"""
from __future__ import annotations
import json, os, re, pathlib
from llm_client import chat_completion

_CAPS_PATH = pathlib.Path(__file__).parent / "backend_capabilities.json"
def _load_backends() -> list:
    with open(_CAPS_PATH, encoding="utf-8") as f:
        return json.load(f)["backends"]

BACKENDS = _load_backends()
BACKENDS_JSON_STR = json.dumps(BACKENDS, ensure_ascii=False, indent=2)

_SYSTEM_PROMPT = f"""你是 LoomQ 量子计算助手，帮助用户使用标准 OpenQASM 2.0 量子电路语言。

你只支持以下 12 个门（白名单）：h, x, s, sdg, t, tdg, rz(θ), ry(θ), cx, cu1(θ), swap, ccx
你必须使用 OPENQASM 2.0 格式，包含 include "qelib1.inc"。

规范后端标识（选后端时必须原文引用）：
{BACKENDS_JSON_STR}

## 任务处理规则

### 任务A：自然语言生成 QASM
- 输出完整可运行的 OpenQASM 2.0 代码块（用 ```qasm ... ``` 包裹）。
- 同时用一句话说明电路用途。

### 任务B：代码纠错
- 分析错误，在保持声明意图的前提下修复。
- 输出修复后的完整 QASM（用 ```qasm ... ``` 包裹）。

### 任务C：智能选后端
- 根据约束对照后端能力表筛选。
- 回复中必须包含规范后端标识原文（如 braket_local_simulator）。
- 无满足条件时如实说明并给出最接近替代。
"""

_GEN_KEYWORDS = re.compile(r'生成|创建|写.*电路|制备|制造|构建|generate|create|write.*circuit|prepare', re.IGNORECASE)
_FIX_KEYWORDS = re.compile(r'修复|修正|纠错|纠正|报错|错误|fix|correct|repair|debug|error', re.IGNORECASE)
_BACKEND_KEYWORDS = re.compile(r'选.*后端|推荐.*平台|哪.*平台|哪.*后端|用哪|recommend.*backend|which.*platform|backend', re.IGNORECASE)

def _classify_task(prompt: str) -> str:
    if _FIX_KEYWORDS.search(prompt): return "fix"
    if _BACKEND_KEYWORDS.search(prompt): return "backend"
    if _GEN_KEYWORDS.search(prompt): return "generate"
    return "general"

def _has_valid_qasm(text: str) -> bool:
    m = re.search(r'OPENQASM\s+2\.0;.*?(?=```|\Z)', text, re.DOTALL)
    if not m: return False
    q = m.group(0)
    return "qreg" in q and ("measure" in q or "MEASURE" in q)

def agent_chat(prompt: str, max_retries: int = 2) -> str:
    task_type = _classify_task(prompt)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    response = chat_completion(messages)
    reply = response["choices"][0]["message"]["content"]
    if task_type in ("generate", "fix"):
        attempt = 0
        while not _has_valid_qasm(reply) and attempt < max_retries:
            attempt += 1
            retry_messages = messages + [
                {"role": "assistant", "content": reply},
                {"role": "user", "content": "请确保回复中包含完整的 OpenQASM 2.0 代码，用 ```qasm ... ``` 代码块包裹，从 OPENQASM 2.0; 开始。"},
            ]
            response = chat_completion(retry_messages)
            reply = response["choices"][0]["message"]["content"]
    return reply
