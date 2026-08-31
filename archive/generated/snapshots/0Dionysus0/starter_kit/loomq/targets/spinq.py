"""spinq 后端。

emit()：按 target_ir_contract.md 的规定，spinq 接受完整的、可执行的
OpenQASM 2.0 程序，用的就是和输入一样的 12 门白名单——所以序列化只是
把 IR 原样、规范地重新拼回 QASM 文本（走契约合规性检查不需要任何门
分解）。

execute()：跑在三后端共用的参考模拟器上（loomq.simulate）。以后可以
按 starter_kit/examples/run_spinq.py 的写法接入真实的 SpinQit——先
`import spinqit` 试一下，失败/没装就退回这个函数（具体做法见
loomq/targets/__init__.py 的模块说明）。但在信任厂商 SDK 自己返回的
counts 之前，一定要先实测验证它的比特序约定，跟 sample_counts() 要求
的"c[0] 在最右"是否一致；如果悄悄信错了顺序，哪怕这一跑是"真"的，也
会把每一个保真度分数都算错。
"""

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from .. import simulate
from ..ir import Circuit, GateOp, MeasureOp

BACKEND_ID = "spinq_taurus_simulator"
NATIVE_GATES = frozenset({"h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx"})


def _emit_gate(op: GateOp) -> str:
    args = ",".join(f"q[{q}]" for q in op.qubits)
    params = f"({','.join(repr(p) for p in op.params)})" if op.params else ""
    return f"{op.name}{params} {args};"


def _emit_measure(op: MeasureOp) -> str:
    return f"measure q[{op.qubit}] -> c[{op.clbit}];"


# Op 是一个封闭的 Union[GateOp, MeasureOp]（见 ir.py），所以按具体类型
# 查字典分发是精确的，不用担心子类问题；而且相比原来那种没有 else 分支
# 的 isinstance if/elif，遇到没见过的 Op 类型现在会直接 KeyError 报错，
# 而不是被默默丢掉。
_EMIT = {GateOp: _emit_gate, MeasureOp: _emit_measure}


def emit(circuit: Circuit) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{circuit.n_qubits}];",
        f"creg c[{circuit.n_clbits}];",
    ]
    lines.extend(_EMIT[type(op)](op) for op in circuit.ops)
    return "\n".join(lines) + "\n"


def execute(circuit: Circuit, shots: int) -> Dict[str, Any]:
    counts = simulate.sample_counts(circuit, shots)
    return {
        "backend": BACKEND_ID,
        "job_id": f"spinq-sim-{uuid4().hex[:12]}",
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
