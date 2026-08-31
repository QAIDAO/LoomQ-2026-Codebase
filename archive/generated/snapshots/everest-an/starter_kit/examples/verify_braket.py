#!/usr/bin/env python3
"""Amazon Braket (official AWS SDK) cross-validation of our braket target IR.

Runs in python:3.10 + amazon-braket-sdk. For every public circuit:
adapter.transpile(qasm, "braket") -> Braket LocalSimulator parses the
OpenQASM 3 artifact -> distribution must match the ideal one
(Hellinger >= 0.97).

Completes the third-party cross-validation triangle (originq -> pyqpanda,
spinq -> spinqit, braket -> amazon-braket-sdk).
"""

import math
import os
import shutil
import sys
from typing import Dict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from adapter import transpile  # noqa: E402

try:
    from braket.devices import LocalSimulator
    from braket.ir.openqasm import Program
except ImportError:  # pragma: no cover - guarded at runtime
    LocalSimulator = Program = None

# Braket's OpenQASM 3 parser resolves include "stdgates.inc" as a real file
# relative to the current working directory; make sure it is present next to
# the script and copy it into the CWD before running.
_STDGATES_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stdgates.inc")
if os.path.isfile(_STDGATES_SRC):
    shutil.copy(_STDGATES_SRC, os.path.join(os.getcwd(), "stdgates.inc"))
else:
    print("warning: stdgates.inc not found next to script; braket include may fail", file=sys.stderr)

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


def main() -> int:
    if LocalSimulator is None:
        print("amazon-braket-sdk not installed; run inside python:3.10 with it.", file=sys.stderr)
        return 2
    device = LocalSimulator()
    circuits_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "circuits")
    failures = 0
    for name, expected in IDEAL.items():
        with open(os.path.join(circuits_dir, name), encoding="utf-8") as handle:
            qasm = handle.read()
        native = transpile(qasm, "braket")
        task = device.run(Program(source=native), shots=SHOTS)
        result = task.result()
        counts = dict(result.measurement_counts)
        observed = {key: value / SHOTS for key, value in counts.items()}
        fidelity = hellinger_fidelity(observed, expected)
        status = "PASS" if fidelity >= THRESHOLD else "FAIL"
        print("[%s] braket:%s fidelity=%.6f counts=%s" % (status, name, fidelity, counts))
        if status == "FAIL":
            failures += 1
    if failures:
        print("braket cross-validation: %d failure(s)" % failures, file=sys.stderr)
        return 1
    print("braket cross-validation: all cases passed (independent OpenQASM 3 parse)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
