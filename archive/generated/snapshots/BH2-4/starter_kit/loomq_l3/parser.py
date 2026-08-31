"""Hybrid-QASM 切分：classical 块抽出，量子部分交由 loomq 解析。"""

from __future__ import annotations

import re
from typing import Tuple

_CLASSICAL_HEAD = re.compile(r"\bclassical\s*\{")


def split_hybrid(source: str) -> Tuple[str, str]:
    """返回 (去掉 classical 块后的 QASM2 文本, classical 块内部语句文本)。

    classical 块以首个 `classical {` 开始，按配对大括号扫描到对应 `}`。
    """
    match = _CLASSICAL_HEAD.search(source)
    if not match:
        return source, ""
    start_brace = source.index("{", match.start())
    depth = 0
    end = start_brace
    for i in range(start_brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if depth != 0:
        raise SyntaxError("classical 块缺少配对的 }")
    inner = source[start_brace + 1:end]
    quantum = source[:match.start()] + source[end + 1:]
    return quantum, inner
