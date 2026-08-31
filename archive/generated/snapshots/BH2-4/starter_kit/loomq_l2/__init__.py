"""L2 智能体入口：agent_chat 编排（意图→确定性执行→本地验证→修复回路→兜底）。

铁律：LLM 只产出结构化意图 JSON，电路一律由模板库确定性生成并本地验证。
"""

from __future__ import annotations

import json
import re
import time
from typing import Dict, Optional

try:
    from . import prompts, repair as repair_mod, selector, templates, validate
except ImportError:  # pragma: no cover
    from loomq_l2 import prompts, repair as repair_mod, selector, templates, validate  # type: ignore

try:
    import llm_client
except ImportError:  # pragma: no cover
    from starter_kit import llm_client  # type: ignore

CASE_BUDGET_SECONDS = 110.0  # 给评测 120s 留余量
_INTENT_MAX_TOKENS = 700


def _llm_call(messages: list, max_tokens: int) -> str:
    response = llm_client.chat_completion(messages, max_tokens=max_tokens)
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("LLM 响应缺少 choices/content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM 返回空 content")
    return content


def _parse_json_object(text: str) -> Dict:
    """标准库容错解析：剥围栏、找首个平衡 JSON 对象。"""
    cleaned = re.sub(r"```[a-zA-Z]*", "", text).replace("```", "")
    start = cleaned.find("{")
    if start < 0:
        raise ValueError("输出中未找到 JSON 对象")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(cleaned[start:])
    if not isinstance(obj, dict):
        raise ValueError("JSON 不是对象")
    return obj


def _intent_once(user_prompt: str, error: Optional[dict] = None) -> Dict:
    if error is None:
        messages = prompts.intent_messages(user_prompt)
    else:
        messages = prompts.repair_messages(user_prompt, error)
    raw = _llm_call(messages, _INTENT_MAX_TOKENS)
    return _parse_json_object(raw)


def _clamp_n(value, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _params_from(intent: Dict) -> Dict:
    ones = intent.get("ones")
    if isinstance(ones, list):
        ones = [int(o) for o in ones if isinstance(o, (int, float, str)) and str(o).isdigit()]
    else:
        ones = []
    return {"n_qubits": intent.get("n_qubits"), "ones": ones}


_TEMPLATE_DEFAULT_N = {"bell": 2, "ghz": 3, "uniform": 3, "basis": 2, "w": 3}

_TEMPLATE_EXPLAIN = {
    "bell": "H 门把第一个比特变成叠加态，再用 CX 门把它和第二个比特纠缠起来",
    "ghz": "先让第一个比特叠加，再用一串 CX 把纠缠传递给每一个比特",
    "uniform": "对每个比特施加 H 门，让所有可能的出现机会完全均等",
    "basis": "用 X 门把需要为 1 的比特翻转，得到确定的基矢态",
    "w": "用受控旋转把唯一的激发逐步分配到每个比特上，形成恰好一个 1 的叠加",
}


def _generation_reply(template: str, n: int, qasm: str, fallback: bool) -> str:
    note = "" if not fallback else "\n（说明：按模板默认参数生成。）"
    explain = _TEMPLATE_EXPLAIN.get(template, "")
    return ("好的，已为你生成 %d 比特的 %s 电路：\n\n```qasm\n%s```\n\n"
            "原理：%s。%s" % (n, template, qasm, explain, note)).strip()


def _run_generate(intent: Dict, user_prompt: str, deadline: float) -> str:
    template = intent.get("template")
    if template not in templates.TEMPLATES:
        template = "ghz"
    error: Optional[dict] = None
    for attempt in range(3):
        params = _params_from(intent)
        default_n = _TEMPLATE_DEFAULT_N[template]
        params["n_qubits"] = _clamp_n(params.get("n_qubits"), default_n, 1, 10)
        try:
            qasm, expect = templates.build(template, params)
            ok, error = validate.validate_qasm(qasm, expect)
        except ValueError as exc:
            ok, error = False, {"stage": "template", "detail": str(exc)}
        if ok:
            return _generation_reply(template, params["n_qubits"], qasm, fallback=False)
        if attempt < 2 and time.monotonic() + 25 < deadline:
            try:
                intent = _intent_once(user_prompt, error)
            except Exception:
                break
            new_template = intent.get("template")
            if new_template in templates.TEMPLATES:
                template = new_template
        else:
            break
    qasm, _ = templates.build(template, {"n_qubits": _TEMPLATE_DEFAULT_N[template]})
    return _generation_reply(template, _TEMPLATE_DEFAULT_N[template], qasm, fallback=True)


def _run_fix(intent: Dict, user_prompt: str) -> str:
    template = intent.get("template")
    if template not in templates.TEMPLATES:
        template = "bell"
    params = _params_from(intent)
    params["n_qubits"] = _clamp_n(params.get("n_qubits"), _TEMPLATE_DEFAULT_N[template], 1, 10)
    _, expect = templates.build(template, params)
    code = intent.get("broken_qasm") or repair_mod.extract_code_from_prompt(user_prompt)
    if not code:
        qasm, _ = templates.build(template, params)
        return ("没有在你的消息里找到量子代码，我按你声明的目标态重新生成了一份：\n\n"
                "```qasm\n%s```" % qasm)
    fixed, notes = repair_mod.normalize_user_qasm(code)
    ok, error = validate.validate_qasm(fixed, expect)
    if ok:
        note_text = "\n".join("- " + n for n in notes) or "- 原代码基本正确，已补全格式"
        return ("已按你声明的目标态修复，修复内容：\n%s\n\n修复后的代码：\n\n"
                "```qasm\n%s```" % (note_text, fixed))
    qasm, _ = templates.build(template, params)
    return ("你提供的代码与你声明的目标态不一致（本地验证：%s %s），"
            "我按声明意图重建了电路：\n\n```qasm\n%s```"
            % (error.get("stage"), error.get("detail"), qasm))


def agent_chat(prompt: str) -> str:
    """L2 入口：一次意图调用 + 确定性执行 + 本地验证。"""
    deadline = time.monotonic() + CASE_BUDGET_SECONDS
    last_error = None
    for _ in range(2):  # 空 content/坏 JSON 自动重试一次
        try:
            intent = _intent_once(prompt)
            break
        except Exception as exc:
            last_error = exc
            intent = None
        if time.monotonic() + 30 > deadline:
            break
    if intent is None:
        raise RuntimeError("意图解析失败：%s" % last_error)
    task = intent.get("task")
    if task == "select":
        constraints = intent.get("constraints") or {}
        return selector.format_selection(prompt, constraints)
    if task == "fix":
        return _run_fix(intent, prompt)
    if task == "chat":
        return ("我是 LoomQ 量子助手，可以帮你：用大白话生成量子电路（如 Bell、GHZ、"
                "W 态、均匀叠加）、修复出错的量子代码、或根据比特数和排队需求推荐"
                "运行平台。直接告诉我你想做什么就行。")
    return _run_generate(intent, prompt, deadline)


__all__ = ["agent_chat"]
