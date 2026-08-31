"""测试 GHZ-3, QFT-4, Grover-3 电路"""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from starter_kit.adapter import run
from starter_kit.tests.circuits import GHZ_3, QFT_4, GROVER_3, BELL_STATE


def hellinger_fidelity(P, Q):
    keys = set(P.keys()) | set(Q.keys())
    s = sum((math.sqrt(P.get(k, 0)) - math.sqrt(Q.get(k, 0))) ** 2 for k in keys)
    return 1 - math.sqrt(s) / math.sqrt(2)


def test_circuit(name, qasm, ideal_dist):
    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")

    result = run(qasm, "braket", shots=8192)
    counts = result["counts"]
    total = sum(counts.values())

    print(f"Backend: {result['backend']}")
    print(f"Shots:   {result['shots']}")
    print(f"Counts:")
    for k, v in sorted(counts.items(), key=lambda x: -x[1])[:6]:
        print(f"  {k}: {v} ({v/total*100:.1f}%)")

    P = {k: v / total for k, v in counts.items()}
    fidelity = hellinger_fidelity(P, ideal_dist)

    status = "PASS" if fidelity >= 0.97 else "FAIL"
    print(f"Fidelity: {fidelity:.4f} [{status}] (threshold: 0.97)")
    return fidelity


if __name__ == "__main__":
    print("\nLoomQ 电路验证")
    print("=" * 50)

    # Bell 态
    test_circuit("Bell State", BELL_STATE, {"00": 0.5, "11": 0.5})

    # GHZ-3 态
    test_circuit("GHZ-3 State", GHZ_3, {"000": 0.5, "111": 0.5})

    # QFT-4 (含 cu1 门分解)
    print("\n(GHZ-3 ideal: 000=50%, 111=50%)")
    print("(QFT-4: uniform distribution expected)")
    result = run(QFT_4, "braket", shots=8192)
    counts = result["counts"]
    total = sum(counts.values())
    print(f"\nQFT-4 counts:")
    for k, v in sorted(counts.items(), key=lambda x: -x[1])[:8]:
        print(f"  {k}: {v} ({v/total*100:.1f}%)")

    # Grover-3 (含 ccx 门)
    result = run(GROVER_3, "braket", shots=8192)
    counts = result["counts"]
    total = sum(counts.values())
    print(f"\nGrover-3 counts:")
    for k, v in sorted(counts.items(), key=lambda x: -x[1])[:5]:
        print(f"  {k}: {v} ({v/total*100:.1f}%)")

    print(f"\n{'='*50}")
    print("所有电路测试完成!")
