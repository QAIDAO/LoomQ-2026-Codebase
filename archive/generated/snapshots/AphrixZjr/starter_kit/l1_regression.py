#!/usr/bin/env python3
"""Run the local L1 hidden-set regression against every installed runner.

The default command is intentionally qualification-sized: all three targets,
8192 shots per case, and the same 0.97 fidelity threshold as the evaluator.
Expected distributions come only from :mod:`l1_reference`; they are never
passed to ``adapter`` or any production runner.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from l1_reference import (
    distribution,
    equivalent_up_to_global_phase,
    hellinger_fidelity,
    statevector,
)
from loomq_l1 import GATE_SIGNATURES, parse_qasm


SHOTS = 8192
FIDELITY_THRESHOLD = 0.97
DEFAULT_TARGETS = ("spinq", "originq", "braket")
_HERE = os.path.dirname(os.path.abspath(__file__))
_ANGLE_CASES = (
    ("zero", "0"),
    ("positive", "pi/2"),
    ("negative", "-pi/3"),
    ("nontrivial", "pi/7"),
)
_RANDOM_SEEDS = (0x5EED071, 0x5EED19B, 0x5EED2C3)


@dataclass(frozen=True)
class RegressionCase:
    case_id: str
    source: str
    group: str


def _qasm(qubits: int, body: Sequence[str], classical: Optional[int] = None) -> str:
    width = qubits if classical is None else classical
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % qubits,
        "creg c[%d];" % width,
    ]
    lines.extend(statement.rstrip(";") + ";" for statement in body)
    return "\n".join(lines) + "\n"


def _gate_cases() -> List[RegressionCase]:
    fixed = {
        "h": (1, ("h q[0]",)),
        "x": (1, ("x q[0]",)),
        "s": (1, ("h q[0]", "s q[0]", "h q[0]")),
        "sdg": (1, ("h q[0]", "t q[0]", "sdg q[0]", "h q[0]")),
        "t": (1, ("h q[0]", "t q[0]", "h q[0]")),
        "tdg": (1, ("h q[0]", "s q[0]", "tdg q[0]", "h q[0]")),
        "cx": (2, ("x q[0]", "cx q[0],q[1]")),
        "swap": (2, ("x q[0]", "swap q[0],q[1]")),
        "ccx": (3, ("x q[0]", "x q[1]", "ccx q[0],q[1],q[2]")),
    }
    cases = [
        RegressionCase(
            "gate/%s" % name,
            _qasm(width, body + ("measure q -> c",)),
            "gate",
        )
        for name, (width, body) in fixed.items()
    ]
    for label, angle in _ANGLE_CASES:
        cases.append(
            RegressionCase(
                "gate/rz/%s" % label,
                _qasm(
                    1,
                    (
                        "h q[0]",
                        "rz(%s) q[0]" % angle,
                        "t q[0]",
                        "h q[0]",
                        "measure q -> c",
                    ),
                ),
                "gate",
            )
        )
        cases.append(
            RegressionCase(
                "gate/ry/%s" % label,
                _qasm(
                    1,
                    ("ry(%s) q[0]" % angle, "h q[0]", "measure q -> c"),
                ),
                "gate",
            )
        )
        cases.append(
            RegressionCase(
                "gate/cu1/%s" % label,
                _qasm(
                    2,
                    (
                        "h q[0]",
                        "h q[1]",
                        "cu1(%s) q[0],q[1]" % angle,
                        "t q[0]",
                        "h q[0]",
                        "h q[1]",
                        "measure q -> c",
                    ),
                ),
                "gate",
            )
        )
    return cases


def _random_case(seed: int) -> RegressionCase:
    generator = random.Random(seed)
    gates = tuple(GATE_SIGNATURES)
    angles = ("0", "pi/7", "-pi/5", "0.371", "-0.619")
    body: List[str] = ["h q[0]", "ry(pi/7) q[1]", "x q[3]"]
    for _ in range(28):
        name = generator.choice(gates)
        parameters, arity = GATE_SIGNATURES[name]
        operands = generator.sample(range(4), arity)
        angle = "(%s)" % generator.choice(angles) if parameters else ""
        body.append(
            "%s%s %s"
            % (name, angle, ",".join("q[%d]" % index for index in operands))
        )
    body.append("measure q -> c")
    return RegressionCase(
        "extended/random-%07x" % seed,
        _qasm(4, body),
        "extended",
    )


def _file_case(relative: str, group: str) -> RegressionCase:
    path = os.path.join(_HERE, "circuits", *relative.split("/"))
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    return RegressionCase("%s/%s" % (group, relative), source, group)


def regression_cases() -> Tuple[RegressionCase, ...]:
    """Build the deterministic public, gate, and supplemental circuit suite."""

    cases: List[RegressionCase] = [
        _file_case("bell.qasm", "public"),
        _file_case("ghz3.qasm", "public"),
    ]
    cases.extend(_gate_cases())
    for filename in (
        "hidden/ghz5.qasm",
        "hidden/qft4.qasm",
        "hidden/grover3.qasm",
        "hidden/bit_order_asymmetric.qasm",
        "hidden/noncontiguous_measurement.qasm",
    ):
        cases.append(_file_case(filename, "extended"))
    cases.extend(_random_case(seed) for seed in _RANDOM_SEEDS)
    identifiers = [case.case_id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise AssertionError("duplicate L1 regression case identifier")
    return tuple(cases)


def _state_source(body: Iterable[str]) -> str:
    return _qasm(3, tuple(body))


def validate_decompositions() -> None:
    """Differentially check native SWAP, CU1, and CCX against standard forms."""

    preparation = (
        "h q[0]",
        "t q[0]",
        "ry(0.371) q[1]",
        "h q[2]",
        "s q[2]",
    )
    angle = "0.619"
    comparisons = {
        "swap": (
            preparation + ("swap q[0],q[1]",),
            preparation
            + (
                "cx q[0],q[1]",
                "cx q[1],q[0]",
                "cx q[0],q[1]",
            ),
        ),
        "cu1": (
            preparation + ("cu1(%s) q[0],q[1]" % angle,),
            preparation
            + (
                "rz((%s)/2) q[0]" % angle,
                "rz((%s)/2) q[1]" % angle,
                "cx q[0],q[1]",
                "rz(-(%s)/2) q[1]" % angle,
                "cx q[0],q[1]",
            ),
        ),
        "ccx": (
            preparation + ("ccx q[0],q[1],q[2]",),
            preparation
            + (
                "h q[2]",
                "cx q[1],q[2]",
                "tdg q[2]",
                "cx q[0],q[2]",
                "t q[2]",
                "cx q[1],q[2]",
                "tdg q[2]",
                "cx q[0],q[2]",
                "t q[1]",
                "t q[2]",
                "h q[2]",
                "cx q[0],q[1]",
                "t q[0]",
                "tdg q[1]",
                "cx q[0],q[1]",
            ),
        ),
    }
    for name, (native, decomposed) in comparisons.items():
        if not equivalent_up_to_global_phase(
            statevector(_state_source(native)),
            statevector(_state_source(decomposed)),
        ):
            raise AssertionError("%s decomposition changed statevector semantics" % name)


def _validate_result(result: Any, shots: int, width: int) -> Dict[str, float]:
    if not isinstance(result, Mapping):
        raise TypeError("runner result must be a mapping")
    required = ("backend", "job_id", "shots", "counts", "bit_order", "timestamp")
    missing = [field for field in required if field not in result]
    if missing:
        raise ValueError("runner result missing: %s" % ", ".join(missing))
    if result["shots"] != shots:
        raise ValueError("runner result shots mismatch")
    if result["bit_order"] != "little":
        raise ValueError("runner result bit_order must be little")
    if not isinstance(result["backend"], str) or not result["backend"]:
        raise ValueError("runner result backend must be non-empty text")
    if not isinstance(result["job_id"], str) or not result["job_id"]:
        raise ValueError("runner result job_id must be non-empty text")
    try:
        timestamp = datetime.fromisoformat(result["timestamp"])
    except (TypeError, ValueError) as exc:
        raise ValueError("runner result timestamp must be ISO-8601") from exc
    if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("runner result timestamp must be UTC")
    counts = result["counts"]
    if not isinstance(counts, Mapping) or not counts:
        raise ValueError("runner result counts must be a non-empty mapping")
    observed: Dict[str, float] = {}
    total = 0
    for key, value in counts.items():
        if not isinstance(key, str) or len(key) != width or set(key) - {"0", "1"}:
            raise ValueError("runner count key violates classical width")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("runner count must be a non-negative integer")
        observed[key] = value / shots
        total += value
    if total != shots:
        raise ValueError("runner counts do not total shots")
    if result.get("meta", {}).get("is_mock"):
        raise ValueError("mock runner results are forbidden")
    return observed


def run_regression(
    targets: Sequence[str] = DEFAULT_TARGETS,
    reporter=print,
) -> List[Dict[str, Any]]:
    """Run every circuit and return per-target records; never raises per case."""

    import adapter

    unknown = sorted(set(targets) - set(DEFAULT_TARGETS))
    if unknown:
        raise ValueError("unknown regression target: %s" % ", ".join(unknown))
    if not targets:
        raise ValueError("at least one regression target is required")

    validate_decompositions()
    reporter("[PASS] reference/decompositions: swap, cu1, ccx")
    records: List[Dict[str, Any]] = []
    for case in regression_cases():
        try:
            circuit = parse_qasm(case.source)
            expected = distribution(circuit)
        except Exception as exc:
            for target in targets:
                record = {
                    "case_id": case.case_id,
                    "target": target,
                    "status": "FAIL",
                    "reason": "reference %s: %s" % (type(exc).__name__, exc),
                }
                records.append(record)
                reporter("[FAIL] {case_id}:{target}: {reason}".format(**record))
            continue
        for target in targets:
            try:
                artifact = adapter.transpile(case.source, target)
                if not isinstance(artifact, str) or not artifact.strip():
                    raise ValueError("transpile returned an empty artifact")
                if artifact != adapter.transpile(case.source, target):
                    raise ValueError("transpile output is not deterministic")
                result = adapter.run(case.source, target, SHOTS)
                observed = _validate_result(result, SHOTS, circuit.classical_count)
                fidelity = hellinger_fidelity(observed, expected)
                if fidelity < FIDELITY_THRESHOLD:
                    raise AssertionError(
                        "fidelity %.6f is below %.2f" % (fidelity, FIDELITY_THRESHOLD)
                    )
                record = {
                    "case_id": case.case_id,
                    "target": target,
                    "status": "PASS",
                    "fidelity": fidelity,
                }
                records.append(record)
                reporter(
                    "[PASS] {case_id}:{target}: fidelity={fidelity:.6f}".format(**record)
                )
            except Exception as exc:
                record = {
                    "case_id": case.case_id,
                    "target": target,
                    "status": "FAIL",
                    "reason": "%s: %s" % (type(exc).__name__, exc),
                }
                records.append(record)
                reporter("[FAIL] {case_id}:{target}: {reason}".format(**record))
    return records


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the complete LoomQ L1 regression")
    parser.add_argument(
        "--target",
        default=",".join(DEFAULT_TARGETS),
        help="comma-separated subset of spinq,originq,braket",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list deterministic regression cases without running SDKs",
    )
    args = parser.parse_args(argv)
    if args.list:
        for case in regression_cases():
            print("%s (%s)" % (case.case_id, case.group))
        return 0
    targets = tuple(item.strip() for item in args.target.split(",") if item.strip())
    try:
        records = run_regression(targets)
    except Exception as exc:
        print("[FAIL] setup: %s: %s" % (type(exc).__name__, exc))
        return 1
    passed = sum(record["status"] == "PASS" for record in records)
    failed = len(records) - passed
    print("summary: passed=%d failed=%d total=%d shots=%d" % (passed, failed, len(records), SHOTS))
    return 0 if records and failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
