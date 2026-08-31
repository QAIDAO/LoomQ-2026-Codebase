"""本地验证器：结构校验 + 精确分布对拍，产出机器可读错误供修复回路回喂。"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from .templates import WHITELIST_GATES
except ImportError:  # pragma: no cover
    from templates import WHITELIST_GATES  # type: ignore

try:
    from loomq import parse_qasm, probabilities, simulate
except ImportError:  # pragma: no cover
    from starter_kit.loomq import parse_qasm, probabilities, simulate  # type: ignore


def hellinger_fidelity(observed: Dict[str, float],
                       expected: Dict[str, float]) -> float:
    states = set(observed) | set(expected)
    distance = math.sqrt(
        sum((math.sqrt(observed.get(s, 0.0)) - math.sqrt(expected.get(s, 0.0))) ** 2
            for s in states)) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - distance))


def validate_qasm(qasm: str, expect: Optional[Dict[str, float]] = None,
                  fidelity_threshold: float = 0.97) -> Tuple[bool, dict]:
    """返回 (通过, 机器可读错误)。expect 为 None 时只做结构校验。"""
    error: Dict = {"stage": None, "detail": None}
    try:
        circuit = parse_qasm(qasm)
    except Exception as exc:
        error.update(stage="parse", detail="%s: %s" % (type(exc).__name__, exc))
        return False, error
    bad = [op.name for op in circuit.ops if op.name not in WHITELIST_GATES]
    if bad:
        error.update(stage="gate_whitelist", detail="非白名单门: %s" % sorted(set(bad)))
        return False, error
    if not circuit.measures:
        error.update(stage="measure_missing", detail="电路缺少测量语句")
        return False, error
    if circuit.n_qubits > 12 or circuit.n_clbits > 12:
        error.update(stage="too_large", detail="比特数超限: %d" % circuit.n_qubits)
        return False, error
    if expect is not None:
        try:
            probs = probabilities(simulate(circuit))
        except Exception as exc:
            error.update(stage="simulate", detail="%s: %s" % (type(exc).__name__, exc))
            return False, error
        got = {format(idx, "0%db" % circuit.n_qubits): p
               for idx, p in enumerate(probs) if p > 1e-12}
        fidelity = hellinger_fidelity(got, expect)
        if fidelity < fidelity_threshold:
            error.update(stage="fidelity",
                         detail="保真度 %.4f 低于 %.2f；实际分布 %s，目标分布 %s"
                                % (fidelity, fidelity_threshold,
                                   _top(got), _top(expect)))
            return False, error
    return True, {"stage": "ok", "detail": None}


def _top(dist: Dict[str, float], k: int = 6) -> str:
    items = sorted(dist.items(), key=lambda kv: -kv[1])[:k]
    return str({key: round(value, 4) for key, value in items})
