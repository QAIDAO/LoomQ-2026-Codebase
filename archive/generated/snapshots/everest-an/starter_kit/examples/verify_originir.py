#!/usr/bin/env python3
"""OriginIR cross-validation against the official OriginQ SDK (pyqpanda).

Runs in the official evaluation container (python:3.10 + pyqpanda), which
is the closest available proxy for the organizer's OriginIR parser:

    docker run --rm -v "$PWD:/work" loomq-verify python /work/.../verify_originir.py

For every public circuit: adapter.transpile(..., "originq") -> pyqpanda
parses and simulates the emitted OriginIR -> the resulting distribution
must match the ideal one (Hellinger >= 0.97).

This is independent third-party confirmation that our OriginIR output is
valid, executable OriginIR - not just text that looks like it.
"""

import math
import os
import sys
from typing import Dict

# Reuse the L1 pipeline for the transpile step.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from adapter import transpile  # noqa: E402

try:
    import pyqpanda as pq
except ImportError:  # pragma: no cover - guarded at runtime
    pq = None

SHOTS = 4096
THRESHOLD = 0.97

IDEAL = {
    "bell.qasm": {"00": 0.5, "11": 0.5},
    "ghz3.qasm": {"000": 0.5, "111": 0.5},
}


def hellinger_fidelity(observed: Dict[str, float], expected: Dict[str, float]) -> float:
    states = set(observed) | set(expected)
    distance = math.sqrt(
        sum(
            (math.sqrt(observed.get(state, 0.0)) - math.sqrt(expected.get(state, 0.0)))
            ** 2
            for state in states
        )
    ) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - distance))


def run_originir(text: str, shots: int) -> Dict[str, int]:
    machine = pq.CPUQVM()
    machine.init_qvm()
    try:
        result = pq.convert_originir_str_to_qprog(text, machine)
        prog, _qubits, creg = result[:3]
        counts = machine.run_with_configuration(prog, creg, shots)
    finally:
        machine.finalize()
    return dict(counts)


def main() -> int:
    if pq is None:
        print("pyqpanda not installed; run inside python:3.10 with pyqpanda.", file=sys.stderr)
        return 2
    circuits_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "circuits")
    failures = 0
    for name, expected in IDEAL.items():
        with open(os.path.join(circuits_dir, name), encoding="utf-8") as handle:
            qasm = handle.read()
        originir = transpile(qasm, "originq")
        counts = run_originir(originir, SHOTS)
        observed = {key: value / SHOTS for key, value in counts.items()}
        fidelity = hellinger_fidelity(observed, expected)
        status = "PASS" if fidelity >= THRESHOLD else "FAIL"
        print("[%s] pyqpanda:%s fidelity=%.6f counts=%s" % (status, name, fidelity, counts))
        if status == "FAIL":
            failures += 1
    if failures:
        print("pyqpanda cross-validation: %d failure(s)" % failures, file=sys.stderr)
        return 1
    print("pyqpanda cross-validation: all cases passed (independent OriginIR parse)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
