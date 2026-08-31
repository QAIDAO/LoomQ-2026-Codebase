#!/usr/bin/env python3
"""L1 round-trip self-test: transpile output must be semantically identical.

Builds hidden-circuit-style programs inside the 12-gate whitelist
(QFT-4, a 3-qubit Grover with a white-listed oracle, and seeded random
circuits), transpiles to the spinq target (full OpenQASM 2.0), re-parses
the emitted artifact and simulates it with the same RNG seed as the
original. Semantic equivalence is checked as bit-exact identical counts -
the strongest possible assertion for a deterministic noiseless simulator.

Exit code 0 = all cases pass.
"""

import math
import random
import sys

try:
    from .qasm_parser import parse_qasm2
    from .simulator import simulate
    from . import adapter
except ImportError:  # standalone-module fallback
    from qasm_parser import parse_qasm2
    from simulator import simulate
    import adapter

SHOTS = 8192
SEED = 20260806


def build_qft4() -> str:
    """4-qubit QFT with h/cu1 only (bit order intentionally unsorted)."""
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[4];",
        "creg c[4];",
    ]
    for j in range(4):
        lines.append("h q[%d];" % j)
        for k in range(j + 1, 4):
            angle = math.pi / (2 ** (k - j))
            lines.append("cu1(pi/%d) q[%d], q[%d];" % (2 ** (k - j), k, j))
    lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"


def build_grover3() -> str:
    """3-qubit Grover, oracle marks |111>, diffusion via s/sdg/ccx/x/h.

    z = s s (phase flip), so the diffusion operator
    H X [C Z on target] X H is expressed entirely with whitelist gates.
    """
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[3];",
        "creg c[3];",
        # superposition
        "h q[0];", "h q[1];", "h q[2];",
        # oracle: mark |111> -> ccx then z (= s s) on q[2], then ccx back
        "ccx q[0], q[1], q[2];",
        "s q[2];", "s q[2];",
        "ccx q[0], q[1], q[2];",
        # diffusion: H X ... X H with controlled-z on target encoded as
        # x-conjugated ccx: X H? standard form uses
        # H H? -> keep it explicit and gate-count honest:
        "h q[0];", "h q[1];", "h q[2];",
        "x q[0];", "x q[1];", "x q[2];",
        "h q[2];",
        "ccx q[0], q[1], q[2];",
        "h q[2];",
        "x q[0];", "x q[1];", "x q[2];",
        "h q[0];", "h q[1];", "h q[2];",
        "measure q -> c;",
    ]
    return "\n".join(lines) + "\n"


def build_random(num_qubits: int, num_gates: int, seed: int) -> str:
    """Seeded random circuit over the 12-gate whitelist."""
    rng = random.Random(seed)
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % num_qubits,
        "creg c[%d];" % num_qubits,
    ]
    gates = ["h", "x", "s", "sdg", "t", "tdg"]
    param_gates = ["rz", "ry"]
    for _ in range(num_gates):
        kind = rng.random()
        if kind < 0.45:
            lines.append("%s q[%d];" % (rng.choice(gates), rng.randrange(num_qubits)))
        elif kind < 0.7:
            lines.append(
                "%s(pi/%d) q[%d];"
                % (rng.choice(param_gates), rng.randrange(1, 9), rng.randrange(num_qubits))
            )
        elif kind < 0.85:
            a, b = rng.sample(range(num_qubits), 2)
            if rng.random() < 0.4:
                lines.append("cu1(pi/%d) q[%d], q[%d];" % (rng.randrange(1, 9), a, b))
            else:
                lines.append("%s q[%d], q[%d];" % (rng.choice(["cx", "swap"]), a, b))
        else:
            a, b, c = rng.sample(range(num_qubits), 3)
            lines.append("ccx q[%d], q[%d], q[%d];" % (a, b, c))
    lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"


def check_roundtrip(label: str, qasm: str) -> None:
    original = simulate(parse_qasm2(qasm), SHOTS, seed=SEED)
    native = adapter.transpile(qasm, "spinq")
    if "OPENQASM 2.0" not in native:
        raise AssertionError("%s: transpile output lost the QASM 2.0 header" % label)
    reparsed = parse_qasm2(native)  # organizer parses our artifact too
    roundtrip = simulate(reparsed, SHOTS, seed=SEED)
    assert roundtrip == original, (
        "%s: transpile output changed the outcome distribution" % label
    )
    print(
        "[PASS] roundtrip:%s gates=%d states=%d"
        % (label, len(reparsed.ops), len(roundtrip))
    )


def build_ghz5() -> str:
    """5-qubit GHZ state (hidden-circuit style): h q[0] + cx chain."""
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[5];",
        "creg c[5];",
        "h q[0];",
    ]
    for i in range(4):
        lines.append("cx q[%d], q[%d];" % (i, i + 1))
    lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"


def main() -> int:
    failures = 0
    cases = [
        ("qft4", build_qft4()),
        ("grover3", build_grover3()),
        ("ghz5", build_ghz5()),
        ("random1", build_random(5, 24, seed=1)),
        ("random2", build_random(6, 30, seed=2)),
        ("random3", build_random(7, 36, seed=3)),
        ("random4", build_random(10, 50, seed=4)),
        ("random5", build_random(12, 60, seed=5)),
    ]
    for label, qasm in cases:
        try:
            check_roundtrip(label, qasm)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print("[FAIL] roundtrip:%s - %s: %s" % (label, type(exc).__name__, exc))
    if failures:
        print("Round-trip self-test: %d failure(s)" % failures, file=sys.stderr)
        return 1
    print("Round-trip self-test: all %d cases passed" % len(cases))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover - top-level guard
        print("Round-trip self-test failed: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(1)
