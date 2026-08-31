#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This file intentionally contains no scoring implementation. Teams may implement
the functions directly or delegate to another language/runtime with subprocess.
"""

from typing import Any, Dict, List, Tuple

try:
    from .backend.braket import run_braket
    from .backend.originq import run_originq
    from .backend.spinq import run_spinq
    from .emitters.braket import emit_braket
    from .emitters.originq import emit_originq
    from .emitters.spinq import emit_spinq
    from .parser import parse_qasm
    from .l2_agent import agent_chat as run_l2_agent
    from .l3_compiler import compile_hybrid as run_l3_compiler
except ImportError:
    from backend.braket import run_braket
    from backend.originq import run_originq
    from backend.spinq import run_spinq
    from emitters.braket import emit_braket
    from emitters.originq import emit_originq
    from emitters.spinq import emit_spinq
    from parser import parse_qasm
    from l2_agent import agent_chat as run_l2_agent
    from l3_compiler import compile_hybrid as run_l3_compiler

SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    circuit = parse_qasm(qasm_str)
    if target == "spinq":
        return emit_spinq(circuit)
    elif target == "originq":
        return emit_originq(circuit)
    elif target == "braket":
        return emit_braket(
            circuit,
            include_stdlib=True,
        )

    raise NotImplementedError(
        f"{target} is not implemented"
    )


def run(
    qasm_str: str,
    target: str,
    shots: int,
) -> Dict[str, Any]:
    if target == "spinq":
        circuit = parse_qasm(qasm_str)
        spinq_qasm = emit_spinq(circuit)
        measurement_map = {
            measurement.qubit: measurement.bit
            for measurement in circuit.measurements
        }
        return run_spinq(
            spinq_qasm,
            shots=shots,
            measurement_map=measurement_map,
            num_bits=circuit.num_bits,
        )

    if target == "originq":
        circuit = parse_qasm(qasm_str)
        origin_ir = emit_originq(
            circuit,
            execution_compatible=True,
        )
        return run_originq(origin_ir, shots=shots)

    if target == "braket":
        circuit = parse_qasm(qasm_str)

        qasm3 = emit_braket(
            circuit,
            include_stdlib=False,
        )

        measurement_map = {
            measurement.qubit: measurement.bit
            for measurement in circuit.measurements
        }

        return run_braket(
            qasm3,
            shots=shots,
            measurement_map=measurement_map,
            num_bits=circuit.num_bits,
        )

    raise NotImplementedError(
        f"{target} backend is not implemented"
    )


def agent_chat(prompt: str) -> str:
    """Run the L2 agent using the documented LOOMQ_LLM_* environment."""
    return run_l2_agent(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Compile quantum operations and the classical RISC-V control program."""
    return run_l3_compiler(hybrid_qasm_str)
