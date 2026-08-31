#!/usr/bin/env python3
"""LoomQ 提交适配器协议 v1.0.
L1 作为一个简单的任务分发器，而真正的核心工作（解析器, IR和模拟器）在loomq/目录下
架构说明载于 loomq/__init__.py
无论是哪种target，底层的语法解析、量子门逻辑和数学计算都可以通用。
通过transpile() 和 run() 根据具体的target调用所对应的emit() 和 execute(),没有任何复杂的区分逻辑。
"""

from typing import Any, Dict, List, Tuple

try:
    from .loomq.qasm import parse_qasm2
    from .loomq.targets import TARGETS
    from .loomq import hybrid
except ImportError:  # 直接在 starter_kit/ 目录里当脚本跑，不是以包的形式跑
    from loomq.qasm import parse_qasm2
    from loomq.targets import TARGETS
    from loomq import hybrid


SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def _target_module(target: str):
    try:
        return TARGETS[target]
    except KeyError:
        raise ValueError(f"unknown target '{target}', expected one of {SUPPORTED_TARGETS}") from None


def transpile(qasm_str: str, target: str) -> str:
    """将 OpenQASM 2.0 转译为目标后端的原生表示。"""
    module = _target_module(target)
    circuit = parse_qasm2(qasm_str)
    return module.emit(circuit)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """执行电路，返回赛制要求的统一结果 Schema。"""
    module = _target_module(target)
    circuit = parse_qasm2(qasm_str)
    return module.execute(circuit, shots)


def agent_chat(prompt: str) -> str:
    """L2 入口：实现放在 loomq_l2/，避免覆盖协作者的 L1 包 loomq/。"""
    try:
        from .loomq_l2.agent import agent_chat as _agent_chat
    except ImportError:
        from loomq_l2.agent import agent_chat as _agent_chat
    return _agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """[L3 可选] 混合编译入口。返回 (量子操作序列, RISC-V 汇编文本)。"""
    return hybrid.compile_program(hybrid_qasm_str)
