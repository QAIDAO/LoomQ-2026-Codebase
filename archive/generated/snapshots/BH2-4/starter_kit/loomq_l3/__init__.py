"""L3 混合编译入口：compile_hybrid(hybrid_qasm_str) -> (quantum_ops, assembly)。"""

from __future__ import annotations

from typing import List, Tuple

try:
    from . import classic, parser
except ImportError:  # pragma: no cover
    from loomq_l3 import classic, parser  # type: ignore

try:
    from loomq import parse_qasm
except ImportError:  # pragma: no cover
    from starter_kit.loomq import parse_qasm  # type: ignore

from .codegen import compile_classical  # noqa: E402,F401  (相对导入，包内总是可用)


def _ordered_quantum_ops(quantum_text: str, circuit) -> List[dict]:
    """按源码语句顺序输出量子操作描述（测量保持原位置）。

    loomq 解析器把门与测量分开收集；这里按语句流交替还原顺序。
    遇到广播/自定义门展开导致数量对不上时，退化为"门在前、测量在后"。
    """
    ops_iter = iter(circuit.ops)
    measures_iter = iter(circuit.measures)
    ordered: List[dict] = []

    def gate_item():
        op = next(ops_iter)
        return {"op": op.name, "params": list(op.params),
                "qubits": list(op.qubits), "measure": None}

    def measure_item():
        qubit, clbit = next(measures_iter)
        return {"op": "measure", "params": [], "qubits": [qubit],
                "measure": [qubit, clbit]}

    for raw in quantum_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        low = line.lower()
        if low.startswith(("openqasm", "include", "qreg", "creg", "qubit",
                           "bit", "gate", "barrier", "opaque")):
            continue
        try:
            if low.startswith("measure"):
                # 一行可能含多条 measure（整寄存器或逗号分隔）
                statements = [s for s in line.split(";") if "measure" in s]
                for _ in statements:
                    ordered.append(measure_item())
            else:
                for statement in line.split(";"):
                    statement = statement.strip()
                    if statement:
                        ordered.append(gate_item())
        except StopIteration:
            return _fallback_quantum_ops(circuit)
    if sum(1 for item in ordered if item["op"] == "measure") != len(circuit.measures):
        return _fallback_quantum_ops(circuit)
    if sum(1 for item in ordered if item["op"] != "measure") != len(circuit.ops):
        return _fallback_quantum_ops(circuit)
    return ordered


def _fallback_quantum_ops(circuit) -> List[dict]:
    items = [{"op": op.name, "params": list(op.params), "qubits": list(op.qubits),
              "measure": None} for op in circuit.ops]
    items += [{"op": "measure", "params": [], "qubits": [q], "measure": [q, c]}
              for q, c in circuit.measures]
    return items


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[dict], str]:
    quantum_text, classical_text = parser.split_hybrid(hybrid_qasm_str)
    circuit = parse_qasm(quantum_text)
    quantum_ops = _ordered_quantum_ops(quantum_text, circuit)
    stmts = classic.parse_classical(classical_text) if classical_text.strip() else []
    assembly = compile_classical(stmts)
    return quantum_ops, assembly


__all__ = ["compile_hybrid"]
