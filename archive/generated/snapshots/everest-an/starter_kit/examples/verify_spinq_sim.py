#!/usr/bin/env python3
"""SpinQit (official SpinQ SDK) cross-validation of our spinq target IR.

Runs in python:3.10 + spinqit (spinqit ships cp310-only wheels). For every
public circuit: adapter.transpile(qasm, "spinq") -> SpinQit's QASM compiler
parses it -> BasicSimulator runs it -> distribution must match the ideal
one (Hellinger >= 0.97).

This mirrors the pyqpanda cross-check for originq: independent third-party
confirmation that our spinq output is valid, executable OpenQASM 2.0.
"""

import math
import os
import sys
import tempfile
from typing import Dict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from adapter import transpile  # noqa: E402

try:
    from spinqit import get_compiler, get_basic_simulator, BasicSimulatorConfig
except ImportError:  # pragma: no cover - guarded at runtime
    get_compiler = get_basic_simulator = BasicSimulatorConfig = None

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


def run_spinq_sim(qasm: str, shots: int) -> Dict[str, int]:
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")
    try:
        handle.write(qasm)
        handle.close()
        compiler = get_compiler("qasm")
        ir = compiler.compile(handle.name, 0)
    finally:
        os.unlink(handle.name)
    engine = get_basic_simulator()
    config = BasicSimulatorConfig()
    config.configure_shots(shots)
    result = engine.execute(ir, config)
    counts = getattr(result, "counts", None) or {}
    return {str(key): int(value) for key, value in counts.items()}


def main() -> int:
    if get_compiler is None:
        print("spinqit not installed; run inside python:3.10 with spinqit.", file=sys.stderr)
        return 2
    circuits_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "circuits")
    failures = 0
    for name, expected in IDEAL.items():
        with open(os.path.join(circuits_dir, name), encoding="utf-8") as handle:
            qasm = handle.read()
        native = transpile(qasm, "spinq")
        counts = run_spinq_sim(native, SHOTS)
        observed = {key: value / SHOTS for key, value in counts.items()}
        fidelity = hellinger_fidelity(observed, expected)
        status = "PASS" if fidelity >= THRESHOLD else "FAIL"
        print("[%s] spinqit:%s fidelity=%.6f counts=%s" % (status, name, fidelity, counts))
        if status == "FAIL":
            failures += 1
    if failures:
        print("spinqit cross-validation: %d failure(s)" % failures, file=sys.stderr)
        return 1
    print("spinqit cross-validation: all cases passed (independent QASM 2.0 parse)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
