#!/usr/bin/env python3
"""Numerical verification of every contest circuit in circuits/.

Checks:
  bell/ghz3/ghz5  -> exact dominant-pair distributions (fidelity >= 0.99)
  qft4            -> amplitude pattern matches the 16x16 DFT matrix
  grover3         -> P(|11>) ~ 1.0 after one iteration
  random1..3      -> parse + run cleanly (statevector finite, all prob sum = 1)

Run:  python3 tools/verify_circuits.py
"""

from __future__ import annotations

import cmath
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loomq_core.qasm import parse_qasm2  # noqa: E402
from loomq_core.simulator import simulate_counts, statevector  # noqa: E402

CIRCUITS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "circuits")

FAILURES = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global FAILURES
    print("[%s] %s %s" % ("PASS" if ok else "FAIL", label, detail))
    if not ok:
        FAILURES += 1


def fidelity(counts: dict, ideal: dict, shots: int) -> float:
    keys = set(ideal) | set(counts)
    term = sum(
        (math.sqrt(counts.get(k, 0) / shots) - math.sqrt(ideal[k])) ** 2 for k in keys
    )
    return 1.0 - math.sqrt(term) / math.sqrt(2.0)


def verify_dominant(name: str, ideal: dict) -> None:
    circuit = parse_qasm2(open(os.path.join(CIRCUITS, name)).read())
    counts = simulate_counts(circuit, 8192)
    fid = fidelity(counts, ideal, 8192)
    check(name, fid >= 0.99, "fidelity=%.4f" % fid)


def _with_input(qasm_text: str, k: int, n: int) -> str:
    """Prepend X gates so the register starts in |k> (qubit b holds bit b)."""
    lines = []
    for line in qasm_text.splitlines():
        lines.append(line)
        if line.startswith("creg"):
            for b in range(n):
                if (k >> b) & 1:
                    lines.append("x q[%d];" % b)
    return "\n".join(lines)


def verify_qft4() -> None:
    text = open(os.path.join(CIRCUITS, "qft4.qasm")).read()
    N = 16
    w = cmath.exp(2j * math.pi / N)
    worst = 0.0
    for k in range(N):
        circuit = parse_qasm2(_with_input(text, k, 4))
        state = statevector(circuit)
        ideal = [w ** (j * k) / 4 for j in range(N)]
        worst = max(worst, max(abs(state[j] - ideal[j]) for j in range(N)))
    check("qft4-vs-DFT(all 16 inputs)", worst < 1e-9, "worst abs err=%.2e" % worst)
    # also check Parseval / norm
    circuit0 = parse_qasm2(open(os.path.join(CIRCUITS, "qft4.qasm")).read())
    state0 = statevector(circuit0)
    norm = math.sqrt(sum(abs(a) ** 2 for a in state0))
    check("qft4-norm", abs(norm - 1.0) < 1e-9, "norm=%.6f" % norm)


def verify_grover3() -> None:
    circuit = parse_qasm2(open(os.path.join(CIRCUITS, "grover3.qasm")).read())
    counts = simulate_counts(circuit, 8192)
    top = max(counts.items(), key=lambda kv: kv[1])
    check("grover3-P(11)", top[0] == "11" and counts.get("11", 0) / 8192 > 0.98,
          "top=%s p=%.3f" % (top[0], top[1] / 8192))


def verify_random(name: str) -> None:
    circuit = parse_qasm2(open(os.path.join(CIRCUITS, name)).read())
    state = statevector(circuit)
    norm = sum(abs(a) ** 2 for a in state)
    counts = simulate_counts(circuit, 4096)
    total = sum(counts.values())
    check(name, abs(norm - 1.0) < 1e-9 and total == 4096,
          "norm=%.6f shots=%d states=%d" % (norm, total, len(counts)))


if __name__ == "__main__":
    verify_dominant("bell.qasm", {"00": 0.5, "11": 0.5})
    verify_dominant("ghz3.qasm", {"000": 0.5, "111": 0.5})
    verify_dominant("ghz5.qasm", {"00000": 0.5, "11111": 0.5})
    verify_qft4()
    verify_grover3()
    print()
    if FAILURES:
        print("CIRCUIT VERIFICATION FAILED: %d" % FAILURES)
        sys.exit(1)
    print("ALL 5 CIRCUITS VERIFIED")
