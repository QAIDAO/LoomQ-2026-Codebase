from adapter import compile_hybrid

# Test 1: with if/else
test1 = """OPENQASM 2.0;
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
cx q[0], q[1];"""

quantum, asm = compile_hybrid(test1)
print("=== TEST 1: if/else ===")
print("QUANTUM:", quantum)
print("ASSEMBLY:")
print(asm)
print()

# Test 2: if without else
test2 = """OPENQASM 2.0;
qreg q[1];
creg c[1];
h q[0];
measure q[0] -> c[0];
classical {
    if (c[0] == 1) {
        r1 = 100;
    }
    r1 = r1 + 5;
}"""

quantum, asm = compile_hybrid(test2)
print("=== TEST 2: if without else ===")
print("QUANTUM:", quantum)
print("ASSEMBLY:")
print(asm)