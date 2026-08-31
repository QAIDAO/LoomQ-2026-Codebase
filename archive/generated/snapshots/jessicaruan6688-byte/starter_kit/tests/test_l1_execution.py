#!/usr/bin/env python3
"""End-to-end L1 execution tests against the real backend SDKs.

This suite exists because ``loomq.verify`` compares the reference simulator to
itself: it proves emit/parse round-trips are consistent but cannot catch a wrong
gate matrix or a wrong bit order. Here ``adapter.run()`` is driven through the
actual SDKs and scored against the reference distribution the way the official
grader does, including measure maps that permute qubits onto classical bits --
Bell and GHZ are symmetric under bit reversal and hide exactly that bug.
"""

from __future__ import annotations

import glob
import math
import os
import random
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import adapter  # noqa: E402
from loomq.reference_sim import ideal_distribution  # noqa: E402

SHOTS = 8192
THRESHOLD = 0.97
WHITELIST_1Q = ("h", "x", "s", "sdg", "t", "tdg")
ANGLES = ("pi/2", "pi/4", "pi/8", "-pi/4", "3*pi/4")


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


def random_circuit(seed: int, permute_measures: bool = False) -> str:
    rng = random.Random(seed)
    n = rng.randint(2, 5)
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{n}];",
        f"creg c[{n}];",
    ]
    for _ in range(rng.randint(5, 14)):
        gate = rng.choice(
            list(WHITELIST_1Q) + ["rz", "ry", "cx", "cu1", "swap", "ccx"]
        )
        if gate in {"rz", "ry"}:
            lines.append(f"{gate}({rng.choice(ANGLES)}) q[{rng.randrange(n)}];")
        elif gate == "cu1":
            a, b = rng.sample(range(n), 2)
            lines.append(f"cu1(pi/{rng.choice([2, 4, 8])}) q[{a}], q[{b}];")
        elif gate in {"cx", "swap"}:
            a, b = rng.sample(range(n), 2)
            lines.append(f"{gate} q[{a}], q[{b}];")
        elif gate == "ccx":
            if n < 3:
                continue
            a, b, c = rng.sample(range(n), 3)
            lines.append(f"ccx q[{a}], q[{b}], q[{c}];")
        else:
            lines.append(f"{gate} q[{rng.randrange(n)}];")

    targets = list(range(n))
    if permute_measures:
        rng.shuffle(targets)
    for qubit, cbit in enumerate(targets):
        lines.append(f"measure q[{qubit}] -> c[{cbit}];")
    return "\n".join(lines) + "\n"


def collect_circuits() -> Dict[str, str]:
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "circuits")
    circuits = {
        os.path.basename(path): open(path, encoding="utf-8").read()
        for path in sorted(glob.glob(os.path.join(base, "*.qasm")))
    }
    for seed in range(20):
        circuits[f"random{seed}"] = random_circuit(seed)
    for seed in range(20):
        circuits[f"permuted{seed}"] = random_circuit(1000 + seed, permute_measures=True)
    return circuits


def available_targets() -> List[str]:
    targets = []
    for target, module in (("spinq", "spinqit"), ("braket", "braket"), ("originq", "pyqpanda")):
        try:
            __import__(module)
        except Exception:  # noqa: BLE001
            print(f"  (skipping {target}: {module} not importable)")
            continue
        targets.append(target)
    return targets


def validate_schema(payload: object, shots: int) -> None:
    assert isinstance(payload, dict), "result must be a dict"
    for field in ("backend", "job_id", "shots", "counts", "bit_order", "timestamp"):
        assert field in payload, f"missing field {field}"
    assert payload["bit_order"] == "little", payload["bit_order"]
    assert payload["shots"] == shots, payload["shots"]
    assert sum(payload["counts"].values()) == shots, "counts must total shots"
    for key in payload["counts"]:
        assert key and set(key) <= {"0", "1"}, f"bad counts key {key!r}"
    assert not payload.get("meta", {}).get("is_mock"), "mock results never score"


def test_execution_fidelity() -> None:
    circuits = collect_circuits()
    targets = available_targets()
    assert targets, "no backend SDK importable"

    failures: List[Tuple[str, str, object]] = []
    for target in targets:
        worst = (1.0, None)
        for name, qasm in circuits.items():
            try:
                payload = adapter.run(qasm, target, SHOTS)
                validate_schema(payload, SHOTS)
                observed = {
                    key: value / SHOTS for key, value in payload["counts"].items()
                }
                fidelity = hellinger_fidelity(observed, ideal_distribution(qasm))
            except Exception as exc:  # noqa: BLE001
                failures.append((target, name, f"{type(exc).__name__}: {exc}"))
                continue
            if fidelity < worst[0]:
                worst = (fidelity, name)
            if fidelity < THRESHOLD:
                failures.append((target, name, round(fidelity, 4)))
        print(
            f"  {target:8s} {len(circuits):3d} circuits, "
            f"worst fidelity {worst[0]:.4f} ({worst[1]})"
        )

    assert not failures, "execution mismatches:\n" + "\n".join(
        f"    {target}:{name} -> {detail}" for target, name, detail in failures[:15]
    )


def test_bit_order_is_classical_little_endian() -> None:
    """``measure q[1] -> c[0]`` must report the bit in c[0], i.e. rightmost."""
    qasm = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
x q[1];
measure q[0] -> c[2];
measure q[1] -> c[0];
measure q[2] -> c[1];
"""
    assert ideal_distribution(qasm) == {"001": 1.0}, ideal_distribution(qasm)
    for target in available_targets():
        payload = adapter.run(qasm, target, 512)
        assert payload["counts"] == {"001": 512}, (target, payload["counts"])


def main() -> int:
    tests = [test_bit_order_is_classical_little_endian, test_execution_fidelity]
    failures = 0
    for test in tests:
        print(f"--- {test.__name__} ---")
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"[FAIL] {test.__name__}: {exc}")
        else:
            print(f"[PASS] {test.__name__}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
