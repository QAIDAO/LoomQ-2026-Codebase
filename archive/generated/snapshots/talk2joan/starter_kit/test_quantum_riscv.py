#!/usr/bin/env python3
"""End-to-end tests for the Quantum eXtension (QX) emulator.

Run:  python test_quantum_riscv.py
Every expected probability is recomputed here with the same math the
emulator uses, so the assertions are exact-by-construction.
"""

import math
import sys

try:
    from .riscv_quantum_emulator import QuantumRISCVEmulator
except ImportError:
    from riscv_quantum_emulator import QuantumRISCVEmulator

PASS = 0


def run_asm(asm):
    emu = QuantumRISCVEmulator()
    emu.load_program(asm)
    return emu.execute()


def expect(cond, name, detail=""):
    global PASS
    if cond:
        PASS += 1
        print("[PASS] %s" % name)
    else:
        print("[FAIL] %s %s" % (name, detail))
        sys.exit(1)


def p1_of(theta_rad):
    return int(round(math.sin(theta_rad / 2) ** 2 * 1e6))


# T1: Hadamard -> exactly 50%
st = run_asm(".qubits 2\nqh q0\nqprob x1, q0\n")
expect(st.get("x1") == 500000, "T1 hadamard 50/50", st)

# T2: Pauli-X flips |0> -> |1>
st = run_asm(".qubits 3\nqx q1\nqprob x2, q1\n")
expect(st.get("x2") == 1000000, "T2 x-flip", st)

# T3: CNOT entanglement marginals
st = run_asm(".qubits 2\nqh q0\nqcx q0, q1\n"
             "qprob x3, q0\nqprob x4, q1\n")
expect(st.get("x3") == 500000 and st.get("x4") == 500000,
       "T3 bell marginals", st)

# T4: Rz phase made visible by interference (h - rz(pi) - h => flip)
theta_mrad = 3142
exp = round((1 - math.cos(theta_mrad / 1000)) / 2 * 1e6)
st = run_asm(".qubits 1\nqh q0\nqrz %d, q0\nqh q0\nqprob x5, q0\n"
             % theta_mrad)
expect(st.get("x5") == exp, "T4 rz interference (%d)" % exp, st)

# T5: register-sourced rotation equals immediate rotation
imm = 785
exp = p1_of(imm / 1000.0)
st = run_asm(".qubits 1\nqry %d, q0\nqprob x6, q0\n" % imm)
expect(st.get("x6") == exp, "T5a immediate rotation (%d)" % exp, st)
st = run_asm(".qubits 1\nli x5, %d\nqry x5, q0\nqprob x6, q0\n" % imm)
expect(st.get("x6") == exp, "T5b register rotation (%d)" % exp, st)

# T6: THE feedback loop - classical code reads a quantum probability
#     and branches on it (impossible in plain Hybrid-QASM)
asm = (".qubits 1\n"
       "qry %(imm)d, q0\n"
       "qprob x6, q0\n"
       "li x7, %(exp)d\n"
       "beq x6, x7, MATCH\n"
       "li x8, 0\n"
       "j DONE\n"
       "MATCH:\n"
       "li x8, 1\n"
       "li x9, 42\n"
       "DONE:\n") % {"imm": imm, "exp": exp}
st = run_asm(asm)
expect(st.get("x8") == 1 and st.get("x9") == 42,
       "T6 classical branch on quantum probability", st)

# T7: official classic subset still works on this emulator (inheritance)
official = """
li x1, 5
li x2, 10
beq x1, x2, EQUAL
add x3, x1, x2
j END
EQUAL:
sub x3, x2, x1
END:
addi x3, x3, 1
"""
st = run_asm(official)
expect(st.get("x3") == 16, "T7 official classic subset inherited", st)

print("\nQX E2E: %d checks passed - READY" % PASS)
