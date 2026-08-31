from adapter import run


TARGETS = (
    "spinq",
    "braket",
    "originq",
)

SHOTS = 1000


def check_all_targets(
    name: str,
    qasm: str,
    expected_key: str,
):
    print()
    print("=" * 60)
    print(name)
    print("=" * 60)

    for target in TARGETS:

        result = run(
            qasm,
            target,
            SHOTS,
        )

        counts = result["counts"]

        print(
            f"{target:8s} -> {counts}"
        )

        assert counts.get(
            expected_key,
            0
        ) == SHOTS


# ------------------------------------------------------------
# pi
# RY(pi)|0> = |1>
# ------------------------------------------------------------

qasm_pi = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

ry(pi) q[0];

measure q -> c;
"""

check_all_targets(
    "RY(pi)",
    qasm_pi,
    "1",
)


# ------------------------------------------------------------
# 2*pi
#
# RY(2*pi)|0> = -|0>
# measurement still gives 0
# ------------------------------------------------------------

qasm_2pi = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

ry(2*pi) q[0];

measure q -> c;
"""

check_all_targets(
    "RY(2*pi)",
    qasm_2pi,
    "0",
)


# ------------------------------------------------------------
# pi/2 + pi/2
#
# two rotations compose to pi
# ------------------------------------------------------------

qasm_half = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

ry(pi/2) q[0];
ry(pi/2) q[0];

measure q -> c;
"""

check_all_targets(
    "RY(pi/2) twice",
    qasm_half,
    "1",
)


# ------------------------------------------------------------
# negative angle
#
# RY(-pi) also maps |0> to |1>
# up to global phase
# ------------------------------------------------------------

qasm_negative = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

ry(-pi) q[0];

measure q -> c;
"""

check_all_targets(
    "RY(-pi)",
    qasm_negative,
    "1",
)


# ------------------------------------------------------------
# decimal
# ------------------------------------------------------------

qasm_decimal = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

ry(3.141592653589793) q[0];

measure q -> c;
"""

check_all_targets(
    "RY(decimal pi)",
    qasm_decimal,
    "1",
)


print()
print("=" * 60)
print("All L1 parameter tests passed.")
print("=" * 60)
