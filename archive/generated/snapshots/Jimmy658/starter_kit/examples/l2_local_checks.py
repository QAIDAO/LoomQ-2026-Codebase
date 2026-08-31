#!/usr/bin/env python3
"""Local L2 checks using a mock LLM.

These tests do not require an API key, but they verify the formal contract
shape: each production-like ``agent_chat_impl`` case completes at least one
successful LLM call before deterministic handlers return.
"""

from __future__ import annotations

import json
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import adapter  # noqa: E402
import l2_agent  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class MockLLM:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[list[dict]] = []

    def __call__(self, messages: list[dict]) -> dict:
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("mock LLM called more times than expected")
        content = self.responses.pop(0)
        return {"choices": [{"message": {"content": content}}]}


def run_agent(prompt: str, responses: list[str]) -> tuple[str, MockLLM]:
    mock = MockLLM(responses)
    reply = l2_agent.agent_chat_impl(prompt, llm_callable=mock, require_llm=True)
    return reply, mock


def semantic_result_for_counts(counts: dict[str, int], validator, intent: dict) -> l2_agent.ValidationResult:
    original_validate = l2_agent._validate_qasm_locally
    try:
        l2_agent._validate_qasm_locally = lambda qasm: l2_agent.ValidationResult(True, "mock counts", counts)
        return validator("mock qasm", intent)
    finally:
        l2_agent._validate_qasm_locally = original_validate


def main() -> int:
    print("Running mock-LLM L2 checks...")

    bell_balanced = semantic_result_for_counts({"00": 256, "11": 256}, l2_agent._validate_bell_semantics, {})
    require(bell_balanced.ok, "Balanced Bell counts should pass semantic fidelity")
    print("[PASS] Bell 50/50 semantic fidelity passes")

    bell_imbalanced = semantic_result_for_counts({"00": 507, "11": 5}, l2_agent._validate_bell_semantics, {})
    require(not bell_imbalanced.ok, "Imbalanced Bell counts should fail semantic fidelity")
    print("[PASS] Bell 99/1 semantic fidelity fails")

    bell_wrong_states = semantic_result_for_counts({"00": 250, "11": 250, "01": 12}, l2_agent._validate_bell_semantics, {})
    require(not bell_wrong_states.ok, "Bell counts with wrong states should fail semantic fidelity")
    print("[PASS] Bell wrong-state counts fail")

    ghz5_balanced = semantic_result_for_counts({"00000": 256, "11111": 256}, l2_agent._validate_ghz_semantics, {"num_qubits": 5})
    require(ghz5_balanced.ok, "Balanced GHZ-5 counts should pass semantic fidelity")
    print("[PASS] GHZ-5 50/50 semantic fidelity passes")

    ghz5_imbalanced = semantic_result_for_counts({"00000": 507, "11111": 5}, l2_agent._validate_ghz_semantics, {"num_qubits": 5})
    require(not ghz5_imbalanced.ok, "Imbalanced GHZ-5 counts should fail semantic fidelity")
    print("[PASS] GHZ-5 99/1 semantic fidelity fails")

    bell_reply, bell_mock = run_agent(
        "Please create a Bell state and measure it.",
        ['{"task_type":"generate","known_task":"bell","num_qubits":2,"constraints":{}}'],
    )
    require(len(bell_mock.calls) == 1, "Bell path must call LLM exactly once")
    require("LLM intent + deterministic known-task handler" in bell_reply, "Bell should use deterministic generator after LLM intent")
    require("OPENQASM 2.0;" in bell_reply and "00" in bell_reply and "11" in bell_reply, "Bell response missing QASM/counts")
    print("[PASS] Bell prompt calls LLM once and uses deterministic handler")

    ghz_reply, ghz_mock = run_agent(
        "Generate a 5-qubit GHZ state and measure all qubits.",
        ['{"task_type":"generate","known_task":"ghz","num_qubits":5,"constraints":{}}'],
    )
    require(len(ghz_mock.calls) == 1, "GHZ path must call LLM exactly once")
    require("qreg q[5];" in ghz_reply and "11111" in ghz_reply, "GHZ-5 response missing expected output")
    print("[PASS] GHZ-5 prompt calls LLM once and extracts n=5")

    explicit_ghz_reply, explicit_ghz_mock = run_agent(
        "Generate a 5 qubit GHZ state.",
        ['{"task_type":"generate","known_task":"ghz","num_qubits":3,"constraints":{}}'],
    )
    require(len(explicit_ghz_mock.calls) == 1, "Explicit GHZ prompt should call LLM once")
    require("qreg q[5];" in explicit_ghz_reply, "Explicit prompt qubit count should override wrong LLM count")
    print("[PASS] Explicit GHZ-5 prompt overrides wrong LLM num_qubits")

    word_ghz_reply, word_ghz_mock = run_agent(
        "Create a five-qubit GHZ state",
        ['{"task_type":"generate","known_task":"ghz","num_qubits":5,"constraints":{}}'],
    )
    require(len(word_ghz_mock.calls) == 1, "Word-number GHZ prompt should call LLM once")
    require("qreg q[5];" in word_ghz_reply, "Word-number GHZ should use LLM-supplied count instead of defaulting to 3")
    print("[PASS] English word-number GHZ uses LLM count")

    chinese_ghz_reply, chinese_ghz_mock = run_agent(
        "生成五比特 GHZ 态",
        ['{"task_type":"generate","known_task":"ghz","num_qubits":5,"constraints":{}}'],
    )
    require(len(chinese_ghz_mock.calls) == 1, "Chinese GHZ prompt should call LLM once")
    require("qreg q[5];" in chinese_ghz_reply, "Chinese word-number GHZ should use LLM-supplied count instead of defaulting to 3")
    print("[PASS] Chinese word-number GHZ uses LLM count")

    chinese_ghz_override_reply, chinese_ghz_override_mock = run_agent(
        "生成一个五比特 GHZ 态，并测量所有量子比特。",
        ['{"task_type":"generate","known_task":"ghz","num_qubits":3,"constraints":{}}'],
    )
    require(len(chinese_ghz_override_mock.calls) == 1, "Chinese explicit five-qubit GHZ should call LLM once")
    require("qreg q[5];" in chinese_ghz_override_reply and "GHZ-5 semantic validation passed" in chinese_ghz_override_reply, "Chinese 五比特 should override wrong LLM count")
    print("[PASS] Chinese 五比特 GHZ overrides wrong LLM num_qubits")

    chinese_ghz_five_quantum_bits_reply, _ = run_agent(
        "生成一个五个量子比特的 GHZ 态。",
        ['{"task_type":"generate","known_task":"ghz","num_qubits":3,"constraints":{}}'],
    )
    require("qreg q[5];" in chinese_ghz_five_quantum_bits_reply and "GHZ-5 semantic validation passed" in chinese_ghz_five_quantum_bits_reply, "Chinese 五个量子比特 should parse as 5")
    print("[PASS] Chinese 五个量子比特 GHZ parses as 5")

    chinese_ghz_ten_reply, _ = run_agent(
        "生成一个十比特 GHZ 态。",
        ['{"task_type":"generate","known_task":"ghz","num_qubits":3,"constraints":{}}'],
    )
    require("qreg q[10];" in chinese_ghz_ten_reply and "GHZ-10 semantic validation passed" in chinese_ghz_ten_reply, "Chinese 十比特 should parse as 10")
    print("[PASS] Chinese 十比特 GHZ parses as 10")

    chinese_ghz_fifteen_reply, _ = run_agent(
        "生成一个十五比特 GHZ 态。",
        ['{"task_type":"generate","known_task":"ghz","num_qubits":3,"constraints":{}}'],
    )
    require("qreg q[15];" in chinese_ghz_fifteen_reply and "GHZ-15 semantic validation passed" in chinese_ghz_fifteen_reply, "Chinese 十五比特 should parse as 15")
    print("[PASS] Chinese 十五比特 GHZ parses as 15")

    english_word_override_reply, _ = run_agent(
        "Generate a five-qubit GHZ state",
        ['{"task_type":"generate","known_task":"ghz","num_qubits":3,"constraints":{}}'],
    )
    require("qreg q[5];" in english_word_override_reply and "GHZ-5 semantic validation passed" in english_word_override_reply, "English five-qubit should override wrong LLM count")
    print("[PASS] English five-qubit GHZ overrides wrong LLM num_qubits")

    english_digit_override_reply, _ = run_agent(
        "Generate a 5-qubit GHZ state",
        ['{"task_type":"generate","known_task":"ghz","num_qubits":3,"constraints":{}}'],
    )
    require("qreg q[5];" in english_digit_override_reply and "GHZ-5 semantic validation passed" in english_digit_override_reply, "English 5-qubit should override wrong LLM count")
    print("[PASS] English 5-qubit GHZ still parses as 5")

    backend_reply, backend_mock = run_agent(
        "15 qubits, zero queue, free backend",
        [
            json.dumps(
                {
                    "task_type": "backend_selection",
                    "known_task": None,
                    "num_qubits": None,
                    "constraints": {"min_qubits": 15, "queue": "none", "free_only": True},
                }
            )
        ],
    )
    require(len(backend_mock.calls) == 1, "Backend path must call LLM exactly once")
    require("braket_local_simulator" in backend_reply, "Backend result should come from deterministic selector")
    require("deterministic backend filtering" in backend_reply, "Backend reply should explain deterministic filtering")
    print("[PASS] Backend prompt calls LLM once and uses deterministic selector")

    chinese_backend_fifteen_reply, _ = run_agent(
        "十五比特、零排队、免费，我应该选哪个后端？",
        ['{"task_type":"backend_selection","constraints":{"min_qubits":3,"queue":"none","free_only":true}}'],
    )
    require("braket_local_simulator" in chinese_backend_fifteen_reply, "Chinese 十五比特 backend prompt should keep simulator backends")
    require("No backend satisfies" not in chinese_backend_fifteen_reply, "Chinese 十五比特 backend prompt should not use wrong min_qubits")
    print("[PASS] Chinese 十五比特 backend constraints parse min_qubits=15")

    backend_conflict_reply, backend_conflict_mock = run_agent(
        "15 qubits, zero queue backend",
        [
            json.dumps(
                {
                    "task_type": "backend_selection",
                    "known_task": None,
                    "constraints": {"min_qubits": 50, "queue": "busy"},
                }
            )
        ],
    )
    require(len(backend_conflict_mock.calls) == 1, "Backend conflict prompt should call LLM once")
    require("braket_local_simulator" in backend_conflict_reply, "Deterministic backend constraints should override wrong LLM constraints")
    print("[PASS] Explicit backend constraints override wrong LLM constraints")

    backend_supplement_reply, backend_supplement_mock = run_agent(
        "Please find an option for about fifteen qubits with no waiting and no fee.",
        [
            json.dumps(
                {
                    "task_type": "backend_selection",
                    "known_task": None,
                    "constraints": {"min_qubits": 15, "queue": "none", "free_only": True},
                }
            )
        ],
    )
    require(len(backend_supplement_mock.calls) == 1, "Backend supplement prompt should call LLM once")
    require("braket_local_simulator" in backend_supplement_reply, "LLM should supplement constraints when deterministic parser is unsure")
    print("[PASS] LLM supplements fuzzy backend constraints")

    explicit_backend_wrong_llm_reply, explicit_backend_wrong_llm_mock = run_agent(
        "Which backend should I use for 15 qubits with zero queue?",
        ['{"task_type":"generate","known_task":null,"constraints":{}}'],
    )
    require(len(explicit_backend_wrong_llm_mock.calls) == 1, "Explicit backend selection should call LLM once")
    require("Recommended backend ID(s):" in explicit_backend_wrong_llm_reply, "Explicit backend selection should override wrong LLM task type")
    require("braket_local_simulator" in explicit_backend_wrong_llm_reply, "Explicit backend selection should still use deterministic backend filtering")
    print("[PASS] Explicit backend selection overrides wrong LLM task type")

    chinese_backend_wrong_llm_reply, chinese_backend_wrong_llm_mock = run_agent(
        "15比特、零排队，我应该选哪个后端？",
        ['{"task_type":"generate","known_task":null,"constraints":{}}'],
    )
    require(len(chinese_backend_wrong_llm_mock.calls) == 1, "Chinese explicit backend selection should call LLM once")
    require("Recommended backend ID(s):" in chinese_backend_wrong_llm_reply, "Chinese explicit backend selection should override wrong LLM task type")
    print("[PASS] Chinese explicit backend selection overrides wrong LLM task type")

    simulator_bell_reply, simulator_bell_mock = run_agent(
        "Generate a Bell circuit for a local simulator.",
        ['{"task_type":"generate","known_task":"bell","num_qubits":2,"constraints":{}}'],
    )
    require(len(simulator_bell_mock.calls) == 1, "Simulator Bell generation should call LLM once")
    require("LLM intent + deterministic known-task handler" in simulator_bell_reply, "Simulator mention should not lock prompt into backend selection")
    require("OPENQASM 2.0;" in simulator_bell_reply, "Simulator Bell prompt should generate QASM")
    print("[PASS] Simulator mention does not override Bell generation")

    hardware_ghz_reply, hardware_ghz_mock = run_agent(
        "Generate a 5-qubit GHZ circuit for quantum hardware.",
        ['{"task_type":"generate","known_task":"ghz","num_qubits":5,"constraints":{}}'],
    )
    require(len(hardware_ghz_mock.calls) == 1, "Hardware GHZ generation should call LLM once")
    require("qreg q[5];" in hardware_ghz_reply, "Hardware mention should not lock prompt into backend selection")
    print("[PASS] Hardware mention does not override GHZ generation")

    fuzzy_backend_type_reply, fuzzy_backend_type_mock = run_agent(
        "I need somewhere free with enough capacity and no waiting.",
        [
            json.dumps(
                {
                    "task_type": "backend_selection",
                    "known_task": None,
                    "constraints": {"min_qubits": 15, "queue": "none", "free_only": True},
                }
            )
        ],
    )
    require(len(fuzzy_backend_type_mock.calls) == 1, "Fuzzy backend type prompt should call LLM once")
    require("braket_local_simulator" in fuzzy_backend_type_reply, "LLM should supply backend_selection type for fuzzy backend prompts")
    print("[PASS] LLM supplies backend type when deterministic confidence is low")

    one_qubit_h_qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
measure q[0] -> c[0];
"""
    one_qubit_h_reply, one_qubit_h_mock = run_agent(
        "Create a 1-qubit circuit that applies H and measures the qubit.",
        [
            json.dumps(
                {
                    "task_type": "generate",
                    "known_task": "bell",
                    "num_qubits": 2,
                    "constraints": {},
                    "qasm": one_qubit_h_qasm,
                }
            )
        ],
    )
    require(len(one_qubit_h_mock.calls) == 1, "1-qubit H regression should call LLM once")
    require("qreg q[1];" in one_qubit_h_reply, "1-qubit H prompt should not be captured by Bell handler")
    require("LLM QASM + L1 local validation" in one_qubit_h_reply, "1-qubit H prompt should use generic QASM validation")
    print("[PASS] 1-qubit H prompt rejects wrong Bell intent")

    chinese_backend_hallucination_reply, chinese_backend_hallucination_mock = run_agent(
        "15比特、零排队、免费，我应该选哪个后端？",
        [
            json.dumps(
                {
                    "task_type": "backend_selection",
                    "constraints": {
                        "min_qubits": 15,
                        "queue": "none",
                        "free_only": True,
                        "real_hardware": True,
                    },
                }
            )
        ],
    )
    require(len(chinese_backend_hallucination_mock.calls) == 1, "Chinese backend hallucination regression should call LLM once")
    require("braket_local_simulator" in chinese_backend_hallucination_reply, "Hallucinated real_hardware should not remove simulator backend IDs")
    require("No backend satisfies" not in chinese_backend_hallucination_reply, "Hallucinated real_hardware should be ignored without prompt evidence")
    print("[PASS] Backend merge ignores hallucinated real_hardware")

    real_hardware_reply, real_hardware_mock = run_agent(
        "I need real quantum hardware. Which backend should I choose?",
        [
            json.dumps(
                {
                    "task_type": "backend_selection",
                    "constraints": {"real_hardware": True},
                }
            )
        ],
    )
    require(len(real_hardware_mock.calls) == 1, "Real hardware backend regression should call LLM once")
    require("originq_wukong" in real_hardware_reply and "spinq_cloud_qpu" in real_hardware_reply, "Explicit real hardware should preserve real_hardware constraint")
    print("[PASS] Explicit real hardware constraint is preserved")

    free_backend_reply, free_backend_mock = run_agent(
        "I need a free backend.",
        [
            json.dumps(
                {
                    "task_type": "backend_selection",
                    "constraints": {"free_only": True, "real_hardware": True},
                }
            )
        ],
    )
    require(len(free_backend_mock.calls) == 1, "Free backend hallucination regression should call LLM once")
    require("braket_local_simulator" in free_backend_reply, "Free backend prompt should not accept hallucinated real_hardware")
    print("[PASS] Free backend prompt rejects hallucinated real_hardware")

    bell_regression_reply, bell_regression_mock = run_agent(
        "Generate a Bell state and measure both qubits.",
        ['{"task_type":"generate","known_task":"bell","num_qubits":2,"constraints":{}}'],
    )
    require(len(bell_regression_mock.calls) == 1, "Bell regression should call LLM once")
    require("LLM intent + deterministic known-task handler" in bell_regression_reply and "qreg q[2];" in bell_regression_reply, "Bell known-task handler should still work")
    print("[PASS] Bell known-task handler still works")

    ghz_regression_reply, ghz_regression_mock = run_agent(
        "Generate a 5-qubit GHZ state and measure all qubits.",
        ['{"task_type":"generate","known_task":"ghz","num_qubits":5,"constraints":{}}'],
    )
    require(len(ghz_regression_mock.calls) == 1, "GHZ regression should call LLM once")
    require("LLM intent + deterministic known-task handler" in ghz_regression_reply and "qreg q[5];" in ghz_regression_reply, "GHZ-5 known-task handler should still work")
    print("[PASS] GHZ-5 known-task handler still works")

    generic_qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
x q[0];
measure q -> c;
"""
    generic_reply, generic_mock = run_agent(
        "Create a one-qubit circuit that always measures 1.",
        [json.dumps({"task_type": "generate", "known_task": None, "constraints": {}, "qasm": generic_qasm})],
    )
    require(len(generic_mock.calls) == 1, "Generic valid generation should use one LLM call")
    require("LLM QASM + L1 local validation" in generic_reply and '"1": 512' in generic_reply, "Generic QASM should validate locally")
    print("[PASS] Generic generation calls LLM and validates QASM")

    bad_qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
foo q[0];
measure q -> c;
"""
    repaired_qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
x q[0];
measure q -> c;
"""
    repair_reply, repair_mock = run_agent(
        "Fix this QASM so it measures 1.",
        [
            json.dumps({"task_type": "repair", "known_task": None, "constraints": {}, "qasm": bad_qasm}),
            repaired_qasm,
        ],
    )
    require(len(repair_mock.calls) == 2, "Repair path should call LLM exactly twice")
    require("LLM repair + L1 local validation" in repair_reply and '"1": 512' in repair_reply, "Repair result should pass local validation")
    print("[PASS] Bad QASM repair uses at most two LLM calls")

    malformed_reply, malformed_mock = run_agent(
        "Generate a 3-qubit GHZ state and measure all qubits.",
        ["I think this is a GHZ request, but here is not valid JSON."],
    )
    require(len(malformed_mock.calls) == 1, "Malformed structured output fallback must not call LLM again")
    require("qreg q[3];" in malformed_reply and "LLM intent + deterministic known-task handler" in malformed_reply, "Fallback should use local rules after successful LLM call")
    print("[PASS] Malformed structured output falls back after one successful LLM call")

    no_key_reply = adapter.agent_chat("Generate a 3-qubit GHZ state and measure all qubits")
    require("local deterministic development path" in no_key_reply.lower(), "No-key local dev path should remain available while L2 is disabled")
    print("[PASS] no-key local development path remains available")

    print("All mock-LLM L2 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
