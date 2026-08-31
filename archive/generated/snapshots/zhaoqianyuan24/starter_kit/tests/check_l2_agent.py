import l2.agent as agent

from adapter import (
    agent_chat,
    run,
)


# ============================================================
# Helpers
# ============================================================

def run_counts(
    qasm: str,
    shots: int = 1000,
):
    result = run(
        qasm,
        "originq",
        shots,
    )

    return result["counts"]


def assert_ghz3(
    qasm: str,
):
    counts = run_counts(
        qasm,
        shots=1000,
    )

    print(
        "GHZ counts =",
        counts
    )

    unexpected = (
        set(counts)
        - {"000", "111"}
    )

    assert not unexpected, (
        f"Unexpected GHZ states: "
        f"{unexpected}"
    )

    assert counts.get(
        "000",
        0
    ) > 300

    assert counts.get(
        "111",
        0
    ) > 300


# ============================================================
# Test 1
# QASM generation
# ============================================================

print()
print("=" * 60)
print("L2 generation")
print("=" * 60)


def fake_generation(
    messages,
    timeout,
):
    return """
LOOMQ_TASK: QASM
OPENQASM 2.0;
include "qelib1.inc";

qreg q[3];
creg c[3];

h q[0];
cx q[0], q[1];
cx q[1], q[2];

measure q -> c;
"""


agent.call_llm = fake_generation

generated_qasm = agent_chat(
    "Generate a 3-qubit GHZ state "
    "and measure all qubits."
)

print(generated_qasm)

assert (
    "LOOMQ_TASK:"
    not in generated_qasm
)

assert_ghz3(
    generated_qasm
)

print("PASS")


# ============================================================
# Test 2
# QASM repair + validation retry
# ============================================================

print()
print("=" * 60)
print("L2 repair")
print("=" * 60)

repair_replies = [
    """
LOOMQ_TASK: QASM
OPENQASM 2.0;
include "qelib1.inc";

qreg q[3];
creg c[3];

h q[0];
ccx q[0], q[1];

measure q -> c;
""",

    """
LOOMQ_TASK: QASM
OPENQASM 2.0;
include "qelib1.inc";

qreg q[3];
creg c[3];

h q[0];
cx q[0], q[1];
cx q[1], q[2];

measure q -> c;
"""
]

repair_calls = 0


def fake_repair(
    messages,
    timeout,
):
    global repair_calls

    repair_calls += 1

    return repair_replies.pop(0)


agent.call_llm = fake_repair

repaired_qasm = agent_chat(
    """
Fix this QASM. It is intended to
create a 3-qubit GHZ state.
"""
)

print(repaired_qasm)

assert repair_calls == 2

assert_ghz3(
    repaired_qasm
)

print("PASS")


# ============================================================
# Test 3
# Backend recommendation routing
# ============================================================

print()
print("=" * 60)
print("L2 backend recommendation")
print("=" * 60)


backend_replies = [
    """
LOOMQ_TASK: BACKEND
LOOMQ_ACTION: GET_BACKEND_CAPABILITIES
""",
    """
LOOMQ_TASK: BACKEND
LOOMQ_DECISION:
{
  "status": "selected",
  "backend_id": "originq_local_simulator",
  "constraints": {
    "platform": "originq",
    "local": true,
    "simulator": true
  },
  "reason": "OriginQ's local CPUQVM satisfies the request."
}
""",
]


def fake_backend(
    messages,
    timeout,
):
    return backend_replies.pop(0)


agent.call_llm = fake_backend

backend_reply = agent_chat(
    "Recommend a suitable backend."
)

print(backend_reply)

assert (
    "LOOMQ_TASK:"
    not in backend_reply
)

assert (
    "originq_local_simulator"
    in backend_reply
)

print("PASS")


# ============================================================
# Test 4
# Protocol violation -> retry
# ============================================================

print()
print("=" * 60)
print("L2 protocol retry")
print("=" * 60)

protocol_replies = [
    "Sure, I can help you with that.",

    """
LOOMQ_TASK: QASM
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

x q[0];

measure q -> c;
"""
]

protocol_calls = 0


def fake_protocol(
    messages,
    timeout,
):
    global protocol_calls

    protocol_calls += 1

    return protocol_replies.pop(0)


agent.call_llm = fake_protocol

protocol_result = agent_chat(
    "Prepare |1> and measure it."
)

print(protocol_result)

assert protocol_calls == 2

counts = run_counts(
    protocol_result,
    shots=100,
)

assert counts == {
    "1": 100
}

print("PASS")


print()
print("=" * 60)
print("All L2 agent control-flow tests passed.")
print("=" * 60)
