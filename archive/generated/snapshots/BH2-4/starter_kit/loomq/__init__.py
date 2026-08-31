"""LoomQ 中间层：QASM2 解析 → 统一 IR → 三后端 codegen / 本地模拟。

纯标准库实现，满足正式评测"默认禁网、容器内离线运行"的约束。
"""

from .ir import Circuit, Op, WHITELIST
from .qasm2 import parse_qasm
from .sim import probabilities, sample_counts, simulate
from .codegen import transpile_to

__all__ = [
    "Circuit",
    "Op",
    "WHITELIST",
    "parse_qasm",
    "simulate",
    "probabilities",
    "sample_counts",
    "transpile_to",
]
