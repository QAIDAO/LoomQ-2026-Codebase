// LoomQ 参赛电路：Grover-3（3 比特 Grover 搜索，标记态 |11>）
// 2 search qubits (q0,q1) + 1 ancilla (q2) kept in |->. Oracle = CCX(q0,q1,q2)
// flips the ancilla when the state is |11>, giving a -1 phase on the marked
// state. One Grover iteration is optimal for N=4 search space, so measuring
// q0,q1 should yield |11> with near-certainty.
OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[2];
x q[2];
h q[2];
h q[0];
h q[1];
ccx q[0],q[1],q[2];
h q[0];
h q[1];
x q[0];
x q[1];
ccx q[0],q[1],q[2];
x q[0];
x q[1];
h q[0];
h q[1];
h q[2];
x q[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
