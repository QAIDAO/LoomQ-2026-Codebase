#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

L1 entry points implemented on a zero-dependency stack:

    OpenQASM 2.0 -> qasm_parser -> Circuit IR
                  -> simulator (counts for run)
                  -> codegen (native IR for transpile)

The simulator is our own state-vector engine over the 12-gate whitelist,
so the submission container needs no third-party packages, no network
and no SDK credentials. L2/L3 remain opt-in (NotImplementedError).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from uuid import uuid4

try:
    from .circuit_ir import Circuit
    from .qasm_parser import parse_qasm2
    from .simulator import simulate
    from . import codegen
    from . import agent as _agent
    from .hybrid_parser import split_hybrid, parse_classic
    from .riscv_codegen import compile_classic_block
except ImportError:  # standalone-module fallback (evaluator imports adapter by path)
    from circuit_ir import Circuit
    from qasm_parser import parse_qasm2
    from simulator import simulate
    import codegen
    import agent as _agent
    from hybrid_parser import split_hybrid, parse_classic
    from riscv_codegen import compile_classic_block


SUPPORTED_TARGETS = ("spinq", "originq", "braket")

_BACKEND_NAMES = {
    "spinq": "spinq_taurus",
    "originq": "originq_simulator",
    "braket": "braket_local_simulator",
}

_CODEGENS = {
    "spinq": codegen.to_spinq_qasm,
    "originq": codegen.to_originir,
    "braket": codegen.to_braket_qasm3,
}


def _circuit_depth(circuit: Circuit) -> int:
    """Classical depth: longest chain of dependent gates on any qubit."""
    layers = [0] * circuit.num_qubits
    for op in circuit.ops:
        start = max(layers[q] for q in op.qubits)
        for q in op.qubits:
            layers[q] = start + 1
    return max(layers) if layers else 0


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    target = target.lower()
    if target not in SUPPORTED_TARGETS:
        raise ValueError("unsupported target %r (use one of %s)" % (target, SUPPORTED_TARGETS))
    circuit = parse_qasm2(qasm_str)
    return _CODEGENS[target](circuit)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    if shots <= 0:
        raise ValueError("shots must be positive")
    target = target.lower()
    if target not in SUPPORTED_TARGETS:
        raise ValueError("unsupported target %r (use one of %s)" % (target, SUPPORTED_TARGETS))
    circuit = parse_qasm2(qasm_str)
    counts = simulate(circuit, shots)
    return {
        "backend": _BACKEND_NAMES[target],
        "job_id": uuid4().hex[:16],
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "meta": {
            "transpiled_gates": len(circuit.ops),
            "depth": _circuit_depth(circuit),
        },
    }


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    return _agent.agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    split = split_hybrid(hybrid_qasm_str)
    stmts = parse_classic(split.classic_text)
    assembly = compile_classic_block(stmts)
    return split.quantum_ops, assembly
