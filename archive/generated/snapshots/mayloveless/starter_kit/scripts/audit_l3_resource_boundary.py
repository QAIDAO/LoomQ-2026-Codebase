#!/usr/bin/env python3
"""运行 L3 release resource-boundary 与独立 differential 审计。"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


STARTER_KIT_ROOT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT_ROOT))

import adapter
from riscv_emulator import TinyRISCVEmulator
from scripts.audit_l3_differential import (
    QuantumExpectation,
    _parse_quantum_op,
    _quantum_mismatch,
    gate,
    measurement,
)


CASE_SET_VERSION = "l3-resource-boundary-2026-08-20-v1"
# 以下只保护固定 release audit case，不是 production 语言限制。
COMPILE_TIME_SENTINEL_SECONDS = 2.0
ASSEMBLY_SIZE_SENTINEL_BYTES = 64 * 1024
INSTRUCTION_COUNT_SENTINEL = 4096
MIN_EXECUTION_MARGIN_STEPS = 500


@dataclass(frozen=True)
class ResourceCase:
    case_id: str
    group: str
    source: str
    expected_quantum_ops: tuple[QuantumExpectation, ...]
    measurement_inputs: tuple[tuple[int, ...], ...]
    expected_registers: tuple[Mapping[int, int], ...]
    nesting_depth: int | None = None


class _CountingInstructions(list[tuple[str, list[str]]]):
    """统计真实 emulator 的 PC 取指次数，不替换其执行语义。"""

    def __init__(self, values: Sequence[tuple[str, list[str]]]) -> None:
        super().__init__(values)
        self.fetch_count = 0

    def __getitem__(self, index: int) -> tuple[str, list[str]]:
        self.fetch_count += 1
        return super().__getitem__(index)


def _hybrid_source(
    body: str,
    *,
    qubits: int,
    bits: int,
    quantum_operations: Sequence[str],
) -> str:
    return (
        "OPENQASM 2.0;\n"
        'include "qelib1.inc";\n'
        "qreg q[%d];\n" % qubits
        + "creg c[%d];\n" % bits
        + "\n".join(quantum_operations)
        + "\nclassical {\n"
        + body
        + "\n}\n"
    )


def _build_nested_case(depth: int) -> ResourceCase:
    def nested(level: int) -> str:
        if level == depth:
            return "r1 = %d;" % depth
        return (
            "if (c[%d] == 1) { %s } else { r1 = -%d; }"
            % (level, nested(level + 1), level + 1)
        )

    operations = ["measure q[%d] -> c[%d];" % (index, index) for index in range(depth)]
    expected_operations = tuple(measurement(index, index) for index in range(depth))
    inputs = [tuple(1 for _ in range(depth))]
    expected = [{1: depth}]
    for failing_level in range(depth):
        bits = tuple(0 if index == failing_level else 1 for index in range(depth))
        inputs.append(bits)
        expected.append({1: -(failing_level + 1)})
    return ResourceCase(
        case_id="nested_if_%d_levels" % depth,
        group="nested_if",
        source=_hybrid_source(
            nested(0),
            qubits=depth,
            bits=depth,
            quantum_operations=operations,
        ),
        expected_quantum_ops=expected_operations,
        measurement_inputs=tuple(inputs),
        expected_registers=tuple(expected),
        nesting_depth=depth,
    )


def _build_feedback_case() -> ResourceCase:
    bit_count = 6
    operations: list[str] = []
    expected_operations: list[QuantumExpectation] = []
    for index in range(bit_count):
        operations.extend(("h q[%d];" % index, "measure q[%d] -> c[%d];" % (index, index)))
        expected_operations.extend((gate("h", index), measurement(index, index)))

    statements = ["r1 = 0;"]
    for index in range(bit_count):
        weight = index + 1
        statements.append(
            "if (c[%d] == 1) { r1 = r1 + %d; } else { r1 = r1 - %d; }"
            % (index, weight, weight)
        )
    statements.extend(
        (
            "r2 = c[0] + c[1] + c[2] + c[3] + c[4] + c[5];",
            "if (r2 != 0) { r3 = r1 + r2; } else { r3 = r1 - 1; }",
        )
    )
    inputs = tuple(itertools.product((0, 1), repeat=bit_count))
    expected = []
    for bits in inputs:
        r1 = sum((index + 1) if value else -(index + 1) for index, value in enumerate(bits))
        r2 = sum(bits)
        r3 = r1 + r2 if r2 != 0 else r1 - 1
        expected.append({1: r1, 2: r2, 3: r3})
    return ResourceCase(
        case_id="measurement_feedback_6_bits",
        group="classical_feedback",
        source=_hybrid_source(
            "\n".join(statements),
            qubits=bit_count,
            bits=bit_count,
            quantum_operations=operations,
        ),
        expected_quantum_ops=tuple(expected_operations),
        measurement_inputs=inputs,
        expected_registers=tuple(expected),
    )


def _build_sequential_quantum_case() -> ResourceCase:
    qubit_count = 6
    operations: list[str] = []
    expected_operations: list[QuantumExpectation] = []
    for round_index in range(12):
        first = round_index % qubit_count
        second = (round_index + 1) % qubit_count
        third = (round_index + 2) % qubit_count
        angle_text, angle_value = (
            ("-pi/4", -math.pi / 4.0)
            if round_index % 2 == 0
            else ("pi/8", math.pi / 8.0)
        )
        operations.extend(
            (
                "h q[%d];" % first,
                "x q[%d];" % second,
                "ry(%s) q[%d];" % (angle_text, first),
                "rz(.5) q[%d];" % second,
                "cx q[%d], q[%d];" % (first, second),
                "swap q[%d], q[%d];" % (second, third),
                "ccx q[%d], q[%d], q[%d];" % (first, second, third),
            )
        )
        expected_operations.extend(
            (
                gate("h", first),
                gate("x", second),
                gate("ry", first, parameter=angle_value),
                gate("rz", second, parameter=0.5),
                gate("cx", first, second),
                gate("swap", second, third),
                gate("ccx", first, second, third),
            )
        )
    for index in range(qubit_count):
        operations.append("measure q[%d] -> c[%d];" % (index, index))
        expected_operations.append(measurement(index, index))

    inputs = (
        (0, 0, 0, 0, 0, 0),
        (1, 1, 1, 1, 1, 1),
        (1, 0, 1, 0, 1, 0),
        (0, 1, 0, 1, 0, 1),
    )
    expected = tuple({1: sum(bits)} for bits in inputs)
    return ResourceCase(
        case_id="sequential_quantum_90_ops",
        group="sequential",
        source=_hybrid_source(
            "r1 = c[0] + c[1] + c[2] + c[3] + c[4] + c[5];",
            qubits=qubit_count,
            bits=qubit_count,
            quantum_operations=operations,
        ),
        expected_quantum_ops=tuple(expected_operations),
        measurement_inputs=inputs,
        expected_registers=expected,
    )


def _sequential_expected(bits: tuple[int, int]) -> Mapping[int, int]:
    registers = {index: index for index in range(1, 10)}
    for _ in range(12):
        registers[1] += bits[0]
        for index in range(2, 10):
            subtraction = 1 if index < 9 else bits[1]
            registers[index] = registers[index] + registers[index - 1] - subtraction
    return registers


def _build_sequential_classical_case() -> ResourceCase:
    statements = ["r%d = %d;" % (index, index) for index in range(1, 10)]
    for _ in range(12):
        statements.append("r1 = r1 + c[0];")
        for index in range(2, 9):
            statements.append(
                "r%d = r%d + r%d - 1;" % (index, index, index - 1)
            )
        statements.append("r9 = r9 + r8 - c[1];")
    inputs = tuple(itertools.product((0, 1), repeat=2))
    return ResourceCase(
        case_id="sequential_classical_117_assignments",
        group="sequential",
        source=_hybrid_source(
            "\n".join(statements),
            qubits=2,
            bits=2,
            quantum_operations=(
                "measure q[0] -> c[0];",
                "measure q[1] -> c[1];",
            ),
        ),
        expected_quantum_ops=(measurement(0, 0), measurement(1, 1)),
        measurement_inputs=inputs,
        expected_registers=tuple(_sequential_expected(bits) for bits in inputs),
    )


RESOURCE_CASES = (
    _build_nested_case(3),
    _build_nested_case(5),
    _build_nested_case(8),
    _build_feedback_case(),
    _build_sequential_quantum_case(),
    _build_sequential_classical_case(),
)


def _repository_state() -> dict[str, Any]:
    root = STARTER_KIT_ROOT.parent
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(root),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=True,
            ).stdout.strip()
        )
        return {"source_commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"source_commit": "unavailable", "dirty": None}


def _instruction_count(assembly: str) -> int:
    return sum(
        1
        for line in assembly.splitlines()
        if line.strip() and not line.strip().endswith(":")
    )


def _execute_with_count(
    assembly: str,
    bits: Sequence[int],
) -> tuple[dict[str, int], int, int]:
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    instructions = _CountingInstructions(emulator.instructions)
    emulator.instructions = instructions
    for index, value in enumerate(bits):
        emulator.set_register("x%d" % (10 + index), value)
    state = emulator.execute()
    return state, instructions.fetch_count, emulator.max_steps


def _expected_payload(case: ResourceCase) -> dict[str, Any]:
    return {
        "quantum_ops": [asdict(operation) for operation in case.expected_quantum_ops],
        "classical_outcomes": [
            {
                "measurement_bits": list(bits),
                "registers": {"r%d" % key: value for key, value in expected.items()},
            }
            for bits, expected in zip(case.measurement_inputs, case.expected_registers)
        ],
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "compile_time_seconds": 0.0,
        "assembly_size_bytes": 0,
        "instruction_count": 0,
        "quantum_operation_count": 0,
        "execution_count": 0,
        "max_execution_steps": 0,
        "emulator_max_steps": None,
    }


def _evaluate_case(case: ResourceCase) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "case_id": case.case_id,
        "group": case.group,
        "nesting_depth": case.nesting_depth,
        "source": case.source,
        "status": "FAIL",
        "semantic": {"quantum": "NOT_RUN", "classical": "NOT_RUN"},
        "metrics": _empty_metrics(),
        "expected": _expected_payload(case),
        "actual": {"quantum_ops": None, "assembly": None, "classical_outcomes": []},
        "failure": None,
    }
    compile_started = time.perf_counter()
    try:
        quantum_ops, assembly = adapter.compile_hybrid(case.source)
    except RecursionError as exc:
        entry["metrics"]["compile_time_seconds"] = round(
            time.perf_counter() - compile_started, 6
        )
        entry["failure"] = {
            "classification": "parser recursion",
            "message": "%s: %s" % (type(exc).__name__, exc),
        }
        return entry
    except Exception as exc:
        entry["metrics"]["compile_time_seconds"] = round(
            time.perf_counter() - compile_started, 6
        )
        classification = (
            "register allocation"
            if "scratch register" in str(exc).lower()
            else "compiler expansion"
        )
        entry["failure"] = {
            "classification": classification,
            "message": "%s: %s" % (type(exc).__name__, exc),
        }
        return entry

    compile_time = time.perf_counter() - compile_started
    entry["metrics"].update(
        {
            "compile_time_seconds": round(compile_time, 6),
            "assembly_size_bytes": len(assembly.encode("utf-8")),
            "instruction_count": _instruction_count(assembly),
            "quantum_operation_count": len(quantum_ops),
        }
    )
    entry["actual"]["quantum_ops"] = list(quantum_ops)
    entry["actual"]["assembly"] = assembly

    try:
        parsed_operations = tuple(_parse_quantum_op(item) for item in quantum_ops)
        mismatch = _quantum_mismatch(case.expected_quantum_ops, parsed_operations)
    except Exception as exc:
        mismatch = "%s while independently reading quantum output" % type(exc).__name__
    if mismatch is not None:
        entry["semantic"]["quantum"] = "FAIL"
        entry["failure"] = {
            "classification": "compiler expansion",
            "message": mismatch,
        }
        return entry
    entry["semantic"]["quantum"] = "PASS"

    max_execution_steps = 0
    emulator_max_steps: int | None = None
    for bits, expected_registers in zip(
        case.measurement_inputs,
        case.expected_registers,
    ):
        try:
            state, steps, max_steps = _execute_with_count(assembly, bits)
        except RuntimeError as exc:
            entry["semantic"]["classical"] = "FAIL"
            entry["failure"] = {
                "classification": "runtime steps",
                "message": str(exc),
                "measurement_bits": list(bits),
            }
            return entry
        except Exception as exc:
            entry["semantic"]["classical"] = "FAIL"
            entry["failure"] = {
                "classification": "emulator issue",
                "message": "%s: %s" % (type(exc).__name__, exc),
                "measurement_bits": list(bits),
            }
            return entry
        max_execution_steps = max(max_execution_steps, steps)
        emulator_max_steps = max_steps
        actual_registers = {
            index: state.get("x%d" % index, 0) for index in range(1, 10)
        }
        expected_all = {
            index: expected_registers.get(index, 0) for index in range(1, 10)
        }
        entry["actual"]["classical_outcomes"].append(
            {
                "measurement_bits": list(bits),
                "execution_steps": steps,
                "register_final_state": state,
                "result_registers": {
                    "r%d" % index: value for index, value in actual_registers.items()
                },
            }
        )
        if actual_registers != expected_all:
            entry["semantic"]["classical"] = "FAIL"
            entry["failure"] = {
                "classification": "emulator issue",
                "message": "classical final state mismatch",
                "measurement_bits": list(bits),
                "expected_result": {
                    "r%d" % index: value for index, value in expected_all.items()
                },
                "actual_result": {
                    "r%d" % index: value for index, value in actual_registers.items()
                },
            }
            return entry

    entry["semantic"]["classical"] = "PASS"
    entry["metrics"].update(
        {
            "execution_count": len(case.measurement_inputs),
            "max_execution_steps": max_execution_steps,
            "emulator_max_steps": emulator_max_steps,
        }
    )
    failures = []
    if compile_time > COMPILE_TIME_SENTINEL_SECONDS:
        failures.append("compile time crossed audit sentinel")
    if entry["metrics"]["assembly_size_bytes"] > ASSEMBLY_SIZE_SENTINEL_BYTES:
        failures.append("assembly size crossed audit sentinel")
    if entry["metrics"]["instruction_count"] > INSTRUCTION_COUNT_SENTINEL:
        failures.append("instruction count crossed audit sentinel")
    if (
        emulator_max_steps is not None
        and emulator_max_steps - max_execution_steps < MIN_EXECUTION_MARGIN_STEPS
    ):
        failures.append("execution safety margin crossed audit sentinel")
    if failures:
        entry["failure"] = {
            "classification": (
                "runtime steps"
                if failures[-1].startswith("execution")
                else "compiler expansion"
            ),
            "message": "; ".join(failures),
        }
        return entry

    entry["status"] = "PASS"
    return entry


def build_report() -> dict[str, Any]:
    started = time.perf_counter()
    repository = _repository_state()
    entries = [_evaluate_case(case) for case in RESOURCE_CASES]
    passed = sum(entry["status"] == "PASS" for entry in entries)
    failed = len(entries) - passed
    max_compile_time = max(entry["metrics"]["compile_time_seconds"] for entry in entries)
    max_assembly_size = max(entry["metrics"]["assembly_size_bytes"] for entry in entries)
    max_instruction_count = max(entry["metrics"]["instruction_count"] for entry in entries)
    max_execution_steps = max(entry["metrics"]["max_execution_steps"] for entry in entries)
    emulator_limits = [
        entry["metrics"]["emulator_max_steps"]
        for entry in entries
        if entry["metrics"]["emulator_max_steps"] is not None
    ]
    emulator_max_steps = min(emulator_limits) if emulator_limits else None
    step_margin = (
        emulator_max_steps - max_execution_steps
        if emulator_max_steps is not None
        else None
    )
    step_margin_percent = (
        round(step_margin / emulator_max_steps * 100.0, 2)
        if step_margin is not None and emulator_max_steps
        else None
    )
    return {
        "case_set_version": CASE_SET_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": repository["source_commit"],
        "dirty": repository["dirty"],
        "status": "PASS" if failed == 0 else "FAIL",
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "summary": {
            "total": len(entries),
            "passed": passed,
            "failed": failed,
            "execution_count": sum(
                entry["metrics"]["execution_count"] for entry in entries
            ),
        },
        "maxima": {
            "compile_time_seconds": max_compile_time,
            "assembly_size_bytes": max_assembly_size,
            "instruction_count": max_instruction_count,
            "execution_steps": max_execution_steps,
            "emulator_max_steps": emulator_max_steps,
        },
        "safety_margin": {
            "execution_steps": step_margin,
            "execution_percent": step_margin_percent,
            "assessment": (
                "SAFE"
                if step_margin is not None
                and step_margin >= MIN_EXECUTION_MARGIN_STEPS
                else "REVIEW"
            ),
        },
        "audit_sentinels": {
            "compile_time_seconds": COMPILE_TIME_SENTINEL_SECONDS,
            "assembly_size_bytes": ASSEMBLY_SIZE_SENTINEL_BYTES,
            "instruction_count": INSTRUCTION_COUNT_SENTINEL,
            "minimum_execution_margin_steps": MIN_EXECUTION_MARGIN_STEPS,
            "scope": "fixed release audit cases only; not a production language limit",
        },
        "cases": entries,
        "remaining_risk": [
            "Finite release cases do not prove bounds for arbitrary source size or nesting.",
            "Compile-time measurements remain dependent on local host load.",
            "Tiny RISC-V executes the classical assembly only; quantum operations are checked structurally and semantically but are not simulated here.",
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    report = build_report()
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
