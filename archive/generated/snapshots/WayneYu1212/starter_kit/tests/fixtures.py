"""Independent QASM fixtures that never call LoomQ production builders."""

from __future__ import annotations

import random


GHZ5_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[5];
creg c[5];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
cx q[2],q[3];
cx q[3],q[4];
measure q -> c;
"""


QFT_LIKE_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[4];
creg c[4];
x q[0];
x q[2];
h q[0];
cu1(pi/2) q[1],q[0];
cu1(pi/4) q[2],q[0];
h q[1];
cu1(pi/2) q[2],q[1];
cu1(pi/4) q[3],q[1];
h q[2];
cu1(pi/2) q[3],q[2];
h q[3];
swap q[0],q[3];
swap q[1],q[2];
measure q -> c;
"""


GROVER_LIKE_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0]; h q[1]; h q[2];
h q[2]; ccx q[0],q[1],q[2]; h q[2];
h q[0]; h q[1]; h q[2];
x q[0]; x q[1]; x q[2];
h q[2]; ccx q[0],q[1],q[2]; h q[2];
x q[0]; x q[1]; x q[2];
h q[0]; h q[1]; h q[2];
measure q -> c;
"""


def random_qasm(seed: int, *, qubits: int = 5, depth: int = 24) -> str:
    generator = random.Random(seed)
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{qubits}];",
        f"creg c[{qubits}];",
        "h q[0];",
    ]
    one_qubit = ("h", "x", "s", "sdg", "t", "tdg")
    parameterized = ("rz", "ry")
    angles = ("pi/7", "-pi/3", "0.37", "3*pi/8")
    families = ("single", "rotation", "cx", "cu1", "swap", "ccx")
    for _ in range(depth):
        family = generator.choice(families)
        if family == "single":
            lines.append(f"{generator.choice(one_qubit)} q[{generator.randrange(qubits)}];")
        elif family == "rotation":
            lines.append(
                f"{generator.choice(parameterized)}({generator.choice(angles)}) "
                f"q[{generator.randrange(qubits)}];"
            )
        elif family in {"cx", "cu1", "swap"}:
            first, second = generator.sample(range(qubits), 2)
            parameter = f"({generator.choice(angles)})" if family == "cu1" else ""
            lines.append(f"{family}{parameter} q[{first}],q[{second}];")
        else:
            first, second, third = generator.sample(range(qubits), 3)
            lines.append(f"ccx q[{first}],q[{second}],q[{third}];")
    lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"
