#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

L1 实现说明：`loomq` 子包（纯标准库）完成 QASM2 解析 → 统一 IR →
三后端 codegen；`run()` 使用本地无噪声状态向量模拟器采样，
满足正式评测"默认禁网"的运行约束。
"""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    from .loomq import parse_qasm, sample_counts, transpile_to
    from . import loomq_l2, loomq_l3
except ImportError:  # 平铺导入（如 python starter_kit/evaluator.py 直接运行）
    from loomq import parse_qasm, sample_counts, transpile_to
    import loomq_l2
    import loomq_l3

SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def _check_target(target: str) -> None:
    if target not in SUPPORTED_TARGETS:
        raise ValueError("未知目标 %r，支持：%s" % (target, ", ".join(SUPPORTED_TARGETS)))


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    _check_target(target)
    circuit = parse_qasm(qasm_str)
    return transpile_to(circuit, target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    _check_target(target)
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots 必须为正整数")
    circuit = parse_qasm(qasm_str)
    counts = sample_counts(circuit, shots)
    digest = hashlib.sha256(
        ("%s|%s|%d|" % (target, shots, circuit.op_count())).encode("utf-8")
        + qasm_str.encode("utf-8")
    ).hexdigest()[:16]
    return {
        "backend": "%s_local_statevector" % target,
        "job_id": "loomq-%s" % digest,
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "engine": "loomq_statevector_v1",
            "qubits": circuit.n_qubits,
            "clbits": circuit.n_clbits,
            "gate_count": circuit.op_count(),
        },
    }


def agent_chat(prompt: str) -> str:
    """L2 entry point using the documented LOOMQ_LLM_* environment."""
    return loomq_l2.agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """L3 entry point. Return quantum operations and RISC-V assembly."""
    return loomq_l3.compile_hybrid(hybrid_qasm_str)
