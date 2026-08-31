import uuid
import datetime
import os
import re
import tempfile
from typing import Any, Dict

from spinqit import get_compiler, get_basic_simulator, BasicSimulatorConfig

from utils import checker_reg, checker_measure


# ---------------------------------------------------------------------------
# transpile_spinq
# ---------------------------------------------------------------------------
def transpile_spinq(qasm_str: str) -> str:
    """
    Parse the given string to OPENQASM 2.0. Add reg declaration and measure if 
    they are missing. Standarlise header if missing. 
    """
    # declare qreg / creg if missing
    res = checker_reg(qasm_str)

    # add measure if missing
    res = checker_measure(res)

    # check header
    if 'include "qelib1.inc";' not in res:
        res = 'include "qelib1.inc";\n' + res

    lines = [line.strip() for line in res.strip().splitlines() if line.strip()]
    has_qasm2 = any("OPENQASM 2.0" in l for l in lines)
    if not has_qasm2:
        res = "OPENQASM 2.0;\n" + res

    return res


# ---------------------------------------------------------------------------
# run_spinq
# ---------------------------------------------------------------------------
def _compile_qasm_via_tempfile(compiler, qasm_str: str, optimization_level: int = 0):
    """
    create a tempfile for qasm compiler
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".qasm")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(qasm_str)
        return compiler.compile(tmp_path, optimization_level)
    finally:
        os.unlink(tmp_path)

def _reverse_bitstring_counts(raw_counts: dict) -> dict:
    out: Dict[str, int] = {}
    for bitstring, cnt in raw_counts.items():
        rev = bitstring[::-1]
        out[rev] = out.get(rev, 0) + cnt
    return out


def _count_transpiled_gates(qasm2_str: str) -> int:
    return len([
        line for line in qasm2_str.splitlines()
        if line.strip()
        and not line.startswith(("OPENQASM", "include", "qreg", "creg", "measure", "//"))
    ])


def run_spinq(qasm_str: str, shots: int = 8192) -> Dict[str, Any]:
    """
    Transpile, then execute on SpinQit Basic Simulator. Return in JSON Schema format
    """
    qasm2_str = transpile_spinq(qasm_str)

    compiler = get_compiler("qasm")
    exe = _compile_qasm_via_tempfile(compiler, qasm2_str, 0)  # optimization_level=0，不改变门序

    engine = get_basic_simulator()
    config = BasicSimulatorConfig()
    config.configure_shots(shots)
    exec_result = engine.execute(exe, config)

    raw_counts = dict(exec_result.counts)
    counts = _reverse_bitstring_counts(raw_counts)

    return {
        "backend": "spinq_taurus",
        "job_id": f"spinq_local_{uuid.uuid4().hex[:8]}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "meta": {
            "transpiled_gates": _count_transpiled_gates(qasm2_str),
            "depth": -1,
        },
    }