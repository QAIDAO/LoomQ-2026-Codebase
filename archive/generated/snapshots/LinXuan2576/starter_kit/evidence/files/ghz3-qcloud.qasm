// LoomQ 真机证据 - 量旋云平台版 GHZ-3 纠缠态（3 比特核磁 / 5 比特核磁）
// 按量旋云 QASM 编辑器语法最小化：无 creg、无 measure（平台自动测量）
OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
h q[0];
cx q[0], q[1];
cx q[0], q[2];
