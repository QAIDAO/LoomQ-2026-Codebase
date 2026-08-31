#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This file intentionally contains no scoring implementation. Teams may implement
the functions directly or delegate to another language/runtime with subprocess.
"""

from typing import Any, Dict, List, Tuple

if __package__:
    from .loomq_l1.emitters import emit_braket, emit_originq, emit_spinq
    from .loomq_l1.errors import NormalizationError, QASMParseError, UnsupportedTargetError
    from .loomq_l1.model import Circuit, RawExecution
    from .loomq_l1.normalize import build_result
    from .loomq_l1.parser import parse_qasm
    from .loomq_l1.runners import run_braket, run_originq, run_spinq
else:
    from loomq_l1.emitters import emit_braket, emit_originq, emit_spinq
    from loomq_l1.errors import NormalizationError, QASMParseError, UnsupportedTargetError
    from loomq_l1.model import Circuit, RawExecution
    from loomq_l1.normalize import build_result
    from loomq_l1.parser import parse_qasm
    from loomq_l1.runners import run_braket, run_originq, run_spinq


SUPPORTED_TARGETS = ("spinq", "originq", "braket")


EMITTERS = {
    "spinq": emit_spinq,
    "originq": emit_originq,
    "braket": emit_braket,
}


RUNNERS = {
    "spinq": run_spinq,
    "originq": run_originq,
    "braket": run_braket,
}


def _validate_target(target: object) -> str:
    if type(target) is not str or target not in SUPPORTED_TARGETS:
        raise UnsupportedTargetError(f"unsupported target: {target!r}")
    return target


def _validate_source(qasm_str: object) -> str:
    if type(qasm_str) is not str:
        raise QASMParseError("source must be a string")
    return qasm_str


def _validate_shots(shots: object) -> int:
    if type(shots) is not int or shots <= 0:
        raise NormalizationError("shots must be a positive built-in integer")
    return shots


def _gate_depth(circuit: Circuit) -> int:
    qubit_depths = [0] * circuit.num_qubits
    depth = 0
    for operation in circuit.operations:
        layer = max(qubit_depths[qubit] for qubit in operation.qubits) + 1
        for qubit in operation.qubits:
            qubit_depths[qubit] = layer
        depth = max(depth, layer)
    return depth


def _with_adapter_metadata(raw: RawExecution, circuit: Circuit, target: str) -> RawExecution:
    """Copy a valid raw execution while applying adapter-owned metadata."""
    if not isinstance(raw, RawExecution) or type(raw.metadata) is not dict:
        return raw
    metadata = dict(raw.metadata)
    metadata.update(
        {
            "target": target,
            "emitted_gate_count": len(circuit.operations),
            "circuit_depth": _gate_depth(circuit),
        }
    )
    return RawExecution(
        backend=raw.backend,
        job_id=raw.job_id,
        counts=raw.counts,
        key_format=raw.key_format,
        reverse_bits=raw.reverse_bits,
        metadata=metadata,
    )


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    target = _validate_target(target)
    circuit = parse_qasm(_validate_source(qasm_str))
    return EMITTERS[target](circuit)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    target = _validate_target(target)
    qasm_str = _validate_source(qasm_str)
    shots = _validate_shots(shots)
    circuit = parse_qasm(qasm_str)
    native_ir = EMITTERS[target](circuit)
    raw = RUNNERS[target](native_ir, shots)
    return build_result(
        _with_adapter_metadata(raw, circuit, target),
        width=circuit.num_clbits,
        shots=shots,
    )


def agent_chat(prompt: str) -> str:
    """L2 entry point using the documented LOOMQ_LLM_* environment."""
    if __package__:
        from .loomq_l2 import agent_chat as run_agent_chat
    else:
        from loomq_l2 import agent_chat as run_agent_chat
    return run_agent_chat(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Compile Hybrid-QASM into ordered quantum operations and RISC-V assembly."""
    if __package__:
        from .loomq_l3 import compile_hybrid as run_compile_hybrid
    else:
        from loomq_l3 import compile_hybrid as run_compile_hybrid
    return run_compile_hybrid(hybrid_qasm_str)
