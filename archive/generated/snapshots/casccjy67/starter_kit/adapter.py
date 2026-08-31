"""
LoomQ Adapter — main submission interface.

Implements the four required functions:
  - transpile(qasm_str, target) -> str   [L1]
  - run(qasm_str, target, shots) -> dict  [L1]
  - agent_chat(prompt) -> str            [L2]
  - compile_hybrid(hybrid_qasm_str) -> (list, str)  [L3]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starter_kit.transpiler.parser import QASMParser
from starter_kit.transpiler import BACKENDS

VALID_TARGETS = {"spinq", "originq", "braket"}


def transpile(qasm_str: str, target: str) -> str:
    """Transpile OpenQASM 2.0 to target backend's native instruction string.

    Args:
        qasm_str: OpenQASM 2.0 circuit string
        target: one of 'spinq', 'originq', 'braket'

    Returns:
        Native instruction string for the target backend
    """
    if target not in VALID_TARGETS:
        raise ValueError(f"Invalid target '{target}'. Valid: {VALID_TARGETS}")

    parser = QASMParser()
    circuit = parser.parse(qasm_str)

    backend = BACKENDS[target]()
    return backend.transpile(circuit)


def run(qasm_str: str, target: str, shots: int = 8192) -> dict:
    """Run a quantum circuit on the specified backend.

    Args:
        qasm_str: OpenQASM 2.0 circuit string
        target: one of 'spinq', 'originq', 'braket'
        shots: number of measurement shots

    Returns:
        Dict conforming to the unified result schema:
        {
            "backend": str,
            "job_id": str,
            "shots": int,
            "counts": {str: int},
            "bit_order": "little",
            "timestamp": str (ISO 8601 UTC),
            "meta": {str: any}
        }
    """
    if target not in VALID_TARGETS:
        raise ValueError(f"Invalid target '{target}'. Valid: {VALID_TARGETS}")

    parser = QASMParser()
    circuit = parser.parse(qasm_str)

    backend = BACKENDS[target]()
    return backend.run(circuit, shots=shots)


def agent_chat(prompt: str) -> str:
    """[L2] Quantum assistant agent — generates QASM, fixes errors, recommends backends.

    Reads configuration from LOOMQ_LLM_* environment variables:
        - LOOMQ_LLM_BASE_URL: model service base URL
        - LOOMQ_LLM_API_KEY: API key
        - LOOMQ_LLM_MODEL: model name

    Returns:
        Agent response text (may include QASM code, backend recommendation, etc.)
    """
    from starter_kit.agent.chat import run_agent
    return run_agent(prompt)


def compile_hybrid(hybrid_qasm_str: str):
    """[L3] Compile Hybrid-QASM to quantum operations + RISC-V assembly.

    Args:
        hybrid_qasm_str: Hybrid-QASM source string

    Returns:
        Tuple of (list_of_quantum_ops, riscv_assembly_text)
    """
    from starter_kit.hybrid_compiler.compiler import compile_hybrid_qasm
    return compile_hybrid_qasm(hybrid_qasm_str)
