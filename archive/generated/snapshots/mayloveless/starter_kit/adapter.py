#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This file intentionally contains no scoring implementation. Teams may implement
the functions directly or delegate to another language/runtime with subprocess.
"""

from typing import Any, Dict, List, Tuple

if __package__:
    # 从仓库根目录：import starter_kit.adapter
    from .loomq.parser import parse_qasm
    from .loomq.l2_agent import agent_chat as _l2_agent_chat
    from .loomq.l3 import compile_hybrid_source
    from .loomq.runners import run_braket, run_originq, run_spinq
    from .loomq.serializers import (
        serialize_braket,
        serialize_originq,
        serialize_spinq,
    )
else:
    # 以 starter_kit 为评测根目录：import adapter
    from loomq.parser import parse_qasm
    from loomq.l2_agent import agent_chat as _l2_agent_chat
    from loomq.l3 import compile_hybrid_source
    from loomq.runners import run_braket, run_originq, run_spinq
    from loomq.serializers import (
        serialize_braket,
        serialize_originq,
        serialize_spinq,
    )


SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    serializers = {
        "spinq": serialize_spinq,
        "originq": serialize_originq,
        "braket": serialize_braket,
    }
    try:
        serializer = serializers[target]
    except KeyError as exc:
        raise ValueError(
            "unsupported transpile target %r; expected one of: %s"
            % (target, ", ".join(sorted(serializers)))
        ) from exc
    return serializer(parse_qasm(qasm_str))


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    if target == "spinq":
        return run_spinq(parse_qasm(qasm_str), shots)
    if target == "braket":
        # Adapter 只负责路由；SDK 调用和结果归一化由 Runner 完成。
        return run_braket(parse_qasm(qasm_str), shots)
    if target == "originq":
        return run_originq(parse_qasm(qasm_str), shots)
    raise ValueError(
        "unsupported run target %r; expected one of: %s"
        % (target, ", ".join(SUPPORTED_TARGETS))
    )


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    return _l2_agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    return compile_hybrid_source(hybrid_qasm_str)
