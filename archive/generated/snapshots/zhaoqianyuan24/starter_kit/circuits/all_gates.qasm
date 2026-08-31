OPENQASM 2.0;
include "qelib1.inc";

qreg q[3];
creg c[3];

h q[0];
x q[1];

s q[0];
sdg q[0];

t q[1];
tdg q[1];

ry(pi/4) q[0];
rz(-pi/3) q[1];

cx q[0], q[1];
cu1(pi/5) q[1], q[2];
swap q[0], q[2];
ccx q[0], q[1], q[2];

measure q -> c;
