from adapter import run, transpile


TARGETS = (
    "spinq",
    "braket",
    "originq",
)


def expect_failure(
    name: str,
    func,
):
    print()
    print("=" * 60)
    print(name)
    print("=" * 60)

    try:
        func()

    except Exception as exc:
        print(
            f"PASS -> "
            f"{type(exc).__name__}: {exc}"
        )
        return

    raise AssertionError(
        f"{name}: expected an exception, "
        f"but the call succeeded"
    )


# ============================================================
# 1. Unsupported target
# ============================================================

simple_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

h q[0];
measure q -> c;
"""

expect_failure(
    "Unsupported target",
    lambda: run(
        simple_qasm,
        "not_a_backend",
        100,
    )
)


# ============================================================
# 2. shots = 0
# ============================================================

for target in TARGETS:

    expect_failure(
        f"shots = 0 ({target})",
        lambda target=target: run(
            simple_qasm,
            target,
            0,
        )
    )


# ============================================================
# 3. shots < 0
# ============================================================

for target in TARGETS:

    expect_failure(
        f"shots = -1 ({target})",
        lambda target=target: run(
            simple_qasm,
            target,
            -1,
        )
    )


# ============================================================
# 4. Unsupported gate
#
# LoomQ whitelist does not contain Z.
# ============================================================

unsupported_gate_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

z q[0];

measure q -> c;
"""

expect_failure(
    "Unsupported gate: z",
    lambda: transpile(
        unsupported_gate_qasm,
        "spinq",
    )
)


# ============================================================
# 5. Qubit index out of range
#
# q[1] does not exist when qreg q[1].
# ============================================================

bad_qubit_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

x q[1];

measure q[0] -> c[0];
"""

expect_failure(
    "Qubit index out of range",
    lambda: transpile(
        bad_qubit_qasm,
        "spinq",
    )
)


# ============================================================
# 6. Classical-bit index out of range
# ============================================================

bad_cbit_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

x q[0];

measure q[0] -> c[1];
"""

expect_failure(
    "Classical-bit index out of range",
    lambda: transpile(
        bad_cbit_qasm,
        "spinq",
    )
)


# ============================================================
# 7. CX with wrong arity
#
# CX requires exactly 2 qubits.
# ============================================================

bad_cx_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[2];

cx q[0];

measure q -> c;
"""

expect_failure(
    "CX wrong arity",
    lambda: transpile(
        bad_cx_qasm,
        "spinq",
    )
)


# ============================================================
# 8. CCX with wrong arity
# ============================================================

bad_ccx_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[3];
creg c[3];

ccx q[0], q[1];

measure q -> c;
"""

expect_failure(
    "CCX wrong arity",
    lambda: transpile(
        bad_ccx_qasm,
        "spinq",
    )
)


# ============================================================
# 9. RY missing parameter
# ============================================================

ry_missing_parameter_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

ry q[0];

measure q -> c;
"""

expect_failure(
    "RY missing parameter",
    lambda: transpile(
        ry_missing_parameter_qasm,
        "spinq",
    )
)


# ============================================================
# 10. H incorrectly has a parameter
# ============================================================

h_extra_parameter_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

h(pi/2) q[0];

measure q -> c;
"""

expect_failure(
    "H has unexpected parameter",
    lambda: transpile(
        h_extra_parameter_qasm,
        "spinq",
    )
)


# ============================================================
# 11. Register measurement size mismatch
#
# q has 2 bits, c has only 1.
# ============================================================

bad_register_measure_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[1];

h q[0];

measure q -> c;
"""

expect_failure(
    "Register measurement size mismatch",
    lambda: transpile(
        bad_register_measure_qasm,
        "spinq",
    )
)


print()
print("=" * 60)
print("All L1 invalid-input tests passed.")
print("=" * 60)
