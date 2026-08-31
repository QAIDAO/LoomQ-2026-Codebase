"""FHB closed-form references for the LoomQ self-test.

The Fuxi Hypercube Benchmark (github.com/AwareLiquid/The-Fuxi-Hypercube-Math)
rests on two exactly provable facts about n parallel R_X(2t) rotations
starting from |0...0>:

- at t = pi/4 the distribution is exactly uniform over all 2^n basis states;
- at t = pi the walk returns exactly to |0...0> (probability 1.0).

Because the reference is closed-form, validating the transpiler against it
needs no classical simulation - the same property that makes FHB a
zero-dependency self-test for L1.
"""

import math
from typing import Dict

try:
    from .qasm_parser import parse_qasm2
    from . import adapter
except ImportError:  # standalone-module fallback (evaluator imports by path)
    from qasm_parser import parse_qasm2
    import adapter


def uniform_distribution(n: int) -> Dict[str, float]:
    """Exact uniform distribution over n-bit strings (rightmost = c[0])."""
    prob = 1.0 / (1 << n)
    return {format(index, "0%db" % n): prob for index in range(1 << n)}


def return_distribution(n: int) -> Dict[str, float]:
    """Exact return distribution at t = pi (all mass on |0...0>)."""
    return {"%0*d" % (n, 0): 1.0}


def hellinger_fidelity(observed: Dict[str, float], expected: Dict[str, float]) -> float:
    """Hellinger fidelity, identical formula to the organizer's evaluator."""
    states = set(observed) | set(expected)
    distance = math.sqrt(
        sum(
            (math.sqrt(observed.get(state, 0.0)) - math.sqrt(expected.get(state, 0.0)))
            ** 2
            for state in states
        )
    ) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - distance))


def build_fhb_qasm(n: int, t: float) -> str:
    """FHB circuit: n parallel R_X(2t) rotations expressed in whitelist gates.

    R_X(theta) = ry(pi/2) . rz(theta) . ry(-pi/2)  (rotation conjugation:
    a pi/2 rotation about Y maps the Z axis onto the X axis).
    """
    theta = 2.0 * t
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % n,
        "creg c[%d];" % n,
    ]
    for i in range(n):
        lines.append("ry(pi/2) q[%d];" % i)
        lines.append("rz(%.12g) q[%d];" % (theta, i))
        lines.append("ry(-pi/2) q[%d];" % i)
    lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"


def check_fhb_circuit(n: int, t: float, shots: int = 8192) -> Dict[str, object]:
    """Transpile -> run the FHB circuit on all three targets.

    Returns per-target fidelity against the closed-form reference.
    """
    qasm = build_fhb_qasm(n, t)
    if t == math.pi / 4:
        expected = uniform_distribution(n)
    elif t == math.pi:
        expected = return_distribution(n)
    else:
        raise ValueError("FHB self-test supports t = pi/4 and t = pi only")
    results: Dict[str, object] = {}
    for target in ("spinq", "originq", "braket"):
        native = adapter.transpile(qasm, target)
        payload = adapter.run(qasm, target, shots)
        observed = {key: value / shots for key, value in payload["counts"].items()}
        results[target] = {
            "fidelity": hellinger_fidelity(observed, expected),
            "native": native,
            "payload": payload,
        }
    return results
