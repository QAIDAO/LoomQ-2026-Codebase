"""Backend runners with SDK integration and noiseless fallback."""

from __future__ import annotations

import hashlib
import importlib
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

try:
    from qasm_engine import simulate_counts
    from transpilers import transpile
except ImportError:
    from starter_kit.qasm_engine import simulate_counts
    from starter_kit.transpilers import transpile

_BACKEND_NAMES = {
    "spinq": "spinq_taurus",
    "originq": "originq_local_simulator",
    "braket": "braket_local_simulator",
}


def _meta(qasm_str: str) -> Dict[str, Any]:
    return {"transpiled_gates": qasm_str.lower().count(" q["), "depth": qasm_str.count("\n")}


def _result(backend: str, shots: int, counts: Dict[str, int], qasm_str: str) -> Dict[str, Any]:
    return {
        "backend": backend,
        "job_id": hashlib.sha256(qasm_str.encode()).hexdigest()[:16],
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta": _meta(qasm_str),
    }


def _run_spinq(qasm_str: str, shots: int) -> Dict[str, Any]:
    try:
        from spinqit import BasicSimulatorConfig, get_basic_simulator, get_compiler

        with tempfile.NamedTemporaryFile("w", suffix=".qasm", delete=False) as handle:
            handle.write(transpile(qasm_str, "spinq"))
            path = handle.name
        compiler = get_compiler("qasm")
        exe = compiler.compile(path, 0)
        config = BasicSimulatorConfig()
        config.configure_shots(shots)
        engine = get_basic_simulator()
        result = engine.execute(exe, config)
        counts = {str(k): int(v) for k, v in dict(result.counts).items()}
        return _result(_BACKEND_NAMES["spinq"], shots, counts, qasm_str)
    except Exception:
        counts = simulate_counts(qasm_str, shots)
        return _result(_BACKEND_NAMES["spinq"], shots, counts, qasm_str)


def _run_originq(qasm_str: str, shots: int) -> Dict[str, Any]:
    try:
        pyqpanda = importlib.import_module("pyqpanda")
        origin_ir = transpile(qasm_str, "originq")
        machine = pyqpanda.CPUQVM()
        machine.init_qvm()
        prog = pyqpanda.QProg()
        pyqpanda.convert_originir_string_to_qprog(origin_ir, machine, prog)
        machine.directly_run(prog, shots)
        result = machine.get_prob_dict(prog, -1)
        machine.finalize()
        counts = {state: int(round(prob * shots)) for state, prob in result.items()}
        diff = shots - sum(counts.values())
        if diff and counts:
            key = max(counts, key=counts.get)
            counts[key] += diff
        return _result(_BACKEND_NAMES["originq"], shots, counts, qasm_str)
    except Exception:
        counts = simulate_counts(qasm_str, shots)
        return _result(_BACKEND_NAMES["originq"], shots, counts, qasm_str)


def _run_braket(qasm_str: str, shots: int) -> Dict[str, Any]:
    try:
        from braket.circuits import Circuit as BraketCircuit
        from braket.devices import LocalSimulator

        oq3 = transpile(qasm_str, "braket")
        device = LocalSimulator()
        circuit = BraketCircuit.from_qasm(oq3)
        task = device.run(circuit, shots=shots)
        raw = task.result().measurement_counts
        counts = {str(k): int(v) for k, v in raw.items()}
        return _result(_BACKEND_NAMES["braket"], shots, counts, qasm_str)
    except Exception:
        counts = simulate_counts(qasm_str, shots)
        return _result(_BACKEND_NAMES["braket"], shots, counts, qasm_str)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    if target == "spinq":
        return _run_spinq(qasm_str, shots)
    if target == "originq":
        return _run_originq(qasm_str, shots)
    if target == "braket":
        return _run_braket(qasm_str, shots)
    raise ValueError(f"unsupported target: {target}")
