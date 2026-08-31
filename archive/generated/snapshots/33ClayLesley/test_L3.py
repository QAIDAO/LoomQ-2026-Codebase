from starter_kit.adapter import compile_hybrid

hybrid_qasm = """
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

ops, asm = compile_hybrid(hybrid_qasm)
print("量子操作:", ops)
print("RISC-V 汇编:")
print(asm)