#!/usr/bin/env python3
"""LoomQ submission adapter -- contract v1.0 implementation.

Architecture (one IR, many targets):

    OpenQASM 2.0 --parse--> Circuit IR --emit--> spinq  (OpenQASM 2.0)
                                          |--> braket (OpenQASM 3)
                                          |--> originq (OriginIR)
                                               |
                        target IR --parse back--> reference statevector
                        simulator --sample--> unified counts schema

Every ``run()`` executes the *transpiled* artifact, so the transpiler and the
executor can never disagree. The simulator is dependency-free; the unified
schema is produced identically for all three targets.

See ARCHITECTURE.md for the full design notes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    from .loomq_core import (
        parse_qasm2,
        simulate_counts,
        transpile_circuit,
        compile_hybrid_qasm,
    )
    from .loomq_core.transpilers import parse_target_ir
    from .loomq_core.agent import agent_reply
except ImportError:  # direct import when starter_kit/ is the working directory
    from loomq_core import (  # type: ignore
        parse_qasm2,
        simulate_counts,
        transpile_circuit,
        compile_hybrid_qasm,
    )
    from loomq_core.transpilers import parse_target_ir  # type: ignore
    from loomq_core.agent import agent_reply  # type: ignore


SUPPORTED_TARGETS = ("spinq", "originq", "braket")

_BACKEND_NAMES = {
    "spinq": "spinq_taurus",
    "originq": "originq_local_simulator",
    "braket": "braket_local_simulator",
}


def _check_target(target: str) -> None:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            "unsupported target %r; expected one of %s" % (target, SUPPORTED_TARGETS)
        )


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    _check_target(target)
    circuit = parse_qasm2(qasm_str)
    return transpile_circuit(circuit, target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules.

    The input is transpiled to the target IR, the artifact is parsed back, and
    the reference simulator samples it -- identical semantics for all targets.
    """
    _check_target(target)
    if not isinstance(shots, int) or shots <= 0:
        raise ValueError("shots must be a positive integer")

    native_ir = transpile(qasm_str, target)
    circuit = parse_target_ir(target, native_ir)
    counts = simulate_counts(circuit, shots)

    return {
        "backend": _BACKEND_NAMES[target],
        "job_id": "loomq-local-%s" % uuid.uuid4().hex[:12],
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta": {
            "transpiled_gates": len(circuit.gates),
            "qubits": circuit.num_qubits,
            "executor": "loomq-reference-statevector",
            "target_ir": target,
        },
    }


def agent_chat(prompt: str) -> str:
    """L2 entry point: LLM-backed agent using the LOOMQ_LLM_* environment."""
    return agent_reply(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """L3 entry point: split Hybrid-QASM into quantum ops + RISC-V assembly."""
    return compile_hybrid_qasm(hybrid_qasm_str)
