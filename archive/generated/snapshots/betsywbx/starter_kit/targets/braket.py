import re
import os
import uuid
import datetime
from typing import Any, Dict
 
from braket.devices import LocalSimulator
from braket.aws import AwsDevice
from braket.ir.openqasm import Program
 
from utils import checker_reg, checker_measure

# ---------------------------------------------------------------------------
# transpile_braket
# ---------------------------------------------------------------------------
def transpile_braket(qasm_str: str) -> str:
    # check whether all registers have been declared
    res = checker_reg(qasm_str)

    # transpile measure
    res = checker_measure(res)

    # check imports
    if 'include "qelib1.inc";' in res:
        res = res.replace('include "qelib1.inc";', 'include "stdgates.inc";')
    elif 'include "stdgates.inc";' not in res:
        res = 'include "stdgates.inc";\n' + res

    # check header
    lines = [line.strip() for line in res.strip().splitlines() if line.strip()]
    has_qasm3 = any("OPENQASM 3.0" in l for l in lines)
    has_qasm2 = any("OPENQASM 2.0" in l for l in lines)
    
    if has_qasm2:
        res = res.replace("OPENQASM 2.0;", "OPENQASM 3.0;")
    elif not has_qasm3:
        res = "OPENQASM 3.0;\n" + res

    # transpile gate - cu1
    res = res.replace("cu1(", "cphase(")

    # transpile register declaration
    res = re.sub(
        r"qreg\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\[(\d+)\];", r"qubit[\2] \1;", res
    )
    res = re.sub(
        r"creg\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\[(\d+)\];", r"bit[\2] \1;", res
    )
    res = res.replace("cx ", "cnot ")

    return res


# ---------------------------------------------------------------------------
# run_braket
# ---------------------------------------------------------------------------
def _count_transpiled_gates(qasm3_str: str) -> int:
    return len([
        line for line in qasm3_str.splitlines()
        if line.strip()
        and not line.startswith(("OPENQASM", "include", "qubit", "bit", "//"))
        and "measure" not in line
    ])
 
 
def _reverse_bitstring_counts(raw_counts: dict) -> dict:
    out: Dict[str, int] = {}
    for bitstring, cnt in raw_counts.items():
        rev = bitstring[::-1]
        out[rev] = out.get(rev, 0) + cnt
    return out
 
 
def run_braket(qasm_str: str, shots: int = 8192, device_arn: str = None) -> Dict[str, Any]:
    qasm3_str = transpile_braket(qasm_str)
 
    if device_arn:
        device = AwsDevice(device_arn)
        qasm3_for_exec = qasm3_str
        backend_name = device.name if hasattr(device, "name") else device_arn
    else:
        device = LocalSimulator()
        qasm3_for_exec = qasm3_str.replace(
            'include "stdgates.inc";', ''
        )
        backend_name = "braket_local_simulator"
 
    program = Program(source=qasm3_for_exec)
    task = device.run(program, shots=shots)
    result = task.result()
 
    raw_counts = dict(result.measurement_counts)
    counts = _reverse_bitstring_counts(raw_counts)
 
    return {
        "backend": backend_name,
        "job_id": str(task.id) if hasattr(task, "id") else f"braket_{uuid.uuid4().hex[:8]}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "meta": {
            "transpiled_gates": _count_transpiled_gates(qasm3_str),
            "depth": -1,
        },
    }