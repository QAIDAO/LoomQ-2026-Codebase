"""从 Circuit IR 生成三个后端的规范 IR 文本。

spinq  → OpenQASM 2.0（含寄存器声明与测量语句）
braket → OpenQASM 3.0（stdgates.inc；cu1 以等价标准名 cp 输出）
originq→ OriginIR 规范子集（QINIT/CREG + 大写门名 + MEASURE）

非白名单门先经恒等式改写到题面 12 门白名单（分布语义不变，允许全局相位差异）。
"""

from __future__ import annotations

from typing import List

from .ir import Circuit, Op, WHITELIST

_pi = 3.141592653589793


def _fmt(x: float) -> str:
    if x == 0.0:
        return "0.0"
    return repr(float(x))


def to_whitelist(circuit: Circuit) -> Circuit:
    """把非白名单门改写为白名单恒等形式；白名单门原样保留。"""
    out_ops: List[Op] = []
    for op in circuit.ops:
        out_ops.extend(_rewrite_op(op))
    return Circuit(
        n_qubits=circuit.n_qubits,
        n_clbits=circuit.n_clbits,
        ops=out_ops,
        measures=list(circuit.measures),
    )


def _rewrite_op(op: Op) -> List[Op]:
    name, params, qubits = op.name, op.params, op.qubits
    if name in WHITELIST:
        return [op]
    if name == "id":
        return []
    if name in ("p", "u1"):
        return [Op("rz", params, qubits)]
    if name == "z":
        return [Op("rz", (_pi,), qubits)]
    if name == "y":
        # X·RZ(π) = -iY，与 Y 分布一致
        return [Op("rz", (_pi,), qubits), Op("x", (), qubits)]
    if name == "rx":
        theta = params[0]
        return [Op("h", (), qubits), Op("ry", (theta,), qubits), Op("h", (), qubits)]
    if name == "sx":
        # sx = e^{iπ/4}·RX(π/2)
        return [Op("h", (), qubits), Op("ry", (_pi / 2,), qubits), Op("h", (), qubits)]
    if name == "cz":
        a, b = qubits
        return [Op("h", (), (b,)), Op("cx", (), (a, b)), Op("h", (), (b,))]
    if name == "cy":
        a, b = qubits
        return [Op("sdg", (), (b,)), Op("cx", (), (a, b)), Op("s", (), (b,))]
    if name in ("cp", "cphase"):
        return [Op("cu1", params, qubits)]
    if name == "crz":
        c, t = qubits
        theta = params[0]
        return [
            Op("rz", (theta / 2,), (t,)),
            Op("cu1", (-theta / 2,), (c, t)),
            Op("rz", (theta / 2,), (t,)),
        ]
    if name in ("u2", "u3", "u"):
        # u3(θ,φ,λ) ≡ RZ(φ)·RY(θ)·RZ(λ)（全局相位无关）；u2(φ,λ) = u3(π/2,φ,λ)
        theta = params[0] if len(params) == 3 else _pi / 2
        phi = params[1] if len(params) >= 2 else 0.0
        lam = params[2] if len(params) == 3 else params[0] if name == "u2" else 0.0
        if name == "u2":
            phi, lam = params[0], params[1]
        return [Op("rz", (phi,), qubits), Op("ry", (theta,), qubits),
                Op("rz", (lam,), qubits)]
    if name == "cu3":
        # 受控 u3：C-RZ(λ)、C-RY(θ)、C-RZ(φ) 逐块分解（cu1 为 C-RZ 的白名单形式）
        c, t = qubits
        theta, phi, lam = params
        return [
            Op("rz", (lam / 2,), (t,)),
            Op("cx", (), (c, t)),
            Op("rz", (-lam / 2,), (t,)),
            Op("cx", (), (c, t)),
            Op("ry", (theta / 2,), (t,)),
            Op("cx", (), (c, t)),
            Op("ry", (-theta / 2,), (t,)),
            Op("cx", (), (c, t)),
            Op("rz", (phi / 2,), (t,)),
            Op("cx", (), (c, t)),
            Op("rz", (-phi / 2,), (t,)),
            Op("cx", (), (c, t)),
        ]
    if name == "ch":
        # H ≡ u3(π/2, 0, π)（全局相位无关），复用 cu3 分解
        c, t = qubits
        return _rewrite_op(Op("cu3", (_pi / 2, 0.0, _pi), (c, t)))
    raise ValueError("暂无 %r 到白名单门集的改写规则" % name)


# ---- spinq：OpenQASM 2.0 ----

def emit_spinq(circuit: Circuit) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % circuit.n_qubits,
        "creg c[%d];" % circuit.n_clbits,
    ]
    for op in circuit.ops:
        lines.append(_gate_line(op, "qasm2"))
    measures = circuit.measures or _fallback_measures(circuit)
    for q, c in measures:
        lines.append("measure q[%d] -> c[%d];" % (q, c))
    return "\n".join(lines) + "\n"


# ---- braket：OpenQASM 3.0 ----

_BRAKET_NAME = {"cu1": "cp"}  # stdgates.inc 的等价标准名，其余白名单门同名存在


def emit_braket(circuit: Circuit) -> str:
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        "qubit[%d] q;" % circuit.n_qubits,
        "bit[%d] c;" % circuit.n_clbits,
    ]
    for op in circuit.ops:
        lines.append(_gate_line(op, "qasm3"))
    measures = circuit.measures or _fallback_measures(circuit)
    for q, c in measures:
        lines.append("c[%d] = measure q[%d];" % (c, q))
    return "\n".join(lines) + "\n"


# ---- originq：OriginIR ----

_ORIGINQ_NAME = {
    "h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T", "tdg": "TDAG",
    "ry": "RY", "rz": "RZ", "cx": "CNOT", "cu1": "CU1", "swap": "SWAP",
    "ccx": "TOFFOLI",
}


def emit_originq(circuit: Circuit) -> str:
    lines = ["QINIT %d" % circuit.n_qubits, "CREG %d" % circuit.n_clbits]
    for op in circuit.ops:
        name = _ORIGINQ_NAME.get(op.name, op.name.upper())
        args = ", ".join("q[%d]" % q for q in op.qubits)
        if op.params:
            lines.append("%s(%s) %s" % (name, ", ".join(_fmt(p) for p in op.params), args))
        else:
            lines.append("%s %s" % (name, args))
    measures = circuit.measures or _fallback_measures(circuit)
    for q, c in measures:
        lines.append("MEASURE q[%d], c[%d]" % (q, c))
    return "\n".join(lines) + "\n"


# ---- 公共工具 ----

def _fallback_measures(circuit: Circuit):
    if circuit.n_qubits > circuit.n_clbits:
        raise ValueError("电路缺少测量语句且经典位不足以承载全测量")
    return [(q, q) for q in range(circuit.n_qubits)]


def _gate_line(op: Op, dialect: str) -> str:
    name = op.name
    if dialect == "qasm3":
        name = _BRAKET_NAME.get(name, name)
    args = ", ".join("q[%d]" % q for q in op.qubits)
    if op.params:
        return "%s(%s) %s;" % (name, ", ".join(_fmt(p) for p in op.params), args)
    return "%s %s;" % (name, args)


TARGETS = ("spinq", "braket", "originq")


def transpile_to(circuit: Circuit, target: str) -> str:
    if target not in TARGETS:
        raise ValueError("未知目标 %r，支持：%s" % (target, ", ".join(TARGETS)))
    normalized = to_whitelist(circuit)
    if target == "spinq":
        return emit_spinq(normalized)
    if target == "braket":
        return emit_braket(normalized)
    return emit_originq(normalized)
