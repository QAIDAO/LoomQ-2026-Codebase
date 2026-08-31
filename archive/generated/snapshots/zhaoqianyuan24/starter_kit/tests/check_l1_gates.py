from adapter import run


TARGETS = (
    "spinq",
    "braket",
    "originq",
)

SHOTS = 1000


def run_qasm(
    qasm: str,
    target: str,
    shots: int = SHOTS,
):
    result = run(
        qasm,
        target,
        shots
    )

    return result["counts"]


def probability(
    counts: dict,
    bitstring: str,
) -> float:
    total = sum(counts.values())

    return (
        counts.get(bitstring, 0)
        / total
    )


def assert_probability(
    counts: dict,
    bitstring: str,
    expected: float,
    tolerance: float = 0.05,
):
    actual = probability(
        counts,
        bitstring
    )

    assert abs(actual - expected) < tolerance, (
        f"{bitstring}: "
        f"expected {expected}, "
        f"got {actual}, "
        f"counts={counts}"
    )


def run_test(
    name: str,
    qasm: str,
    checker,
):
    print()
    print("=" * 60)
    print(name)
    print("=" * 60)

    for target in TARGETS:

        counts = run_qasm(
            qasm,
            target
        )

        print(
            f"{target:8s} -> {counts}"
        )

        checker(counts)


# ============================================================
# X
# |0> -> |1>
# ============================================================

x_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

x q[0];

measure q -> c;
"""

run_test(
    "X gate",
    x_qasm,
    lambda counts:
        assert_probability(
            counts,
            "1",
            1.0,
            0.01,
        )
)


# ============================================================
# Bell = H + CX
# ============================================================

bell_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[2];

h q[0];
cx q[0], q[1];

measure q -> c;
"""


def check_bell(counts):
    assert_probability(
        counts,
        "00",
        0.5,
        0.06,
    )

    assert_probability(
        counts,
        "11",
        0.5,
        0.06,
    )


run_test(
    "H + CX (Bell)",
    bell_qasm,
    check_bell
)


# ============================================================
# SWAP
#
# q0=1 q1=0
#      ↓
# q0=0 q1=1
#
# output = c1 c0 = 10
# ============================================================

swap_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[2];

x q[0];
swap q[0], q[1];

measure q -> c;
"""

run_test(
    "SWAP",
    swap_qasm,
    lambda counts:
        assert_probability(
            counts,
            "10",
            1.0,
            0.01,
        )
)


# ============================================================
# CCX
# ============================================================

ccx_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[3];
creg c[3];

x q[0];
x q[1];

ccx q[0], q[1], q[2];

measure q -> c;
"""

run_test(
    "CCX",
    ccx_qasm,
    lambda counts:
        assert_probability(
            counts,
            "111",
            1.0,
            0.01,
        )
)


# ============================================================
# RY(pi)
# ============================================================

ry_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

ry(pi) q[0];

measure q -> c;
"""

run_test(
    "RY(pi)",
    ry_qasm,
    lambda counts:
        assert_probability(
            counts,
            "1",
            1.0,
            0.01,
        )
)


# ============================================================
# RZ(pi)
#
# H -> RZ(pi) -> H
# should produce |1>
# ============================================================

rz_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

h q[0];
rz(pi) q[0];
h q[0];

measure q -> c;
"""

run_test(
    "RZ(pi)",
    rz_qasm,
    lambda counts:
        assert_probability(
            counts,
            "1",
            1.0,
            0.01,
        )
)


# ============================================================
# S individually:
#
# S^2 = Z
# H -> Z -> H = X
# ============================================================

s_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

h q[0];

s q[0];
s q[0];

h q[0];

measure q -> c;
"""

run_test(
    "S gate",
    s_qasm,
    lambda counts:
        assert_probability(
            counts,
            "1",
            1.0,
            0.01,
        )
)


# ============================================================
# SDG individually:
#
# SDG^2 = Z up to global phase
# ============================================================

sdg_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

h q[0];

sdg q[0];
sdg q[0];

h q[0];

measure q -> c;
"""

run_test(
    "SDG gate",
    sdg_qasm,
    lambda counts:
        assert_probability(
            counts,
            "1",
            1.0,
            0.01,
        )
)


# ============================================================
# T individually:
#
# T^4 = Z
# ============================================================

t_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

h q[0];

t q[0];
t q[0];
t q[0];
t q[0];

h q[0];

measure q -> c;
"""

run_test(
    "T gate",
    t_qasm,
    lambda counts:
        assert_probability(
            counts,
            "1",
            1.0,
            0.01,
        )
)


# ============================================================
# TDG individually:
#
# TDG^4 = Z up to global phase
# ============================================================

tdg_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

h q[0];

tdg q[0];
tdg q[0];
tdg q[0];
tdg q[0];

h q[0];

measure q -> c;
"""

run_test(
    "TDG gate",
    tdg_qasm,
    lambda counts:
        assert_probability(
            counts,
            "1",
            1.0,
            0.01,
        )
)


# ============================================================
# CU1(pi/2)
#
# Expected:
# 00 -> 0.625
# 01 -> 0.125
# 10 -> 0.125
# 11 -> 0.125
# ============================================================

cu1_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[2];

h q[0];
h q[1];

cu1(pi/2) q[0], q[1];

h q[0];
h q[1];

measure q -> c;
"""


def check_cu1(counts):
    assert_probability(
        counts,
        "00",
        0.625,
        0.06,
    )

    assert_probability(
        counts,
        "01",
        0.125,
        0.06,
    )

    assert_probability(
        counts,
        "10",
        0.125,
        0.06,
    )

    assert_probability(
        counts,
        "11",
        0.125,
        0.06,
    )


run_test(
    "CU1(pi/2)",
    cu1_qasm,
    check_cu1
)


print()
print("=" * 60)
print("All L1 semantic tests passed on all targets.")
print("=" * 60)
