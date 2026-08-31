#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This first implementation keeps L1 self-contained: it parses the contest's
OpenQASM 2.0 subset, emits the required target IR strings, and uses a tiny
state-vector simulator for ``run`` so public checks work without SDK installs.
"""

from __future__ import annotations

import ast
import cmath
import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


SUPPORTED_TARGETS = ("spinq", "originq", "braket")
_SINGLE_GATES = {"h", "x", "s", "sdg", "t", "tdg", "rz", "ry"}
_TWO_GATES = {"cx", "cu1", "swap"}
_THREE_GATES = {"ccx"}


@dataclass
class GateOp:
    name: str
    qubits: List[int]
    params: List[float] = field(default_factory=list)


@dataclass
class MeasureOp:
    qubit: int
    cbit: int


@dataclass
class CircuitIR:
    num_qubits: int
    num_cbits: int
    ops: List[GateOp | MeasureOp]


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    ir = _parse_qasm(qasm_str)
    if target == "spinq":
        return _emit_openqasm2(ir)
    if target == "braket":
        return _emit_openqasm3(ir)
    if target == "originq":
        return _emit_originir(ir)
    raise ValueError(f"unsupported target: {target}")


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")

    ir = _parse_qasm(qasm_str)
    counts = _simulate_counts(ir, shots)
    return {
        "backend": _backend_id(target),
        "job_id": f"local-{uuid.uuid4().hex[:12]}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {"transpiled_gates": sum(isinstance(op, GateOp) for op in ir.ops)},
    }


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    try:
        from .l2_agent import agent_chat_impl
    except ImportError:
        from l2_agent import agent_chat_impl

    return agent_chat_impl(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    try:
        from .l3_hybrid_compiler import compile_hybrid_impl
    except ImportError:
        from l3_hybrid_compiler import compile_hybrid_impl

    return compile_hybrid_impl(hybrid_qasm_str)


def _backend_id(target: str) -> str:
    return {
        "spinq": "spinq_taurus_simulator",
        "originq": "originq_local_simulator",
        "braket": "braket_local_simulator",
    }[target]


def _strip_comments(qasm: str) -> str:
    lines = []
    for line in qasm.splitlines():
        lines.append(line.split("//", 1)[0])
    return "\n".join(lines)


def _parse_qasm(qasm: str) -> CircuitIR:
    statements = [stmt.strip() for stmt in _strip_comments(qasm).split(";") if stmt.strip()]
    qregs: Dict[str, int] = {}
    cregs: Dict[str, int] = {}
    ops: List[GateOp | MeasureOp] = []

    for stmt in statements:
        compact = " ".join(stmt.split())
        if re.fullmatch(r"OPENQASM\s+2\.0", compact, re.IGNORECASE):
            continue
        if re.fullmatch(r'include\s+"qelib1\.inc"', compact, re.IGNORECASE):
            continue
        if re.fullmatch(r"barrier\s+.+", compact, re.IGNORECASE):
            continue

        match = re.fullmatch(r"qreg\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]", compact)
        if match:
            name, size = match.group(1), int(match.group(2))
            qregs[name] = size
            continue

        match = re.fullmatch(r"creg\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]", compact)
        if match:
            name, size = match.group(1), int(match.group(2))
            cregs[name] = size
            continue

        match = re.fullmatch(
            r"measure\s+([A-Za-z_]\w*)(?:\s*\[\s*(\d+)\s*\])?\s*->\s*"
            r"([A-Za-z_]\w*)(?:\s*\[\s*(\d+)\s*\])?",
            compact,
        )
        if match:
            qname, qindex, cname, cindex = match.groups()
            if qindex is None and cindex is None:
                _require_register(qregs, qname, "qreg")
                _require_register(cregs, cname, "creg")
                if qregs[qname] != cregs[cname]:
                    raise ValueError("whole-register measurement requires equal register sizes")
                for idx in range(qregs[qname]):
                    ops.append(MeasureOp(idx, idx))
            elif qindex is not None and cindex is not None:
                qubit = _parse_index(qregs, qname, qindex, "qreg")
                cbit = _parse_index(cregs, cname, cindex, "creg")
                ops.append(MeasureOp(qubit, cbit))
            else:
                raise ValueError(f"unsupported measurement form: {stmt}")
            continue

        gate = _parse_gate(compact, qregs)
        if gate is not None:
            ops.append(gate)
            continue

        raise ValueError(f"unsupported OpenQASM statement: {stmt}")

    if len(qregs) != 1:
        raise ValueError("exactly one qreg is supported")
    if len(cregs) != 1:
        raise ValueError("exactly one creg is supported")
    return CircuitIR(next(iter(qregs.values())), next(iter(cregs.values())), ops)


def _parse_gate(stmt: str, qregs: Dict[str, int]) -> GateOp | None:
    match = re.fullmatch(r"([A-Za-z_]\w*)(?:\s*\((.*)\))?\s+(.+)", stmt)
    if not match:
        return None
    name = match.group(1).lower()
    params_text = match.group(2)
    qubit_text = match.group(3)
    qubits = [_parse_qubit_ref(part.strip(), qregs) for part in qubit_text.split(",")]
    params = [] if params_text is None else [_parse_angle(part.strip()) for part in params_text.split(",")]

    if name in _SINGLE_GATES and len(qubits) == 1:
        if name in {"rz", "ry"} and len(params) == 1:
            return GateOp(name, qubits, params)
        if name not in {"rz", "ry"} and not params:
            return GateOp(name, qubits, params)
    if name in _TWO_GATES and len(qubits) == 2:
        if name == "cu1" and len(params) == 1:
            return GateOp(name, qubits, params)
        if name != "cu1" and not params:
            return GateOp(name, qubits, params)
    if name in _THREE_GATES and len(qubits) == 3 and not params:
        return GateOp(name, qubits, params)
    raise ValueError(f"unsupported gate signature: {stmt}")


def _parse_qubit_ref(text: str, qregs: Dict[str, int]) -> int:
    match = re.fullmatch(r"([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]", text)
    if not match:
        raise ValueError(f"invalid qubit reference: {text}")
    return _parse_index(qregs, match.group(1), match.group(2), "qreg")


def _parse_index(regs: Dict[str, int], name: str, raw_index: str, kind: str) -> int:
    _require_register(regs, name, kind)
    index = int(raw_index)
    if not 0 <= index < regs[name]:
        raise ValueError(f"{kind} index out of range: {name}[{index}]")
    return index


def _require_register(regs: Dict[str, int], name: str, kind: str) -> None:
    if name not in regs:
        raise ValueError(f"unknown {kind}: {name}")


def _parse_angle(expr: str) -> float:
    node = ast.parse(expr, mode="eval")
    return float(_eval_angle_node(node.body))


def _eval_angle_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id == "pi":
        return math.pi
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval_angle_node(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = _eval_angle_node(node.left)
        right = _eval_angle_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right
    raise ValueError("unsupported angle expression")


def _format_angle(value: float) -> str:
    return f"{value:.15g}"


def _emit_openqasm2(ir: CircuitIR) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{ir.num_qubits}];",
        f"creg c[{ir.num_cbits}];",
    ]
    for op in ir.ops:
        if isinstance(op, GateOp):
            lines.append(_emit_qasm2_gate(op))
        else:
            lines.append(f"measure q[{op.qubit}] -> c[{op.cbit}];")
    return "\n".join(lines) + "\n"


def _emit_qasm2_gate(op: GateOp) -> str:
    args = ",".join(f"q[{q}]" for q in op.qubits)
    if op.params:
        params = ",".join(_format_angle(param) for param in op.params)
        return f"{op.name}({params}) {args};"
    return f"{op.name} {args};"


def _emit_openqasm3(ir: CircuitIR) -> str:
    gate_names = {"cx": "cnot"}
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        f"qubit[{ir.num_qubits}] q;",
        f"bit[{ir.num_cbits}] c;",
    ]
    measures: List[MeasureOp] = []
    for op in ir.ops:
        if isinstance(op, GateOp):
            name = gate_names.get(op.name, op.name)
            args = ", ".join(f"q[{q}]" for q in op.qubits)
            if op.params:
                params = ", ".join(_format_angle(param) for param in op.params)
                lines.append(f"{name}({params}) {args};")
            else:
                lines.append(f"{name} {args};")
        else:
            measures.append(op)
    if _is_whole_register_measurement(measures, ir):
        lines.append("c = measure q;")
    else:
        for op in measures:
            lines.append(f"c[{op.cbit}] = measure q[{op.qubit}];")
    return "\n".join(lines) + "\n"


def _emit_originir(ir: CircuitIR) -> str:
    names = {
        "h": "H",
        "x": "X",
        "s": "S",
        "sdg": "SDAG",
        "t": "T",
        "tdg": "TDAG",
        "rz": "RZ",
        "ry": "RY",
        "cx": "CNOT",
        "cu1": "CU1",
        "swap": "SWAP",
        "ccx": "TOFFOLI",
    }
    lines = [f"QINIT {ir.num_qubits}", f"CREG {ir.num_cbits}"]
    for op in ir.ops:
        if isinstance(op, GateOp):
            name = names[op.name]
            args = ", ".join(f"q[{q}]" for q in op.qubits)
            if op.params:
                lines.append(f"{name}({_format_angle(op.params[0])}) {args}")
            else:
                lines.append(f"{name} {args}")
        else:
            lines.append(f"MEASURE q[{op.qubit}], c[{op.cbit}]")
    return "\n".join(lines) + "\n"


def _is_whole_register_measurement(measures: List[MeasureOp], ir: CircuitIR) -> bool:
    return (
        ir.num_qubits == ir.num_cbits
        and len(measures) == ir.num_qubits
        and all(measure.qubit == idx and measure.cbit == idx for idx, measure in enumerate(measures))
    )


def _simulate_counts(ir: CircuitIR, shots: int) -> Dict[str, int]:
    state = [0j] * (1 << ir.num_qubits)
    state[0] = 1 + 0j
    measures: List[MeasureOp] = []
    for op in ir.ops:
        if isinstance(op, GateOp):
            _apply_gate(state, ir.num_qubits, op)
        else:
            measures.append(op)

    if not measures:
        measures = [MeasureOp(i, i) for i in range(min(ir.num_qubits, ir.num_cbits))]

    probabilities: Dict[str, float] = {}
    for basis, amplitude in enumerate(state):
        probability = abs(amplitude) ** 2
        if probability < 1e-12:
            continue
        cbits = ["0"] * ir.num_cbits
        for measure in measures:
            bit = (basis >> measure.qubit) & 1
            cbits[measure.cbit] = str(bit)
        key = "".join(reversed(cbits))
        probabilities[key] = probabilities.get(key, 0.0) + probability

    total = sum(probabilities.values())
    if total <= 0:
        raise ValueError("simulation produced no probability mass")
    probabilities = {key: value / total for key, value in probabilities.items()}

    counts = {key: int(math.floor(value * shots)) for key, value in probabilities.items()}
    remainder = shots - sum(counts.values())
    ranked = sorted(probabilities, key=lambda key: (probabilities[key] * shots - counts[key]), reverse=True)
    for key in ranked[:remainder]:
        counts[key] += 1
    return {key: value for key, value in sorted(counts.items()) if value > 0}


def _apply_gate(state: List[complex], num_qubits: int, op: GateOp) -> None:
    if op.name == "h":
        factor = 1 / math.sqrt(2)
        _apply_single(state, op.qubits[0], ((factor, factor), (factor, -factor)))
    elif op.name == "x":
        _apply_single(state, op.qubits[0], ((0, 1), (1, 0)))
    elif op.name == "s":
        _apply_single(state, op.qubits[0], ((1, 0), (0, 1j)))
    elif op.name == "sdg":
        _apply_single(state, op.qubits[0], ((1, 0), (0, -1j)))
    elif op.name == "t":
        _apply_single(state, op.qubits[0], ((1, 0), (0, cmath.exp(1j * math.pi / 4))))
    elif op.name == "tdg":
        _apply_single(state, op.qubits[0], ((1, 0), (0, cmath.exp(-1j * math.pi / 4))))
    elif op.name == "rz":
        theta = op.params[0]
        _apply_single(state, op.qubits[0], ((cmath.exp(-0.5j * theta), 0), (0, cmath.exp(0.5j * theta))))
    elif op.name == "ry":
        theta = op.params[0]
        c = math.cos(theta / 2)
        s = math.sin(theta / 2)
        _apply_single(state, op.qubits[0], ((c, -s), (s, c)))
    elif op.name == "cx":
        _apply_controlled_x(state, op.qubits[0], op.qubits[1])
    elif op.name == "cu1":
        _apply_cu1(state, op.qubits[0], op.qubits[1], op.params[0])
    elif op.name == "swap":
        _apply_swap(state, op.qubits[0], op.qubits[1])
    elif op.name == "ccx":
        _apply_ccx(state, op.qubits[0], op.qubits[1], op.qubits[2])
    else:
        raise ValueError(f"unsupported gate in simulator: {op.name}")


def _apply_single(state: List[complex], qubit: int, matrix: Tuple[Tuple[complex, complex], Tuple[complex, complex]]) -> None:
    step = 1 << qubit
    span = step << 1
    for base in range(0, len(state), span):
        for offset in range(step):
            i0 = base + offset
            i1 = i0 + step
            a0 = state[i0]
            a1 = state[i1]
            state[i0] = matrix[0][0] * a0 + matrix[0][1] * a1
            state[i1] = matrix[1][0] * a0 + matrix[1][1] * a1


def _apply_controlled_x(state: List[complex], control: int, target: int) -> None:
    control_mask = 1 << control
    target_mask = 1 << target
    for basis in range(len(state)):
        if basis & control_mask and not basis & target_mask:
            other = basis | target_mask
            state[basis], state[other] = state[other], state[basis]


def _apply_cu1(state: List[complex], control: int, target: int, theta: float) -> None:
    mask = (1 << control) | (1 << target)
    phase = cmath.exp(1j * theta)
    for basis in range(len(state)):
        if (basis & mask) == mask:
            state[basis] *= phase


def _apply_swap(state: List[complex], q0: int, q1: int) -> None:
    if q0 == q1:
        return
    mask0 = 1 << q0
    mask1 = 1 << q1
    for basis in range(len(state)):
        bit0 = bool(basis & mask0)
        bit1 = bool(basis & mask1)
        if bit0 != bit1 and not bit0:
            other = basis ^ mask0 ^ mask1
            state[basis], state[other] = state[other], state[basis]


def _apply_ccx(state: List[complex], control0: int, control1: int, target: int) -> None:
    controls = (1 << control0) | (1 << control1)
    target_mask = 1 << target
    for basis in range(len(state)):
        if (basis & controls) == controls and not basis & target_mask:
            other = basis | target_mask
            state[basis], state[other] = state[other], state[basis]
