
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from l3 import (
    compile_hybrid_l3,
)

from riscv_emulator import (
    TinyRISCVEmulator,
)


def run_classical(
    assembly,
    measurements,
):

    emulator = (
        TinyRISCVEmulator()
    )

    emulator.load_program(
        assembly
    )

    # IMPORTANT:
    #
    # load_program() resets all registers.
    # Therefore measurement registers must
    # be injected AFTER load_program().

    for index, value in (
        measurements.items()
    ):

        emulator.set_register(
            f"x{10 + index}",
            value,
        )

    return emulator.execute()


# ============================================================
# CASE 1
# Official-style Hybrid-QASM
# ============================================================


source = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[2];

h q[0];
measure q[0] -> c[0];

classical {

    if (c[0] == 1) {
        r1 = 100;
    } else {
        r1 = 10;
    }

    r1 = r1 + 5;
}

cx q[0], q[1];
"""


quantum_ops, assembly = (
    compile_hybrid_l3(
        source
    )
)


print()
print("=" * 70)
print("QUANTUM OPS")
print("=" * 70)

for operation in quantum_ops:
    print(operation)


print()
print("=" * 70)
print("RISC-V")
print("=" * 70)

print(assembly)


assert quantum_ops == [
    "h q[0];",
    "measure q[0] -> c[0];",
    "cx q[0], q[1];",
]


# c[0] = 0

state = run_classical(
    assembly,
    {
        0: 0,
    },
)

print()
print("c[0] = 0")
print(state)

assert (
    state.get(
        "x1",
        0,
    )
    == 15
)


# c[0] = 1

state = run_classical(
    assembly,
    {
        0: 1,
    },
)

print()
print("c[0] = 1")
print(state)

assert (
    state.get(
        "x1",
        0,
    )
    == 105
)


# ============================================================
# CASE 2
# != + nested if + subtraction + negative integer
# ============================================================


source = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[2];

measure q[1] -> c[1];

classical {

    r1 = 10;
    r2 = r1 - 3;

    if (c[1] != 0) {

        r3 = r2 + 5;

        if (r3 == 12) {
            r4 = -7;
        } else {
            r4 = 99;
        }

    } else {

        r3 = 0;
        r4 = 1;
    }
}
"""


quantum_ops, assembly = (
    compile_hybrid_l3(
        source
    )
)


print()
print("=" * 70)
print("NESTED RISC-V")
print("=" * 70)

print(assembly)


# c[1] = 1
#
# r1 = 10
# r2 = 7
# r3 = 12
# r4 = -7

state = run_classical(
    assembly,
    {
        1: 1,
    },
)

print()
print("c[1] = 1")
print(state)

assert (
    state.get("x1", 0)
    == 10
)

assert (
    state.get("x2", 0)
    == 7
)

assert (
    state.get("x3", 0)
    == 12
)

assert (
    state.get("x4", 0)
    == -7
)


# c[1] = 0
#
# r3 = 0
# r4 = 1

state = run_classical(
    assembly,
    {
        1: 0,
    },
)

print()
print("c[1] = 0")
print(state)

assert (
    state.get("x3", 0)
    == 0
)

assert (
    state.get("x4", 0)
    == 1
)


# ============================================================
# CASE 3
# Important self-reference regression
# ============================================================


source = """
OPENQASM 2.0;

qreg q[1];
creg c[1];

classical {
    r1 = 4;
    r2 = 10;

    r1 = r2 - r1;
}
"""


_, assembly = (
    compile_hybrid_l3(
        source
    )
)


state = run_classical(
    assembly,
    {},
)


assert (
    state.get("x1", 0)
    == 6
)


print()
print("=" * 70)
print("ALL L3 COMPILER TESTS PASSED")
print("=" * 70)
