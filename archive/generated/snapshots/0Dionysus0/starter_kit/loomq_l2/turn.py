"""One user turn → structured payload for CLI / web."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from loomq_l2.agent import (
    explain,
    extract_backend_id,
    extract_qasm,
    last_verification,
    looks_like_task,
    model_call_failures,
    model_calls_made,
)
from loomq_l2.tasks import resolve_task_prompt
from loomq_l2.viz import counts_bar_chart


def env_ready() -> Dict[str, Any]:
    missing = [
        name
        for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")
        if not os.environ.get(name)
    ]
    if missing:
        return {
            "ok": False,
            "missing": missing,
            "message": (
                "还不能开始对话：缺少模型配置 "
                + ", ".join(missing)
                + "。请设置 LOOMQ_LLM_BASE_URL / LOOMQ_LLM_API_KEY / LOOMQ_LLM_MODEL（不要写进仓库）。"
            ),
        }
    return {"ok": True, "missing": [], "message": "模型配置已就绪。"}


def plain_error(exc: BaseException) -> str:
    text = str(exc)
    if "missing required LoomQ L2 environment variable" in text:
        return env_ready()["message"] + f"\n技术细节：{text}"
    if "unreachable" in text.lower() or "HTTP" in text:
        return (
            "模型服务暂时连不上。请检查网络/代理和 LOOMQ_LLM_BASE_URL，然后重试。\n"
            f"技术细节：{text}"
        )
    return f"出了点问题，可以换个说法或点任务 1 再试。\n技术细节：{type(exc).__name__}: {text}"


def provenance() -> Dict[str, Any]:
    """Where the answer that was just produced actually came from.

    The UI shows this next to every reply so a beginner can tell a verified
    circuit apart from a guess the self-check could not clear.
    """
    calls = model_calls_made()
    verification = last_verification()
    status = verification.get("status") if verification else None
    fidelity = verification.get("fidelity") if verification else None

    if calls == 0:
        level, label = "degraded", "模型未连上 · 由本地规则算出"
    elif status == "passed":
        level = "verified"
        label = "模型生成 · 已通过本地验证"
        if fidelity is not None:
            label += f"（吻合度 {fidelity:.2f}）"
    elif status == "failed":
        level = "failed"
        label = "模型生成 · 未通过验证，助手已声明没做对"
        if fidelity is not None:
            label += f"（吻合度 {fidelity:.2f}）"
    elif status == "unverified":
        level, label = "unverified", "模型生成 · 助手无法验证，请自行核对"
    else:
        level, label = "model", "模型生成"

    return {
        "level": level,
        "label": label,
        "model_calls": calls,
        "call_failures": model_call_failures(),
        "verification": verification,
    }


def run_explain_turn(question: str, context: str = "") -> Dict[str, Any]:
    """A teaching answer, for questions that are not one of the three tasks."""
    out: Dict[str, Any] = {
        "input": question.strip(),
        "mode": "explain",
        "reply": "",
        "error": None,
        "ok": False,
        "provenance": None,
    }
    try:
        reply = explain(question, context)
    except Exception as exc:  # noqa: BLE001
        out["error"] = plain_error(exc)
        out["provenance"] = provenance()
        return out
    out["reply"] = reply.strip()
    out["provenance"] = provenance()
    out["ok"] = True
    return out


def run_free_question(question: str, context: str = "", *, shots: int = 1024) -> Dict[str, Any]:
    """Route a free-form question to the circuit agent or to the explainer.

    Routing is a local heuristic so that deciding never costs a model call.
    """
    if looks_like_task(question) is not None:
        result = run_user_turn(question, auto_run=True, shots=shots)
        result["mode"] = "task"
        return result
    return run_explain_turn(question, context)


def run_user_turn(
    user_text: str,
    *,
    auto_run: bool = True,
    shots: int = 1024,
    run_target: str = "braket",
) -> Dict[str, Any]:
    """Execute one beginner turn. Never raises for normal agent/run failures."""
    import adapter

    prompt = resolve_task_prompt(user_text)
    out: Dict[str, Any] = {
        "input": user_text.strip(),
        "prompt": prompt,
        "reply": "",
        "qasm": None,
        "backend_id": None,
        "counts": None,
        "run_backend": None,
        "shots": shots,
        "chart_text": None,
        "error": None,
        "ok": False,
        "provenance": None,
    }
    try:
        reply = adapter.agent_chat(prompt)
    except Exception as exc:  # noqa: BLE001
        out["error"] = plain_error(exc)
        out["provenance"] = provenance()
        return out

    out["reply"] = reply.strip()
    out["qasm"] = extract_qasm(reply)
    out["backend_id"] = extract_backend_id(reply)
    out["provenance"] = provenance()
    out["ok"] = True

    if out["qasm"] and auto_run:
        try:
            result = adapter.run(out["qasm"], run_target, shots)
            out["counts"] = result.get("counts") or {}
            out["run_backend"] = result.get("backend")
            out["chart_text"] = counts_bar_chart(out["counts"])
        except Exception as exc:  # noqa: BLE001
            out["error"] = (
                "电路已生成，但本地试跑失败。可以请助手修好电路，或改点任务 1。\n"
                f"技术细节：{type(exc).__name__}: {exc}"
            )
    return out
