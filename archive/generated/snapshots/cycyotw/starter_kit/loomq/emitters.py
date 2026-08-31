#!/usr/bin/env python3
"""三个后端方言的输出器：Circuit -> 目标文本

这是 `transpile()` 的实现。三个后端各说一种话：

| target | 目标格式 | 长相 |
|---|---|---|
| `spinq` | OpenQASM 2.0 | `h q[0];` |
| `braket` | OpenQASM 3 | `h q[0];` 但 cx 要写成 `cnot` |
| `originq` | OriginIR | `H q[0]`，门名大写、不带分号、参数写在后面 |

**每个后端认得的门不一样**，认不得的必须先改写。下面这张表是逐个门
在真机模拟器上试出来的，不是查文档抄的——文档和实现对不上的地方有好几处：

- braket 不认 `sdg` / `tdg` / `ccx` / `cx`（它自己叫 si / ti / ccnot / cnot）
- originq 的 `SDAG` / `TDAG` **在官方契约的允许门名里，但 pyqpanda 根本没实现**

所以这里的做法是：**只输出"目标格式的规范写法"与"后端真能跑"两者都满足的门**，
其余一律按官方 `gate_identities.md` 的等价式改写（改写已数值复核，见 gates.py）。
"""

try:
    from .circuit import Circuit, Gate, Measure
    from .gates import UnsupportedGateError, decompose
except ImportError:  # 允许把 starter_kit 直接加进 sys.path 使用
    from circuit import Circuit, Gate, Measure
    from gates import UnsupportedGateError, decompose


TARGETS = ("spinq", "originq", "braket")

# 每个后端"不需要改写就能直接输出"的门。实测得出，勿凭文档修改。
NATIVE_GATES = {
    # OpenQASM 2.0 + qelib1：12 门全都是标准门
    "spinq": {"h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx"},
    # braket：sdg/tdg/cu1/ccx 都要改写（它的原生名 si/ti/cphaseshift/ccnot
    # 不是 OpenQASM 3 标准写法，改写后只用两边都认的门，最保险）
    "braket": {"h", "x", "s", "t", "rz", "ry", "cx", "swap"},
    # originq：只有 SDAG/TDAG 缺席，改写成 RZ（RZ 在契约允许门名里）
    "originq": {"h", "x", "s", "t", "rz", "ry", "cx", "cu1", "swap", "ccx"},
}


def transpile(circuit, target):
    """Circuit -> 目标后端的文本。"""
    if target not in TARGETS:
        raise ValueError("不认识的后端 %r，只支持 %s" % (target, ", ".join(TARGETS)))
    lowered = lower(circuit, NATIVE_GATES[target])
    return {"spinq": _emit_qasm2, "braket": _emit_qasm3, "originq": _emit_originir}[target](lowered)


def lower(circuit, native):
    """把电路里所有"目标后端不认识的门"逐层改写掉，直到只剩它认识的门。

    递归是安全的：所有分解式的产物都落在 {h, x, rz, t, cx} 里，
    而这五个门三个后端都认识，所以一定会停下来。
    """
    output = []

    def emit(name, params, qubits):
        if name in native:
            output.append(Gate(name, params, tuple(qubits)))
            return
        pieces = decompose(name, params, qubits)
        if pieces is None:
            raise UnsupportedGateError("门 %s 既不被后端支持，也没有对应的分解式" % name)
        for piece_name, piece_params, piece_qubits in pieces:
            emit(piece_name, piece_params, piece_qubits)

    for op in circuit.ops:
        if isinstance(op, Gate):
            emit(op.name, op.params, op.qubits)
        else:
            output.append(op)

    return Circuit(circuit.num_qubits, circuit.num_clbits, output)


def _number(value):
    """参数统一用 17 位有效数字输出，保证浮点数不丢精度。"""
    return "%.17g" % value


# --------------------------------------------------------------------------
# spinq · OpenQASM 2.0
# --------------------------------------------------------------------------


def _emit_qasm2(circuit):
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % max(circuit.num_qubits, 1),
        "creg c[%d];" % max(circuit.num_clbits, 1),
    ]
    for op in circuit.ops:
        if isinstance(op, Gate):
            args = ", ".join("q[%d]" % index for index in op.qubits)
            params = "(%s)" % ", ".join(_number(p) for p in op.params) if op.params else ""
            lines.append("%s%s %s;" % (op.name, params, args))
        else:
            lines.append("measure q[%d] -> c[%d];" % (op.qubit, op.clbit))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# braket · OpenQASM 3
# --------------------------------------------------------------------------

# braket 的本地模拟器会把 include 当成磁盘上的文件去找并报 FileNotFoundError。
# 但官方契约的 braket 范例里带着这一行，所以 transpile() 保留它以符合契约，
# 执行前由 backends.py 删掉。这是唯一一处"转译产物"与"实际喂给 SDK 的文本"的差别。
QASM3_INCLUDE = 'include "stdgates.inc";'

_QASM3_NAMES = {"cx": "cnot"}


def _emit_qasm3(circuit):
    lines = [
        "OPENQASM 3.0;",
        QASM3_INCLUDE,
        "qubit[%d] q;" % max(circuit.num_qubits, 1),
        "bit[%d] c;" % max(circuit.num_clbits, 1),
    ]
    for op in circuit.ops:
        if isinstance(op, Gate):
            name = _QASM3_NAMES.get(op.name, op.name)
            args = ", ".join("q[%d]" % index for index in op.qubits)
            params = "(%s)" % ", ".join(_number(p) for p in op.params) if op.params else ""
            lines.append("%s%s %s;" % (name, params, args))
        else:
            # 逐位赋值而不是整寄存器赋值：测量可以错位（q[0] 测进 c[1]），
            # 逐位写才能把这种映射如实表达出来。契约明确两种都接受。
            lines.append("c[%d] = measure q[%d];" % (op.clbit, op.qubit))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# originq · OriginIR
# --------------------------------------------------------------------------

_ORIGINIR_NAMES = {
    "h": "H",
    "x": "X",
    "s": "S",
    "t": "T",
    "rz": "RZ",
    "ry": "RY",
    "cx": "CNOT",
    "cu1": "CR",  # 契约写作 CU1/CR；pyqpanda 只认 CR
    "swap": "SWAP",
    "ccx": "TOFFOLI",
}


def _emit_originir(circuit):
    lines = [
        "QINIT %d" % max(circuit.num_qubits, 1),
        "CREG %d" % max(circuit.num_clbits, 1),
    ]
    for op in circuit.ops:
        if isinstance(op, Gate):
            name = _ORIGINIR_NAMES[op.name]
            args = ", ".join("q[%d]" % index for index in op.qubits)
            if op.params:
                # OriginIR 的参数写在比特后面：RZ q[0],(1.57)
                lines.append("%s %s,(%s)" % (name, args, ", ".join(_number(p) for p in op.params)))
            else:
                lines.append("%s %s" % (name, args))
        else:
            lines.append("MEASURE q[%d], c[%d]" % (op.qubit, op.clbit))
    return "\n".join(lines) + "\n"
