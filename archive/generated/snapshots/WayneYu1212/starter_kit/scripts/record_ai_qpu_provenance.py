#!/usr/bin/env python3
"""Record one real LLM -> verified Bell program -> completed-QPU provenance link."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FILES = ROOT / "starter_kit" / "evidence" / "files"
OUT = FILES / "originq_tomography_bell_phi_plus-ai-qpu-provenance.json"
TOMOGRAPHY_JOB = "F7287E16E8478E4DB5051105468DB638"
PROMPT = "制备一个两比特 Bell Phi+ 态。"


def main() -> int:
    from starter_kit.llm_client import chat_completion
    from starter_kit.loomq.agent.prompts import SYSTEM_PROMPT
    from starter_kit.loomq.agent.response import parse_agent_plan
    from starter_kit.loomq.agent.verifier import verify_qasm

    response = chat_completion([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": PROMPT},
    ])
    runtime_model = response.get("model")
    if runtime_model != "deepseek-v4-flash":
        raise RuntimeError("runtime response does not identify deepseek-v4-flash")
    content = response["choices"][0]["message"]["content"]
    plan = parse_agent_plan(content)
    if plan.task != "generate" or plan.qasm is None:
        raise RuntimeError("model did not generate a QASM plan")
    verified = verify_qasm(plan.qasm)
    circuit = verified.circuit
    gate_signature = [(gate.name, list(gate.qubits), list(gate.params)) for gate in circuit.gates]
    tomography_preparation = [("h", [0], []), ("cx", [0, 1], [])]
    logical_equivalent = (
        circuit.qubit_count == 2
        and gate_signature == tomography_preparation
        and all(abs(float(verified.distribution.get(bit, 0.0)) - target) < 1e-12 for bit, target in {
            "00": 0.5, "01": 0.0, "10": 0.0, "11": 0.5,
        }.items())
    )
    if not logical_equivalent:
        raise RuntimeError("verified AI Bell preparation is not logically equivalent to tomography preparation")
    safe_response: dict[str, Any] = {
        "id": response.get("id"),
        "model": runtime_model,
        "created": response.get("created"),
        "usage": response.get("usage"),
        "content": content,
    }
    payload = {
        "prompt": PROMPT,
        "runtime_model": runtime_model,
        "real_model_response": safe_response,
        "structured_plan": {
            "task": plan.task,
            "explanation": plan.explanation,
            "qasm": plan.qasm,
        },
        "loomq_verification": {
            "checks": list(verified.checks),
            "reference_distribution": verified.distribution,
        },
        "tomography_job_id": TOMOGRAPHY_JOB,
        "tomography_logical_preparation": tomography_preparation,
        "ai_gate_signature": gate_signature,
        "logical_equivalence": logical_equivalent,
        "measurement_boundary": "Tomography API measurements are required input mechanics and are excluded from the Bell-state preparation equivalence comparison.",
    }
    FILES.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("AI_QPU_PROVENANCE=PASS")
    print(f"runtime_model={runtime_model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
