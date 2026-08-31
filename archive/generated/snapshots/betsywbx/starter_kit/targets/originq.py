import re
import uuid
import datetime
from typing import Any, Dict

import pyqpanda as pq

# ---------------------------------------------------------------------------
# transpile_originq
# ---------------------------------------------------------------------------
_P_RE = re.compile(r'^P\s+q\[(\d+)\],\(([-\d.eE]+)\)$')
_CNOT_RE = re.compile(r'^CNOT\s+q\[(\d+)\],q\[(\d+)\]$')


def _fold_cu1_pattern(originir: str, tol: float = 1e-6) -> str:
    """
    pyqpanda 的 convert_qprog_to_originir 会把 cu1/cp(θ) 统一拆解成:
        P q[a],(θ/2)
        CNOT q[a],q[b]
        P q[b],(-θ/2)
        CNOT q[a],q[b]
        P q[b],(θ/2)
    P 不在契约的12门白名单里(只允许 CU1/CR),这里把这个固定5行模式识别出来,
    折叠回契约要求的单行 CR(θ) q[a],q[b]。
    """
    lines = originir.splitlines()
    out = []
    i = 0
    while i < len(lines):
        if i + 4 < len(lines):
            m0 = _P_RE.match(lines[i].strip())
            m1 = _CNOT_RE.match(lines[i + 1].strip())
            m2 = _P_RE.match(lines[i + 2].strip())
            m3 = _CNOT_RE.match(lines[i + 3].strip())
            m4 = _P_RE.match(lines[i + 4].strip())
            if m0 and m1 and m2 and m3 and m4:
                a0, t1 = int(m0.group(1)), float(m0.group(2))
                c1a, c1b = int(m1.group(1)), int(m1.group(2))
                b2, t2 = int(m2.group(1)), float(m2.group(2))
                c3a, c3b = int(m3.group(1)), int(m3.group(2))
                b4, t3 = int(m4.group(1)), float(m4.group(2))
                same_qubits = (a0 == c1a == c3a) and (c1b == b2 == c3b == b4)
                same_angles = abs(t2 + t1) < tol and abs(t3 - t1) < tol
                if same_qubits and same_angles:
                    theta = 2 * t1
                    out.append(f"CR({theta:.6f}) q[{a0}],q[{c1b}]")
                    i += 5
                    continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def transpile_originq(qasm_str: str) -> str:
    machine = pq.CPUQVM()
    machine.init_qvm()
    try:
        prog, qubits, cbits = pq.convert_qasm_string_to_qprog(qasm_str, machine)
        originir = pq.convert_qprog_to_originir(prog, machine)
    finally:
        machine.finalize()

    return _fold_cu1_pattern(originir)


# ---------------------------------------------------------------------------
# run_originq
# ---------------------------------------------------------------------------
def _count_transpiled_gates(originir_str: str) -> int:
    return len([
        line for line in originir_str.splitlines()
        if line.strip()
        and not line.startswith(("QINIT", "CREG", "MEASURE", "//"))
    ])


def run_originq(qasm_str: str, shots: int = 8192) -> Dict[str, Any]:
    originir_str = transpile_originq(qasm_str)

    # 每次调用都用全新 machine 实例,避免 qubit/creg 分配状态跨调用累积
    machine = pq.CPUQVM()
    machine.init_qvm()
    try:
        prog, qubits, cbits = pq.convert_qasm_string_to_qprog(qasm_str, machine)
        raw_counts = machine.run_with_configuration(prog, cbits, shots)
    finally:
        machine.finalize()

    counts = dict(raw_counts)

    return {
        "backend": "originq_cpu_simulator",
        "job_id": f"originq_local_{uuid.uuid4().hex[:8]}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "meta": {
            "transpiled_gates": _count_transpiled_gates(originir_str),
            "depth": -1,
        },
    }