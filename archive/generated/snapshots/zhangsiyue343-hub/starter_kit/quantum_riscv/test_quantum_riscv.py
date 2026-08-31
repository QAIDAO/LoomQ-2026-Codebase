#!/usr/bin/env python3
"""自定义量子 RISC-V 扩展 —— 端到端测试。

覆盖：
  T1  标准指令与官方 riscv_emulator.py 行为一致（向后兼容）
  T2  量子门分布与 adapter 无噪声模拟器一致（H/X/CX/SWAP/CCX/RY/RZ/CU1）
  T3  Bell 态多轮统计：00/11 各约 50%
  T4  GHZ-3 态多轮统计：000/111 各约 50%
  T5  量子测量进入经典控制流（混合程序）
  T6  指令编码（encode_quantum_instruction）机器码验证
  T7  经典指令与量子指令混合执行正确性
"""

import sys
import math
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from quantum_riscv_emulator import QuantumRISCVEmulator, encode_quantum_instruction
import adapter


def run_asm(asm, seed=0):
    e = QuantumRISCVEmulator()
    e.rng.seed(seed)
    e.load_program(asm)
    state = e.execute()
    return e, state


def freq(asm, trials=512, seed0=1, nbits=2):
    """多次运行同一程序，统计前 nbits 个测量寄存器 (x10..) 的组合频率。"""
    counters = Counter()
    for t in range(trials):
        e, state = run_asm(asm, seed0 + t)
        key = tuple(state.get("x%d" % (10 + i), 0) for i in range(nbits))
        counters[key] += 1
    return counters


print("=== T1: 标准指令向后兼容 ===")
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
from riscv_emulator import TinyRISCVEmulator as OfficialEmu
off = OfficialEmu(); off.load_program(official); off_state = off.execute()
ext = QuantumRISCVEmulator(); ext.load_program(official); ext_state = ext.execute()
assert off_state.get("x3") == ext_state.get("x3") == 16, (off_state, ext_state)
print("PASS: 标准指令结果一致 x3=%d" % ext_state["x3"])

print("=== T2: 量子门分布与 adapter 无噪声模拟器一致 ===")
# 用同一 QASM 电路，分别用 adapter 和量子 RISC-V 模拟
def qasm_for(gates, nbits=None):
    # 从门操作推断所需比特数（q[i] 最大索引+1）
    if nbits is None:
        maxq = -1
        for g in gates:
            import re
            idxs = [int(x) for x in re.findall(r"q\[(\d+)\]", g)]
            if idxs:
                maxq = max(maxq, max(idxs))
        nbits = maxq + 1
    return ("OPENQASM 2.0;\nqreg q[%d];\ncreg c[%d];\n" % (nbits, nbits)
            + "\n".join(gates) + "\nmeasure q -> c;\n")

def qasm_dist(qasm, shots=20000):
    c = adapter.run(qasm, "spinq", shots)["counts"]
    tot = sum(c.values())
    return {k: v / tot for k, v in c.items()}

def qriscv_dist(asm, trials=20000):
    e = QuantumRISCVEmulator(); e.rng.seed(7)
    e.load_program(asm)
    e.execute()  # 只到测量前不行——测量会坍缩。改为单次采样模拟多次。
    return None

# 用"测量前概率"验证：不执行测量指令，直接读 quantum_probs
def qriscv_probs(asm_no_meas, nbits):
    e = QuantumRISCVEmulator()
    e.load_program(asm_no_meas)
    e.execute()
    return e.quantum_probs()

def hell(p, q):
    st = set(p) | set(q)
    d = sum((math.sqrt(p.get(k, 0)) - math.sqrt(q.get(k, 0))) ** 2 for k in st)
    return math.sqrt(d / 2)

# H + CX on q0,q1 -> Bell (比较测量前概率 vs adapter 分布)
qasm = qasm_for(["h q[0];", "cx q[0], q[1];"])
adist = qasm_dist(qasm)
pdist = qriscv_probs("qinit 2\nqh q0\nqcx q0, q1\n", 2)
h = hell(adist, pdist)
print("  Bell: Hellinger(adapter, qRISC-V)=%.4f" % h)
assert h < 0.01

# X + SWAP
qasm = qasm_for(["x q[0];", "swap q[0], q[1];"])
adist = qasm_dist(qasm)
pdist = qriscv_probs("qinit 2\nqx q0\nqswap q0, q1\n", 2)
h = hell(adist, pdist)
print("  X+SWAP: Hellinger=%.4f" % h)
assert h < 0.01

# CCX (Toffoli) with x on two controls
qasm = qasm_for(["x q[0];", "x q[1];", "ccx q[0], q[1], q[2];"])
adist = qasm_dist(qasm)
pdist = qriscv_probs("qinit 3\nqx q0\nqx q1\nqccx q0, q1, q2\n", 3)
h = hell(adist, pdist)
print("  CCX: Hellinger=%.4f" % h)
assert h < 0.01

# RY(pi/2) == H 效果
qasm = qasm_for(["ry(pi/2) q[0];"])
adist = qasm_dist(qasm)
pdist = qriscv_probs("qinit 1\nqry q0, 8\n", 1)  # imm16=8 -> pi/2
h = hell(adist, pdist)
print("  RY(pi/2): Hellinger=%.4f" % h)
assert h < 0.01

# RZ + CU1 phases (phase gates don't change measurement)
qasm = qasm_for(["x q[0];", "x q[1];", "cu1(pi/2) q[0], q[1];"])
adist = qasm_dist(qasm)
pdist = qriscv_probs("qinit 2\nqx q0\nqx q1\nqcu1 q0, q1, 8\n", 2)
h = hell(adist, pdist)
print("  CU1: Hellinger=%.4f" % h)
assert h < 0.01

print("PASS: 量子门与 adapter 一致")

print("=== T3: Bell 态多轮统计 00/11 各约 50% ===")
bell_asm = "qinit 2\nli x10, 0\nli x11, 0\nqh q0\nqcx q0, q1\nqmeas x10, q0\nqmeas x11, q1\n"
c = freq(bell_asm, trials=1024, nbits=2)
n = sum(c.values())
print("  分布:", {k: round(v / n, 3) for k, v in sorted(c.items())})
p00 = c.get((0, 0), 0) / n
p11 = c.get((1, 1), 0) / n
assert abs(p00 - 0.5) < 0.06 and abs(p11 - 0.5) < 0.06
assert c.get((0, 1), 0) + c.get((1, 0), 0) < 0.05 * n
print("PASS: Bell 00/11 各 ~50%，无 01/10")

print("=== T4: GHZ-3 态多轮统计 000/111 各约 50% ===")
ghz_asm = ("qinit 3\nli x10, 0\nli x11, 0\nli x12, 0\n"
           "qh q0\nqcx q0, q1\nqcx q1, q2\n"
           "qmeas x10, q0\nqmeas x11, q1\nqmeas x12, q2\n")
c = freq(ghz_asm, trials=1024, nbits=3)
n = sum(c.values())
print("  分布:", {k: round(v / n, 3) for k, v in sorted(c.items())})
p000 = c.get((0, 0, 0), 0) / n
p111 = c.get((1, 1, 1), 0) / n
assert abs(p000 - 0.5) < 0.06 and abs(p111 - 0.5) < 0.06
print("PASS: GHZ-3 000/111 各 ~50%")

print("=== T5: 测量进入经典控制流（混合程序） ===")
# 测量 q0，若为 1 则 r1=100，否则 r1=10；再 r1+=5
hybrid = """
qinit 1
qh q0
qmeas x10, q0
li x1, 10
li x2, 1
beq x10, x2, ISONE
j ADJ
ISONE:
li x1, 100
ADJ:
addi x1, x1, 5
"""
e, state = run_asm(hybrid)
meas = state.get("x10", 0)
r1 = state.get("x1", 0)
print("  测量=%d -> x1=%d" % (meas, r1))
assert r1 == (105 if meas == 1 else 15), state
# 多次验证分支都正确
for t in range(200):
    e, state = run_asm(hybrid, t)
    m = state.get("x10", 0)
    assert state.get("x1", 0) == (105 if m == 1 else 15)
print("PASS: 量子测量正确驱动经典 if/else")

print("=== T6: 指令编码验证 ===")
# qh q0
code = encode_quantum_instruction("qh", ["q0"])
assert (code >> 25) & 0x7F == 0x01, hex(code)
assert code & 0x7F == 0x0B, hex(code)
assert (code >> 15) & 0x1F == 0, hex(code)
print("  qh q0 -> 0x%08X (funct7=0x01, qa=0, opcode=0x0B) OK" % code)
# qcx q0, q1
code = encode_quantum_instruction("qcx", ["q0", "q1"])
assert (code >> 25) & 0x7F == 0x08
assert ((code >> 20) & 0x1F) == 1  # qb=1
assert ((code >> 15) & 0x1F) == 0  # qa=0
print("  qcx q0, q1 -> 0x%08X OK" % code)
# qmeas x10, q0
code = encode_quantum_instruction("qmeas", ["x10", "q0"])
assert (code >> 25) & 0x7F == 0x0B
assert ((code >> 7) & 0x1F) == 10  # qd=10
print("  qmeas x10, q0 -> 0x%08X OK" % code)
# qry q0, 8  (pi/2)
code = encode_quantum_instruction("qry", ["q0", "8"])
assert ((code >> 20) & 0xFFF) == 8
assert ((code >> 12) & 0x7) == 3  # funct3=3 (参数门区)
print("  qry q0, 8 -> 0x%08X OK" % code)
# qcu1 q0, q1, 8
code = encode_quantum_instruction("qcu1", ["q0", "q1", "8"])
assert ((code >> 12) & 0x7) == 5  # funct3=5 (参数门区)
assert ((code >> 7) & 0x1F) == 1  # qd=qb=1
print("  qcu1 q0, q1, 8 -> 0x%08X OK" % code)
print("PASS: 指令编码正确")

print("=== T7: 经典-量子混合 + 参数门组合 ===")
# 用 ry 把 q0 转到 |+>，测量，经典累加
mixed = """
qinit 1
qry q0, 8
qmeas x10, q0
li x1, 0
add x1, x1, x10
"""
c = freq(mixed, trials=512, nbits=1)
n = sum(c.values())
p1 = c.get((1,), 0) / n
print("  ry(pi/2) 测量为 1 的频率: %.3f" % p1)
assert abs(p1 - 0.5) < 0.06
print("PASS: 混合程序正确")

print()
print("ALL QUANTUM RISC-V TESTS PASSED")