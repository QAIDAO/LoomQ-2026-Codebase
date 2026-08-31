"""L2 agent: natural language <-> quantum circuits, backed by an LLM.

The model service is configured exclusively through the LOOMQ_LLM_*
environment variables (see l2_policy.json); nothing about the endpoint, key,
or model name is hardcoded here.

Strategy per contest task type:
  1. intent -> QASM 2.0 generation (whitelist gates, always fully measured)
  2. QASM error repair that preserves the user's declared target state
  3. backend selection answered with a canonical id from
     backend_capabilities.json (the official scoring baseline)

After the model replies, any QASM it produced is parsed and executed on the
local reference simulator ("generate -> self-check -> retry" loop). If the
artifact does not parse or cannot run, the error is fed back to the model for
a repair round. Every reply path performs at least one real model call.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from .qasm import parse_qasm2
from .simulator import simulate_counts

try:  # package import (starter_kit.loomq_core.agent)
    from ..llm_client import chat_completion
except ImportError:  # direct import (loomq_core.agent with starter_kit on path)
    try:
        from llm_client import chat_completion  # type: ignore
    except ImportError:  # running inside starter_kit dir
        import sys

        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from llm_client import chat_completion  # type: ignore


_QASM_RE = re.compile(r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", re.DOTALL | re.MULTILINE)

_SYSTEM_PROMPT = """你是 LoomQ 量子助手的内核。用户大多没有量子计算背景，请用简洁的中文回答。

你必须处理三类任务：

1. 【意图生成】用户描述想要的量子态或算法 → 输出完整、可直接运行的 OpenQASM 2.0 程序。
2. 【纠错修复】用户给出报错的 QASM 代码并声明目标态 → 在保持用户意图的前提下修复，输出完整修复版。
3. 【智能选后端】用户给出比特数、排队、成本等约束 → 依据下方后端能力表选出一个最合适的后端。

硬性规则：
- QASM 必须以 `OPENQASM 2.0;` 开头、包含 `include "qelib1.inc";`、qreg/creg 声明和全比特测量。
- 只能使用这 12 个标准门：h, x, s, sdg, t, tdg, rz(θ), ry(θ), cx, cu1(θ), swap, ccx。
- QASM 代码放在 ```qasm 代码块中；一个回答里只放一个完整的 QASM 程序。
- 选后端任务必须包含且只包含一个下表中的规范后端 id（原样写出，不要翻译）。
- 不要编造能力表之外的参数。

后端能力表（评测基准）：
{capabilities}
"""

_MAX_ATTEMPTS = 3


def _capabilities_text() -> str:
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "backend_capabilities.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError:
        return "(capability table unavailable)"
    lines = []
    for backend in data.get("backends", []):
        lines.append(
            "- id={id} | 平台={platform} | 类型={kind} | 最大比特数={max_qubits} | "
            "排队={queue} | 费用={cost} | 需要账号={requires_account} | 备注={notes}".format(
                **backend
            )
        )
    return "\n".join(lines)


def _extract_qasm(text: str) -> Optional[str]:
    match = _QASM_RE.search(text or "")
    return match.group(0).strip() if match else None


def _self_check(qasm: str) -> Optional[str]:
    """Return None if the QASM parses and executes, else an error message."""
    try:
        circuit = parse_qasm2(qasm)
        simulate_counts(circuit, 64)
    except Exception as exc:  # noqa: BLE001 - error text is fed back to the model
        return "%s: %s" % (type(exc).__name__, exc)
    return None


def agent_reply(prompt: str) -> str:
    """Produce the agent response for one user prompt (see adapter.agent_chat)."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("empty prompt")

    system = _SYSTEM_PROMPT.replace("{capabilities}", _capabilities_text())
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    reply = ""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        response = chat_completion(messages)
        reply = response["choices"][0]["message"]["content"]
        qasm = _extract_qasm(reply)
        if qasm is None:
            # Backend-selection answers legitimately contain no QASM.
            return reply
        error = _self_check(qasm)
        if error is None:
            return reply
        if attempt == _MAX_ATTEMPTS:
            break
        messages.append({"role": "assistant", "content": reply})
        messages.append(
            {
                "role": "user",
                "content": (
                    "这段 QASM 在参考模拟器上运行失败：%s。"
                    "请修复并重新输出一个完整可运行的 OpenQASM 2.0 程序。" % error
                ),
            }
        )
    return reply
