#!/usr/bin/env python3
"""Generate 100 varied circuits and prove all emitted IR round-trips exactly."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import List, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loomq.facade import transpile
from loomq.qasm import parse_and_normalize
from loomq.runtime.reference_simulator import simulate_counts
from loomq.targets.roundtrip import parse_target_artifact


GATES = ("h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx")
ANGLES = ("pi/2", "-pi/4", "(pi+pi)/8", "1.25e-1", "-2.5E-2")


def _gate_statement(rng: random.Random, name: str, qubits: int) -> str:
    arity = 3 if name == "ccx" else 2 if name in {"cx", "cu1", "swap"} else 1
    selected = rng.sample(range(qubits), arity)
    parameter = "(%s)" % rng.choice(ANGLES) if name in {"rz", "ry", "cu1"} else ""
    operands = ", ".join("q[%d]" % index for index in selected)
    return "%s%s %s;" % (name, parameter, operands)


def make_circuit(seed: int, forced_gate: str | None = None) -> Tuple[str, Set[str]]:
    rng = random.Random(seed)
    minimum = 3 if forced_gate == "ccx" else 2 if forced_gate in {"cx", "cu1", "swap"} else 1
    qubits = rng.randint(max(2, minimum), 5)
    statements: List[str] = []
    covered: Set[str] = set()
    if forced_gate:
        statements.append(_gate_statement(rng, forced_gate, qubits))
        covered.add(forced_gate)
    available = [gate for gate in GATES if qubits >= (3 if gate == "ccx" else 2 if gate in {"cx", "cu1", "swap"} else 1)]
    for _ in range(rng.randint(8, 16)):
        gate = rng.choice(available)
        statements.append(_gate_statement(rng, gate, qubits))
        covered.add(gate)
    source = "\n".join(
        [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            "qreg q[%d];" % qubits,
            "creg c[%d];" % qubits,
            *statements,
            "measure q -> c;",
        ]
    )
    return source + "\n", covered


def main() -> int:
    coverage: Set[str] = set()
    checked = 0
    for seed in range(100):
        forced = GATES[seed] if seed < len(GATES) else None
        source, used = make_circuit(seed, forced)
        coverage.update(used)
        canonical = parse_and_normalize(source)
        baseline_counts = simulate_counts(canonical, 128, seed)
        for target in ("spinq", "originq", "braket"):
            artifact = transpile(source, target)
            round_tripped = parse_target_artifact(artifact, target)
            if round_tripped != canonical:
                raise AssertionError("semantic IR mismatch for seed %d target %s" % (seed, target))
            if simulate_counts(round_tripped, 128, seed) != baseline_counts:
                raise AssertionError("simulation mismatch for seed %d target %s" % (seed, target))
            checked += 1
    missing = set(GATES) - coverage
    if missing:
        raise AssertionError("random corpus did not cover gates: %s" % sorted(missing))
    print(
        json.dumps(
            {
                "seeds": 100,
                "target_round_trips": checked,
                "gates": sorted(coverage),
                "status": "PASS",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
