#!/usr/bin/env python3
"""End-to-end test for the custom quantum RISC-V extension (Bonus, +8).

Runs on QuantumRISCVEmulator (fork of the official riscv_emulator.py). Covers:
  1. Bell correlation  (qrun  → outcome ∈ {00, 11})
  2. GHZ-3 correlation (qrun  → outcome ∈ {000, 111})
  3. Probability check (qcount → P(00) ≈ 0.5, tolerance for 8192 shots)
  4. Parameterized RY (qry + qcount → deterministic |1>, all shots match)
  5. Parameterized RZ (qrz + qcount → P(0) ≈ (2+√2)/4)
  6. Toffoli control  (qtof → deterministic |111>)
  7. Cross-check vs L1 backends (Hellinger >= 0.97 for cu1 circuit)

Run:  python3 starter_kit/test_quantum_riscv.py
"""

import math
import sys

sys.path.insert(0, "starter_kit")

from riscv_quantum_emulator import (QuantumRISCVEmulator, QuantumState,
                                    encode_instruction, decode_instruction,
                                    OPC_GATE, OPC_CTRL)


def check_encode_decode():
    """Verify the 32-bit custom encoding round-trips and uses the right opcode
    space (custom-0 0x0B gates / custom-1 0x7B control) — proves the encoding
    is not just documentation but flows through the execution pipeline."""
    from riscv_quantum_emulator import _F3, _F7
    cases = [("qh", (0,)), ("qx", (1,)), ("qcnot", (0, 1)), ("qswap", (0, 3)),
             ("qrz", (2, "r4")), ("qry", (2, "r4")), ("qcu1", (0, 1, "r4")),
             ("qtof", (0, 1, 2)), ("qrun", ("r1", "r3")), ("qcount", ("r1", "r3", "r2"))]
    for m, ops in cases:
        word = encode_instruction(m, ops)
        dm, dops = decode_instruction(word)
        if dm != m:
            return False, "opcode mismatch: %s -> %s" % (m, dm)
        expected = []
        for o in ops:
            s = str(o).lower()
            expected.append(int(s[1:]) if s.startswith(("x", "r")) else int(o))
        if list(dops) != expected:
            return False, "operand mismatch: %s %s -> %s" % (m, ops, dops)
        opcode = word & 0x7F
        want = OPC_GATE if m in _F3 else OPC_CTRL
        if opcode != want:
            return False, "wrong opcode space for %s: 0x%02x" % (m, opcode)
    return True, "10 instructions encode/decode round-trip with correct opcode/funct fields"


def run_program(lines, init=None):
    emu = QuantumRISCVEmulator()
    emu.load_program("\n".join(lines))
    for reg, val in (init or {}).items():
        emu.set_register(reg, val)
    return emu.execute()


def bell_program():
    return ["li r2, 0", "qh 0", "qcnot 0, 1", "qrun r1, r3"]


def ghz3_program():
    return ["li r2, 0", "qh 0", "qcnot 0, 1", "qcnot 1, 2", "qrun r1, r3"]


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print("[%s] %s %s" % (status, label, detail))
    return condition


def hellinger(p, q):
    states = set(p) | set(q)
    d = math.sqrt(sum((math.sqrt(p.get(s, 0.0)) - math.sqrt(q.get(s, 0.0))) ** 2
                      for s in states)) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - d))


def main():
    ok = True

    # 0. 32-bit encoding round-trip
    enc_ok, enc_detail = check_encode_decode()
    ok &= check("Encoding round-trip (opcode/funct fields)", enc_ok, enc_detail)

    # 1. Bell correlation
    all_ok = True
    for _ in range(5):
        out = run_program(bell_program(), {"r3": 8192}).get("x1", 0)
        all_ok &= out in (0, 3)
    ok &= check("Bell correlation (5 runs, x1 ∈ {0,3})", all_ok)

    # 2. GHZ-3 correlation
    all_ok = True
    for _ in range(5):
        out = run_program(ghz3_program(), {"r3": 8192}).get("x1", 0)
        all_ok &= out in (0, 7)
    ok &= check("GHZ-3 correlation (5 runs, x1 ∈ {0,7})", all_ok)

    # 3. P(00) via qcount ~ 0.5
    out = run_program(["li r2, 0", "qh 0", "qcnot 0, 1", "qcount r1, r3, r2"],
                      {"r3": 8192}).get("x1", 0)
    ok &= check("Bell P(00) ≈ 0.5 (qcount=%d, expect ≈4096)" % out,
                abs(out - 4096) <= 300)

    # 4. Parameterized RY(π/2): qh; qry(π/2) -> |1> deterministically
    out = run_program(["li r2, 1", "li r4, 500", "qh 0", "qry 0, r4",
                       "qcount r1, r3, r2"], {"r3": 8192}).get("x1", 0)
    ok &= check("RY(pi/2) gives |1> (qcount=%d, expect 8192)" % out, out == 8192)

    # 5. Parameterized RZ(pi/4): P(0) ≈ (2+√2)/4 ≈ 0.8536
    out = run_program(["li r2, 0", "li r4, 250", "qh 0", "qrz 0, r4", "qh 0",
                       "qcount r1, r3, r2"], {"r3": 8192}).get("x1", 0)
    expect = int(8192 * (2 + math.sqrt(2)) / 4)
    ok &= check("RZ(pi/4) P(0) ≈ 0.8536 (qcount=%d, expect≈%d)" % (out, expect),
                abs(out - expect) <= 300)

    # 6. Toffoli: qx 0; qx 1; qtof 0,1,2 -> |111>
    out = run_program(["li r2, 0", "qx 0", "qx 1", "qtof 0, 1, 2",
                       "qrun r1, r3"], {"r3": 8192}).get("x1", 0)
    ok &= check("Toffoli |111> (x1=%d, expect 7)" % out, out == 7)

    # 7. Cross-check vs L1 braket backend on a cu1 circuit
    from riscv_quantum_emulator import QuantumState
    from agent import run_backend

    qasm = (
        "OPENQASM 2.0;\ninclude \"qelib1.inc\";\n"
        "qreg q[2];\ncreg c[2];\n"
        "h q[0];\nh q[1];\ncu1(pi) q[0], q[1];\nh q[0];\nh q[1];\nmeasure q -> c;\n"
    )
    state = QuantumState(2)
    state.h(0)
    state.h(1)
    state.cu1(0, 1, math.pi)
    state.h(0)
    state.h(1)
    emu_counts = state.run(8192)
    payload = run_backend(qasm, "braket", 8192)
    ref_counts = payload["counts"]
    emu_p = {format(k, "02b"): v / 8192 for k, v in emu_counts.items()}
    ref_p = {k: v / 8192 for k, v in ref_counts.items()}
    fid = hellinger(emu_p, ref_p)
    ok &= check("emulator vs braket on cu1(pi) (Hellinger=%.4f)" % fid, fid >= 0.97)

    print("summary: %s" % ("ALL PASS" if ok else "FAILURES PRESENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())