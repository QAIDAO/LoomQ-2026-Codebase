from starter_kit.adapter import run

qasm_bell = """
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""

# 测试 SpinQ
print("=== SpinQ 测试 ===")
result_spinq = run(qasm_bell, "spinq", 8192)
print(result_spinq)

# 测试 Braket
print("\n=== Braket 测试 ===")
result_braket = run(qasm_bell, "braket", 8192)
print(result_braket)