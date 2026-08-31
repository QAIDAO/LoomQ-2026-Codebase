from adapter import agent_chat, run
from l1 import parse_qasm2


# ============================================================
# Helpers
# ============================================================

def title(name):
    print()
    print("=" * 78)
    print(name)
    print("=" * 78)


def get_counts(qasm, shots=1000):
    result = run(
        qasm,
        "originq",
        shots,
    )

    return result["counts"]


def assert_only_states(
    counts,
    allowed,
    min_good_fraction=0.95,
):
    total = sum(
        counts.values()
    )

    good = sum(
        count
        for state, count in counts.items()
        if state in allowed
    )

    fraction = (
        good / total
        if total
        else 0.0
    )

    assert fraction >= min_good_fraction, (
        f"Expected states {allowed}, "
        f"got {counts}, "
        f"good fraction={fraction}"
    )


def ask_qasm(name, prompt):
    title(name)

    result = agent_chat(
        prompt
    )

    print(result)

    # Syntax / LoomQ gate validation.
    parse_qasm2(
        result
    )

    return result


def ask_backend(
    name,
    prompt,
    expected_ids=None,
    expect_no_match=False,
):
    title(name)

    result = agent_chat(
        prompt
    )

    print(result)

    if expect_no_match:
        assert (
            "No backend" in result
            or "no backend" in result
        ), result

        return

    assert expected_ids

    assert any(
        backend_id in result
        for backend_id in expected_ids
    ), (
        f"Expected one of {expected_ids}, "
        f"got:\n{result}"
    )


# ============================================================
# 1-4: Natural language -> QASM
# ============================================================

qasm = ask_qasm(
    "CASE 1 - Bell state / English",
    """
Generate an OpenQASM 2.0 circuit that prepares
a 2-qubit Bell state and measures both qubits.
""",
)

counts = get_counts(qasm)

print("counts =", counts)

assert_only_states(
    counts,
    {"00", "11"},
)


qasm = ask_qasm(
    "CASE 2 - GHZ / Chinese",
    """
生成一个 3 比特 GHZ 态，并对三个量子比特全部进行测量。
返回完整 OpenQASM 2.0。
""",
)

counts = get_counts(qasm)

print("counts =", counts)

assert_only_states(
    counts,
    {"000", "111"},
)


qasm = ask_qasm(
    "CASE 3 - Deterministic X",
    """
Generate a one-qubit OpenQASM 2.0 circuit.
Prepare |1> from |0> using an X gate and measure it.
""",
)

counts = get_counts(qasm)

print("counts =", counts)

assert_only_states(
    counts,
    {"1"},
    min_good_fraction=0.99,
)


qasm = ask_qasm(
    "CASE 4 - Parameterized gates",
    """
Generate valid OpenQASM 2.0 for a two-qubit circuit
using RY(pi/2), RZ(-pi/4), and CU1(pi/3), followed
by measurements of both qubits.
""",
)

# Parsing above is the important assertion for this case.


# ============================================================
# 5-8: QASM repair
# ============================================================

qasm = ask_qasm(
    "CASE 5 - Repair bad CCX arity",
    """
Repair the following circuit.

Its intended state is a 3-qubit GHZ state.

OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];

h q[0];
ccx q[0],q[1];
measure q -> c;
""",
)

counts = get_counts(qasm)

print("counts =", counts)

assert_only_states(
    counts,
    {"000", "111"},
)


qasm = ask_qasm(
    "CASE 6 - Repair out-of-range qubit",
    """
Repair this OpenQASM 2.0 circuit so that it prepares
a Bell state and measures both qubits.

OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];

h q[0];
cx q[0],q[2];
measure q -> c;
""",
)

counts = get_counts(qasm)

print("counts =", counts)

assert_only_states(
    counts,
    {"00", "11"},
)


qasm = ask_qasm(
    "CASE 7 - Repair wrong measurement target",
    """
Fix this circuit so it prepares |1> and measures
that qubit correctly.

OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];

x q[0];
measure q[1] -> c[0];
""",
)

counts = get_counts(qasm)

print("counts =", counts)

assert_only_states(
    counts,
    {"1"},
    min_good_fraction=0.99,
)


qasm = ask_qasm(
    "CASE 8 - Repair incomplete QASM",
    """
The following circuit is intended to make a Bell state,
but it is incomplete. Repair it into complete valid
OpenQASM 2.0 and measure both qubits.

qreg q[2];
h q[0];
cx q[0],q[1];
""",
)

counts = get_counts(qasm)

print("counts =", counts)

assert_only_states(
    counts,
    {"00", "11"},
)


# ============================================================
# 9-12: Backend recommendation
# ============================================================

ask_backend(
    "CASE 9 - Unique local 28-qubit backend",
    """
I need a 28-qubit circuit to run locally.
It must be completely free, have no queue,
and require no account.

Which LoomQ backend should I use?
""",
    {
        "originq_local_simulator",
    },
)


ask_backend(
    "CASE 10 - Multiple valid no-queue backends",
    """
I need a backend for a 15-qubit circuit.
The only additional requirement is that there
must be no queue.
""",
    {
        "spinq_taurus_simulator",
        "originq_local_simulator",
        "braket_local_simulator",
    },
)


ask_backend(
    "CASE 11 - Free real QPU",
    """
I need real quantum hardware with at least 5 qubits.
I do not want a paid backend; a free quota is acceptable.

Recommend a LoomQ backend.
""",
    {
        "spinq_cloud_qpu",
        "originq_wukong",
    },
)


ask_backend(
    "CASE 12 - Impossible local request",
    """
I need a local 100-qubit simulator.
It must be free and require no account.

Which LoomQ backend should I use?
""",
    expect_no_match=True,
)


print()
print("=" * 78)
print("ALL 12 REAL L2 REGRESSION CASES PASSED")
print("=" * 78)
