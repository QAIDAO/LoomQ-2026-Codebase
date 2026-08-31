#!/usr/bin/env python3
"""Small OpenAI-compatible transport helper for LoomQ L2 entrants.

This module deliberately contains no prompting strategy or scoring logic. Teams
may use it, replace it, or call the same environment-variable contract from any
language.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


REQUIRED_ENV = ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")


def _load_env_file() -> None:
    """变量缺失时，去几个约定位置找一个 .env 补上。已设好的环境变量优先。

    放在这一层是为了让**每个入口**都一致：官方 evaluator.py、adapter.py、
    命令行入口、几个实测脚本，都是经过这里去拿配置的。
    在这里补一次，就不必要求使用者（包括评委）在每条命令前面手写
    `set -a && . ./.env && set +a`——那串东西是纯噪音，还很容易漏。

    正式评测时组委会直接注入环境变量，`envfile.load` 不会覆盖已有值，
    评测容器里也不会有 .env 文件，所以这一步在评测时是空操作。
    """
    try:
        try:
            from .loomq import envfile
        except (ImportError, ValueError):  # 允许把 starter_kit 直接加进 sys.path 使用
            from loomq import envfile  # type: ignore[no-redef]
        envfile.load()
    except Exception:  # noqa: BLE001  找不到就算了，下面照常报"缺变量"
        pass


def _configuration() -> tuple[str, str, str, float, int]:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        _load_env_file()
        missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError("missing required LoomQ L2 environment variable(s): " + ", ".join(missing))
    try:
        timeout = float(os.environ.get("LOOMQ_LLM_TIMEOUT_SECONDS", "120"))
        max_output = int(os.environ.get("LOOMQ_LLM_MAX_OUTPUT_TOKENS", "4096"))
    except ValueError as exc:
        raise RuntimeError("invalid LoomQ L2 numeric environment variable") from exc
    if timeout <= 0 or max_output <= 0:
        raise RuntimeError("LoomQ L2 timeout and output-token limit must be positive")
    return (
        os.environ["LOOMQ_LLM_BASE_URL"].rstrip("/"),
        os.environ["LOOMQ_LLM_API_KEY"],
        os.environ["LOOMQ_LLM_MODEL"],
        timeout,
        max_output,
    )


def chat_completion(messages: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    """Create one non-streaming chat completion using the public L2 contract."""
    base_url, api_key, model, timeout, max_output = _configuration()
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": 0,
        "max_tokens": max_output,
    }
    payload.update(extra)

    # 关掉"思考"模式：我们只要一段 JSON 或一段短正文，思考过程纯属浪费时间和 token。
    #
    # 这个字段不是 OpenAI 协议的标准字段，有的服务认、有的服务会直接报 400。
    # 原先的写法是 `if model == "<某个具体模型名>"` —— 能用，但**违反赛题要求**：
    # 源码里不得出现任何服务地址、密钥或模型名。（这一处是被 verify_l2 第六节
    # 扩大扫描范围之后揪出来的，之前那节只扫 loomq/ 目录，扫不到本文件。）
    #
    # 所以改成不认名字、只看服务端答不答应：先带着这个字段发，
    # 服务端要是嫌它多余就去掉重发一次。这样对任何 OpenAI 协议的服务都成立，
    # 也正好是赛题"换服务不用改代码"那句话的本意。
    try:
        return _post(base_url, api_key, timeout, dict(payload, thinking={"type": "disabled"}))
    except _FieldRejected:
        return _post(base_url, api_key, timeout, payload)


class _FieldRejected(Exception):
    """服务端不认可选字段（HTTP 400），去掉再试一次就好。"""


def _post(base_url: str, api_key: str, timeout: float, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        # 400 一律当成"可选字段不被接受"处理，交给上层去掉重试。
        # 只有重试那一次的 400 才会真的抛出去（那时 payload 里已经没有可选字段了）。
        if exc.code == 400 and "thinking" in payload:
            raise _FieldRejected() from exc
        # 把服务端的说法带上。诊断的时候这句话很值钱——排查网络问题时
        # 就是靠响应体里"x-api-key header is required"才认出那不是地域封锁，
        # 只是没带凭证。（响应体是服务端返回的内容，不含我们的密钥。）
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:200].strip()
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(
            "LoomQ L2 API returned HTTP %d%s" % (exc.code, ("：" + detail) if detail else "")
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("LoomQ L2 API is unreachable: %s" % (exc.reason,)) from exc
