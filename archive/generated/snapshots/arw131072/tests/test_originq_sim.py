import os
# 确保环境变量未被设置或设为0
os.environ.pop("ORIGINQ_USE_WUKONG", None)
os.environ["ORIGINQ_USE_WUKONG"] = "0"

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

result = run(qasm_bell, "originq", 1024)
print(result)