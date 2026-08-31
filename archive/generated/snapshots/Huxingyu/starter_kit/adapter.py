#!/usr/bin/env python3
"""Dependency-free L1 reference adapter.

The implementation is deliberately backend-neutral: one parser/simulator is
used for local development, while ``transpile`` emits each target's contracted
IR.  Real SDK/cloud execution can replace ``run`` later without changing the
public interface.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    from .agent_engine import agent_chat as _agent_chat
    from .qasm_core import Circuit, parse_qasm, render_braket, render_origin, render_qasm2, sample_counts
    from .hybrid_compiler import compile_hybrid as _compile_hybrid
except ImportError:
    from agent_engine import agent_chat as _agent_chat
    from qasm_core import Circuit, parse_qasm, render_braket, render_origin, render_qasm2, sample_counts
    from hybrid_compiler import compile_hybrid as _compile_hybrid


SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    target = target.strip().lower()
    circuit = parse_qasm(qasm_str)
    if target == "spinq":
        return render_qasm2(circuit)
    if target == "originq":
        return render_origin(circuit)
    if target == "braket":
        return render_braket(circuit)
    raise ValueError(f"unsupported target: {target}")


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")
    target = target.strip().lower()
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")
    circuit = parse_qasm(qasm_str)
    native = transpile(qasm_str, target)
    counts = sample_counts(circuit, shots, target + "\n" + native)
    backend = {
        "spinq": "spinq_taurus_simulator",
        "originq": "originq_local_simulator",
        "braket": "braket_local_simulator",
    }[target]
    digest = hashlib.sha256(native.encode("utf-8")).hexdigest()[:16]
    return {
        "backend": backend,
        "job_id": f"local-{target}-{digest}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "meta": {
            "transpiled_gates": sum(operation.name != "measure" for operation in circuit.operations),
            "qubits": circuit.qubits,
            "simulator": "loomq_reference_statevector",
        },
    }


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    return _agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    return _compile_hybrid(hybrid_qasm_str)
