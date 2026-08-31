"""originq 后端。

emit()：按 target_ir_contract.md 的规定，OriginIR 接受同样的 12 门
白名单，只是换了一套（大写的）名字——先是 QINIT/CREG 头部，然后每条
指令占一行，每个测量对应一行 MEASURE q[i], c[j]。

execute()：跑在三后端共用的参考模拟器上（loomq.simulate）。以后可以
按 starter_kit/examples/run_originq.py 的写法接入真实的 pyqpanda，接法
跟 spinq.py 一样——先试 SDK，失败就退回这个函数，并且在信任它返回的
counts 之前，一定要先实测验证其比特序约定。
"""

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from .. import simulate
from ..ir import Circuit, GateOp, MeasureOp

BACKEND_ID = "originq_local_simulator"
NATIVE_GATES = frozenset({"h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx"})

_GATE_NAMES = {
    "h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T", "tdg": "TDAG",
    "ry": "RY", "rz": "RZ", "cx": "CNOT", "cu1": "CU1", "swap": "SWAP",
    "ccx": "TOFFOLI",
}


def _emit_gate(op: GateOp) -> str:
    name = _GATE_NAMES[op.name]
    args = ", ".join(f"q[{q}]" for q in op.qubits)
    params = f"({','.join(repr(p) for p in op.params)})" if op.params else ""
    return f"{name}{params} {args}"


def _emit_measure(op: MeasureOp) -> str:
    return f"MEASURE q[{op.qubit}], c[{op.clbit}]"


# Op 是一个封闭的 Union[GateOp, MeasureOp]（见 ir.py），所以按具体类型
# 查字典分发是精确的，不用担心子类问题；而且相比原来那种没有 else 分支
# 的 isinstance if/elif，遇到没见过的 Op 类型现在会直接 KeyError 报错，
# 而不是被默默丢掉。
_EMIT = {GateOp: _emit_gate, MeasureOp: _emit_measure}


def emit(circuit: Circuit) -> str:
    lines = [f"QINIT {circuit.n_qubits}", f"CREG {circuit.n_clbits}"]
    lines.extend(_EMIT[type(op)](op) for op in circuit.ops)
    return "\n".join(lines) + "\n"


def execute(circuit: Circuit, shots: int) -> Dict[str, Any]:
    counts = simulate.sample_counts(circuit, shots)
    return {
        "backend": BACKEND_ID,
        "job_id": f"originq-sim-{uuid4().hex[:12]}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "engine": "reference_simulator",
            "transpiled_gates": len(circuit.gate_ops()),
            "depth": circuit.depth(),
        },
    }
