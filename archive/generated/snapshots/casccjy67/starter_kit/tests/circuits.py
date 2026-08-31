"""Public test circuits from the LoomQ Starter Kit."""

BELL_STATE = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""

GHZ_3 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0], q[1];
cx q[1], q[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
"""

GHZ_5 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[5];
creg c[5];
h q[0];
cx q[0], q[1];
cx q[1], q[2];
cx q[2], q[3];
cx q[3], q[4];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
measure q[3] -> c[3];
measure q[4] -> c[4];
"""

QFT_4 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[4];
creg c[4];
h q[0];
h q[1];
h q[2];
h q[3];
cu1(pi/2) q[0], q[1];
cu1(pi/3) q[0], q[2];
cu1(pi/4) q[0], q[3];
cu1(pi/2) q[1], q[2];
cu1(pi/3) q[1], q[3];
cu1(pi/2) q[2], q[3];
swap q[0], q[3];
swap q[1], q[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
measure q[3] -> c[3];
"""

GROVER_3 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
h q[1];
h q[2];
s q[2];
h q[2];
ccx q[0], q[1], q[2];
sdg q[2];
h q[2];
h q[0];
h q[1];
h q[2];
x q[0];
x q[1];
h q[2];
ccx q[0], q[1], q[2];
x q[0];
x q[1];
h q[0];
h q[1];
h q[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
"""

PUBLIC_CIRCUITS = {
    "Bell": BELL_STATE,
    "GHZ-3": GHZ_3,
}

ALL_CIRCUITS = {
    "Bell": BELL_STATE,
    "GHZ-3": GHZ_3,
    "GHZ-5": GHZ_5,
    "QFT-4": QFT_4,
    "Grover-3": GROVER_3,
}

HYBRID_EXAMPLE = """OPENQASM 2.0;
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
