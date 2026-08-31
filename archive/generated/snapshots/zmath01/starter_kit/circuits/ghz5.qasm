// LoomQ 参赛电路：GHZ-5（5 比特最大纠缠态）
// GHZ state |00000> + |11111> over 5 qubits. Public-circuit analogue of the
// official GHZ-5 hidden test: h q0 then cx chain, full measurement.
OPENQASM 2.0;
include "qelib1.inc";
qreg q[5];
creg c[5];
h q[0];
cx q[0],q[1];
cx q[0],q[2];
cx q[0],q[3];
cx q[0],q[4];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
measure q[3] -> c[3];
measure q[4] -> c[4];
