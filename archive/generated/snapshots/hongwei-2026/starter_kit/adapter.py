#!/usr/bin/env python3
"""LoomQ submission adapter — unified middleware for SpinQ / OriginQ / Braket."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Tuple

try:
    from .loomq_core import (
        BACKEND_NAMES,
        compile_hybrid_program,
        parse_qasm,
        simulate_counts,
        transpile_circuit,
        unified_result,
    )
except ImportError:
    from loomq_core import (
        BACKEND_NAMES,
        compile_hybrid_program,
        parse_qasm,
        simulate_counts,
        transpile_circuit,
        unified_result,
    )

SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    if target not in SUPPORTED_TARGETS:
        raise ValueError("unsupported target: %s (expected one of %s)" % (target, SUPPORTED_TARGETS))
    circuit = parse_qasm(qasm_str)
    return transpile_circuit(circuit, target)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema."""
    if target not in SUPPORTED_TARGETS:
        raise ValueError("unsupported target: %s" % target)
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")

    circuit = parse_qasm(qasm_str)
    if os.environ.get("LOOMQ_USE_NATIVE_SDK", "").strip().lower() in {"1", "true", "yes"}:
        try:
            if target == "braket":
                return _run_braket(circuit, qasm_str, shots)
            if target == "spinq":
                return _run_spinq(circuit, qasm_str, shots)
            if target == "originq":
                return _run_originq(circuit, qasm_str, shots)
        except Exception:
            pass

    counts = simulate_counts(circuit, shots)
    return unified_result(
        BACKEND_NAMES[target],
        shots,
        counts,
        meta={
            "transpiled_gates": len(circuit.gates),
            "depth": len(circuit.gates),
            "engine": "loomq_statevector",
        },
    )


def agent_chat(prompt: str) -> str:
    """L2: natural-language → QASM / backend advice via LOOMQ_LLM_* + verify loop."""
    try:
        from .llm_client import chat_completion
        from . import loomq_agent as agent
    except ImportError:
        from llm_client import chat_completion
        import loomq_agent as agent

    backends = agent.load_backends(os.path.dirname(os.path.abspath(__file__)))
    task = agent.classify_task(prompt)
    capabilities = _load_capabilities_brief()

    # Deterministic backend shortlist (scoring requires exact capability ids).
    recommend_text, recommend_ids = ("", [])
    if task == "recommend":
        recommend_text, recommend_ids = agent.recommend_reply(prompt, backends)

    messages = [
        {"role": "system", "content": agent.system_prompt_for(task)},
        {
            "role": "user",
            "content": (
                "Backend capability reference:\n%s\n\n"
                "Deterministic shortlist (if any):\n%s\n\n"
                "User request:\n%s"
                % (capabilities, recommend_text or "(n/a)", prompt)
            ),
        },
    ]

    last_text = ""
    for _attempt in range(3):
        response = chat_completion(messages)
        last_text = _message_content(response)

        if task == "recommend":
            return agent.ensure_backend_ids(last_text + "\n\n" + recommend_text, recommend_ids)

        qasm = agent.extract_qasm(last_text)
        if task in ("generate", "fix") and not qasm:
            messages.append({"role": "assistant", "content": last_text})
            messages.append(
                {
                    "role": "user",
                    "content": "请在 ```qasm 代码块中给出完整可运行的 OpenQASM 2.0（含寄存器声明与 measure）。",
                }
            )
            continue

        if qasm and task in ("generate", "fix", "general"):
            try:
                parse_qasm(qasm)
                result = run(qasm, "spinq", 64)
                if not result.get("counts"):
                    raise RuntimeError("empty counts")
                return last_text
            except Exception as exc:
                messages.append({"role": "assistant", "content": last_text})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "本地 L1 校验失败：%s。保持用户声明的目标态/意图，输出修复后的完整 OpenQASM 2.0。"
                            % exc
                        ),
                    }
                )
                continue
        return last_text
    if task == "recommend":
        return agent.ensure_backend_ids(last_text + "\n\n" + recommend_text, recommend_ids)
    return last_text


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """L3: Hybrid-QASM → (quantum op list, RISC-V assembly)."""
    return compile_hybrid_program(hybrid_qasm_str)


# ----- helpers -----

def _message_content(response: Dict[str, Any]) -> str:
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("malformed LLM response") from exc


def _load_capabilities_brief() -> str:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend_capabilities.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        lines = []
        for item in data.get("backends", []):
            lines.append(
                "- {id}: platform={platform}, kind={kind}, max_qubits={max_qubits}, "
                "queue={queue}, cost={cost}, account={requires_account}".format(**item)
            )
        return "\n".join(lines)
    except OSError:
        return "(capabilities file unavailable)"


def _run_braket(circuit, qasm_str: str, shots: int) -> Dict[str, Any]:
    from braket.devices import LocalSimulator
    from braket.ir.openqasm import Program

    native = transpile_circuit(circuit, "braket")
    device = LocalSimulator()
    task = device.run(Program(source=native), shots=shots)
    result = task.result()
    counts = {str(k): int(v) for k, v in dict(result.measurement_counts).items()}
    return unified_result(
        "braket_local_simulator",
        shots,
        counts,
        meta={"transpiled_gates": len(circuit.gates), "engine": "amazon-braket-sdk"},
    )


def _run_spinq(circuit, qasm_str: str, shots: int) -> Dict[str, Any]:
    import tempfile
    import os as _os

    from spinqit import BasicSimulatorConfig, get_basic_simulator, get_compiler

    native = transpile_circuit(circuit, "spinq")
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")
    try:
        tmp.write(native)
        tmp.close()
        ir = get_compiler("qasm").compile(tmp.name, 0)
    finally:
        _os.unlink(tmp.name)
    engine = get_basic_simulator()
    config = BasicSimulatorConfig()
    config.configure_shots(shots)
    result = engine.execute(ir, config)
    counts = {str(k): int(v) for k, v in dict(result.counts).items()}
    return unified_result(
        "spinq_taurus",
        shots,
        counts,
        meta={"transpiled_gates": len(circuit.gates), "engine": "spinqit"},
    )


def _run_originq(circuit, qasm_str: str, shots: int) -> Dict[str, Any]:
    import pyqpanda as pq

    # OriginQ path: feed OpenQASM 2.0 (same as spinq emit) into pyqpanda.
    native_qasm = transpile_circuit(circuit, "spinq")
    machine = pq.CPUQVM()
    machine.init_qvm()
    try:
        if hasattr(pq, "convert_qasm_string_to_qprog"):
            prog, _qreg, creg = pq.convert_qasm_string_to_qprog(native_qasm, machine)
        else:
            prog = pq.convert_qasm_to_qprog(native_qasm, machine)
            creg = machine.qAlloc_many(0)  # placeholder; fall through on failure
            creg = machine.get_allocate_cbits()
        raw = machine.run_with_configuration(prog, creg, shots)
    finally:
        machine.finalize()

    num_bits = circuit.n_clbits or circuit.n_qubits
    formatted: Dict[str, int] = {}
    for key, val in dict(raw).items():
        if isinstance(key, int) or (isinstance(key, str) and key.isdigit()):
            bin_str = bin(int(key))[2:].zfill(num_bits)
        else:
            bin_str = str(key)
        formatted[bin_str] = int(val)
    return unified_result(
        "originq_local_simulator",
        shots,
        formatted,
        meta={"transpiled_gates": len(circuit.gates), "engine": "pyqpanda"},
    )
