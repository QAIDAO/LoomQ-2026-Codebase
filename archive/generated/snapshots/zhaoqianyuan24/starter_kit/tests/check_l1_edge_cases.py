from adapter import run, transpile


TARGETS = (
    "spinq",
    "braket",
    "originq",
)

SHOTS = 1000


def check_counts(
    qasm: str,
    expected_key: str,
):
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
        ) == SHOTS, (
            f"{target}: expected "
            f"{expected_key}, got {counts}"
        )


# ============================================================
# Test 1
#
# q0 = 1
# q1 = 0
#
# but measurement is intentionally swapped:
#
# q0 -> c1
# q1 -> c0
#
# Therefore:
# c1 = 1
# c0 = 0
#
# output string must be:
# c1 c0 = "10"
# ============================================================

swapped_measure_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[2];

x q[0];

measure q[0] -> c[1];
measure q[1] -> c[0];
"""

print()
print("=" * 60)
print("Swapped measurement mapping")
print("=" * 60)

check_counts(
    swapped_measure_qasm,
    "10",
)


# ============================================================
# Test 2
#
# Classical register is larger than measured qubits.
#
# q0 = 1 -> c2
# q1 = 0 -> c0
#
# c1 is never written, therefore remains 0.
#
# output:
# c2 c1 c0
#  1  0  0
# -> "100"
# ============================================================

sparse_measure_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[3];

x q[0];

measure q[0] -> c[2];
measure q[1] -> c[0];
"""

print()
print("=" * 60)
print("Sparse classical-bit mapping")
print("=" * 60)

check_counts(
    sparse_measure_qasm,
    "100",
)


# ============================================================
# Test 3
#
# Result schema
# ============================================================

schema_qasm = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

x q[0];

measure q -> c;
"""

print()
print("=" * 60)
print("Result schema")
print("=" * 60)

required_fields = {
    "backend",
    "job_id",
    "shots",
    "counts",
    "bit_order",
    "timestamp",
}

for target in TARGETS:

    result = run(
        schema_qasm,
        target,
        SHOTS,
    )

    print(
        target,
        "->",
        result
    )

    assert required_fields.issubset(
        result.keys()
    )

    assert result["shots"] == SHOTS

    assert result["bit_order"] == "little"

    assert sum(
        result["counts"].values()
    ) == SHOTS


# ============================================================
# Test 4
#
# transpile() basic contract
# ============================================================

print()
print("=" * 60)
print("Transpile output headers")
print("=" * 60)

spinq_ir = transpile(
    schema_qasm,
    "spinq"
)

braket_ir = transpile(
    schema_qasm,
    "braket"
)

originq_ir = transpile(
    schema_qasm,
    "originq"
)

assert spinq_ir.startswith(
    "OPENQASM 2.0;"
)

assert braket_ir.startswith(
    "OPENQASM 3"
)

assert originq_ir.startswith(
    "QINIT "
)

print("SpinQ header   : OK")
print("Braket header  : OK")
print("OriginQ header : OK")


print()
print("=" * 60)
print("All L1 edge-case tests passed.")
print("=" * 60)
