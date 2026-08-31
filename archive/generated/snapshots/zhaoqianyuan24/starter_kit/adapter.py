#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This file intentionally contains no scoring implementation. Teams may implement
the functions directly or delegate to another language/runtime with subprocess.
"""
import importlib

from typing import Any, Dict, List, Tuple
#from l1 import transpile_l1,run_l1
#from l2 import agent_chat_l2,execute_hybrid_from_prompt,explain_hybrid_result,execute_from_prompt
#from l3 import (
#    compile_hybrid_l3,
#    execute_hybrid_l3,
#)
SUPPORTED_TARGETS = ("spinq", "originq", "braket")

# The public L1 contract names provider platforms.  The Playground additionally
# passes the canonical backend IDs from backend_capabilities.json so a selected
# cloud/QPU backend follows the same adapter.run() path as a local simulator.
LOCAL_BACKEND_IDS = {
    "spinq_taurus_simulator": "spinq",
    "originq_local_simulator": "originq",
    "braket_local_simulator": "braket",
}

REMOTE_BACKEND_IDS = {
    "spinq_cloud_qpu",
    "originq_wukong",
    "braket_cloud",
}

#def _load_module(name: str):
#    """
#    Load a LoomQ implementation module in both supported contexts:
#
#    1. import starter_kit.adapter
#    2. import adapter from inside starter_kit/
#    """
#
#    if __package__:
#        return importlib.import_module(
#            f"{__package__}.{name}"
#        )
#
#    return importlib.import_module(
#        name
#    )

# Support both:
#   import adapter
# and:
#   import starter_kit.adapter
if __package__:
    from .l1 import (
        transpile_l1,
        run_l1,
    )

    from .l2 import (
        agent_chat_l2,
        execute_from_prompt,
        execute_hybrid_from_prompt,
        explain_hybrid_result,
    )

    from .l3 import (
        compile_hybrid_l3,
        execute_hybrid_l3,
    )

else:
    from l1 import (
        transpile_l1,
        run_l1,
    )

    from l2 import (
        agent_chat_l2,
        execute_from_prompt,
        execute_hybrid_from_prompt,
        explain_hybrid_result,
    )

    from l3 import (
        compile_hybrid_l3,
        execute_hybrid_l3,
    )


def transpile(qasm_str: str,target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    return transpile_l1(qasm_str,target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit through a platform or canonical backend ID.

    ``spinq``, ``originq`` and ``braket`` retain the public local L1 behavior.
    The canonical backend IDs are an additive Playground path: local IDs map to
    those same simulators, while configured remote IDs use the provider adapter.
    """

    normalized = target.strip().lower()
    if normalized in LOCAL_BACKEND_IDS:
        return run_l1(qasm_str, LOCAL_BACKEND_IDS[normalized], shots)
    if normalized in REMOTE_BACKEND_IDS:
        return run_hardware(qasm_str, normalized, shots)
    return run_l1(qasm_str, normalized, shots)
       
def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""

    return agent_chat_l2(
        prompt
    )

def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    
    return compile_hybrid_l3(
        hybrid_qasm_str
    )

def agent_run(prompt: str):
    """
    Generate and execute a quantum circuit
    directly from natural language.
    """

    return execute_from_prompt(
        prompt
    )
def execute_hybrid(
    hybrid_qasm_str: str,
    target: str = "originq",
    shots: int = 1024,
):
    """
    Execute a Hybrid-QASM program using a LoomQ
    quantum backend plus the RISC-V classical runtime.
    """

    return execute_hybrid_l3(
        hybrid_qasm_str,
        target=target,
        shots=shots,
    )
def agent_run_hybrid(
    prompt: str,
):
    """
    Execute a hybrid quantum-classical program
    directly from natural language.
    """

    return execute_hybrid_from_prompt(
        prompt
    )
def agent_run_hybrid_explain(
    prompt: str,
):
    """
    Natural language
        -> Hybrid-QASM
        -> quantum execution
        -> RISC-V execution
        -> natural-language explanation
    """

    execution = (
        agent_run_hybrid(
            prompt
        )
    )

    explanation = (
        explain_hybrid_result(
            execution
        )
    )

    return {
        "execution": execution,
        "explanation": explanation,
    }


def run_hardware(
    qasm_str: str,
    target: str,
    shots: int,
    task_name: str = "LoomQ experiment",
) -> Dict[str, Any]:
    """Provider implementation used by ``run`` for remote backend IDs.

    It requires provider credentials and may incur queue time or cost.  Product
    callers should pass the canonical backend ID to ``run`` instead of bypassing
    the backend selection flow.
    """

    if __package__:
        from .hardware import run_hardware as _run_hardware
    else:
        from hardware import run_hardware as _run_hardware
    return _run_hardware(
        qasm_str,
        target,
        shots,
        task_name=task_name,
    )
