#!/usr/bin/env python3
"""运行版本化 L3 hidden-like 与独立 differential 审计。"""

from __future__ import annotations

import argparse
import ast
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import itertools
import json
import math
from pathlib import Path
import random
import re
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


STARTER_KIT_ROOT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT_ROOT))

import adapter
from riscv_emulator import TinyRISCVEmulator


CASE_SET_VERSION = "l3-hidden-like-2026-08-20-v1"
RANDOM_SEEDS = tuple(15000 + index for index in range(24))
_ALLOWED_INSTRUCTIONS = {"li", "add", "sub", "addi", "beq", "bne", "j"}
_QUBIT_RE = re.compile(r"q\[(\d+)\]\Z")
_MEASUREMENT_RE = re.compile(
    r"measure\s+q\[(\d+)\]\s*->\s*c\[(\d+)\];\Z"
)
_GATE_RE = re.compile(r"([a-z][a-z0-9_]*)\s*(?:\((.*)\))?\s+(.+);\Z")


@dataclass(frozen=True)
class QuantumExpectation:
    """测试侧独立量子操作表示，不复用 production AST。"""

    gate: str
    qubits: tuple[int, ...]
    parameter: float | None = None
    classical_bit: int | None = None


@dataclass(frozen=True)
class ClassicalOutcome:
    bits: tuple[int, ...]
    registers: Mapping[int, int]


@dataclass(frozen=True)
class DeterministicCase:
    case_id: str
    group: str
    source: str
    expected_quantum_ops: tuple[QuantumExpectation, ...] = ()
    outcomes: tuple[ClassicalOutcome, ...] = ()
    expected_error: bool = False


@dataclass(frozen=True)
class RandomCase:
    seed: int
    source: str
    qubit_count: int
    classical_bit_count: int
    quantum_depth: int
    expected_quantum_ops: tuple[QuantumExpectation, ...]
    measurement_inputs: tuple[tuple[int, ...], ...]
    expected_registers: tuple[Mapping[int, int], ...]


def gate(
    name: str,
    *qubits: int,
    parameter: float | None = None,
) -> QuantumExpectation:
    return QuantumExpectation(name, tuple(qubits), parameter, None)


def measurement(qubit: int, classical_bit: int) -> QuantumExpectation:
    return QuantumExpectation("measure", (qubit,), None, classical_bit)


def outcome(bits: Sequence[int], **registers: int) -> ClassicalOutcome:
    return ClassicalOutcome(
        tuple(bits),
        {int(name[1:]): value for name, value in registers.items()},
    )


def hybrid_source(
    body: str,
    *,
    qubits: int,
    bits: int,
    before: str = "",
    after: str = "",
) -> str:
    return (
        "OPENQASM 2.0;\n"
        'include "qelib1.inc";\n'
        "qreg q[%d];\n" % qubits
        + "creg c[%d];\n" % bits
        + before
        + "classical {\n"
        + body
        + "\n}\n"
        + after
    )


DETERMINISTIC_CASES = (
    DeterministicCase(
        "basic_declarations_gate_measure",
        "basic",
        hybrid_source(
            "r1 = c[0];",
            qubits=1,
            bits=1,
            before="h q[0];\nmeasure q[0] -> c[0];\n",
        ),
        (gate("h", 0), measurement(0, 0)),
        (outcome((0,), r1=0), outcome((1,), r1=1)),
    ),
    DeterministicCase(
        "basic_single_gate_sequence",
        "basic",
        hybrid_source(
            "r1 = 7;",
            qubits=2,
            bits=1,
            before="x q[1];\ns q[0];\nsdg q[1];\nt q[0];\ntdg q[1];\n",
        ),
        (
            gate("x", 1),
            gate("s", 0),
            gate("sdg", 1),
            gate("t", 0),
            gate("tdg", 1),
        ),
        (outcome((0,), r1=7),),
    ),
    DeterministicCase(
        "basic_parameter_gates",
        "basic",
        hybrid_source(
            "r1 = -2;",
            qubits=2,
            bits=1,
            before="ry(-pi/2) q[0];\nrz(.5) q[1];\n",
        ),
        (
            gate("ry", 0, parameter=-math.pi / 2.0),
            gate("rz", 1, parameter=0.5),
        ),
        (outcome((0,), r1=-2),),
    ),
    DeterministicCase(
        "basic_multiqubit_operand_order",
        "basic",
        hybrid_source(
            "r1 = 1;",
            qubits=5,
            bits=1,
            before="cx q[4],q[1];\nswap q[0], q[3];\nccx q[4],q[2],q[1];\n",
        ),
        (
            gate("cx", 4, 1),
            gate("swap", 0, 3),
            gate("ccx", 4, 2, 1),
        ),
        (outcome((0,), r1=1),),
    ),
    DeterministicCase(
        "logic_else_branch",
        "logic",
        hybrid_source(
            "if (c[0] == 1) { r1 = 10; } else { r1 = 20; }",
            qubits=1,
            bits=1,
        ),
        (),
        (outcome((0,), r1=20), outcome((1,), r1=10)),
    ),
    DeterministicCase(
        "logic_nested_if",
        "logic",
        hybrid_source(
            "if (c[0] == 1) {\n"
            "  if (c[1] != 0) { r1 = 11; } else { r1 = 12; }\n"
            "} else { r1 = 13; }",
            qubits=2,
            bits=2,
        ),
        (),
        (
            outcome((0, 0), r1=13),
            outcome((1, 0), r1=12),
            outcome((1, 1), r1=11),
        ),
    ),
    DeterministicCase(
        "logic_three_levels",
        "logic",
        hybrid_source(
            "if (c[0] == 1) { if (c[1] == 1) { if (c[2] == 1) "
            "{ r1 = 7; } else { r1 = 6; } } else { r1 = 5; } } "
            "else { r1 = 4; }",
            qubits=3,
            bits=3,
        ),
        (),
        (
            outcome((0, 1, 1), r1=4),
            outcome((1, 0, 1), r1=5),
            outcome((1, 1, 0), r1=6),
            outcome((1, 1, 1), r1=7),
        ),
    ),
    DeterministicCase(
        "logic_multiple_conditions",
        "logic",
        hybrid_source(
            "r1 = 3;\n"
            "if (c[0] != 0) { r1 = r1 + 4; } else { r1 = r1 - 1; }\n"
            "if (r1 == 7) { r2 = 9; } else { r2 = -9; }",
            qubits=1,
            bits=1,
        ),
        (),
        (outcome((0,), r1=2, r2=-9), outcome((1,), r1=7, r2=9)),
    ),
    DeterministicCase(
        "expression_signed_integers",
        "expression",
        hybrid_source(
            "r1 = -7; r2 = +5; r3 = r1 + r2; r4 = 0 - r3;",
            qubits=1,
            bits=1,
        ),
        (),
        (outcome((0,), r1=-7, r2=5, r3=-2, r4=2),),
    ),
    DeterministicCase(
        "expression_variable_references",
        "expression",
        hybrid_source(
            "r1 = c[0] + 4; r2 = r1 - c[1]; r3 = r2 + (r1 - 2);",
            qubits=2,
            bits=2,
        ),
        (),
        (
            outcome((0, 0), r1=4, r2=4, r3=6),
            outcome((1, 1), r1=5, r2=4, r3=7),
        ),
    ),
    DeterministicCase(
        "expression_associativity",
        "expression",
        hybrid_source(
            "r1 = 10 - 3 - 2; r2 = 10 - (3 - 2); r3 = -(r1 - r2);",
            qubits=1,
            bits=1,
        ),
        (),
        (outcome((0,), r1=5, r2=9, r3=4),),
    ),
    DeterministicCase(
        "expression_float_and_negative_angles",
        "expression",
        hybrid_source(
            "r1 = 1;",
            qubits=2,
            bits=1,
            before="ry(-0.25) q[0]; rz(3*pi/8) q[1];\n",
        ),
        (
            gate("ry", 0, parameter=-0.25),
            gate("rz", 1, parameter=3.0 * math.pi / 8.0),
        ),
        (outcome((0,), r1=1),),
    ),
    DeterministicCase(
        "hybrid_measurement_feedback",
        "hybrid",
        hybrid_source(
            "if (c[0] == 1) { r1 = 101; } else { r1 = 202; }",
            qubits=2,
            bits=1,
            before="h q[0]; measure q[0] -> c[0];\n",
            after="x q[1];\n",
        ),
        (gate("h", 0), measurement(0, 0), gate("x", 1)),
        (outcome((0,), r1=202), outcome((1,), r1=101)),
    ),
    DeterministicCase(
        "hybrid_multiple_measurements",
        "hybrid",
        hybrid_source(
            "r1 = c[0] + c[1];",
            qubits=3,
            bits=2,
            before="measure q[2] -> c[1]; measure q[0] -> c[0];\n",
            after="swap q[2], q[0];\n",
        ),
        (measurement(2, 1), measurement(0, 0), gate("swap", 2, 0)),
        (
            outcome((0, 0), r1=0),
            outcome((1, 0), r1=1),
            outcome((0, 1), r1=1),
            outcome((1, 1), r1=2),
        ),
    ),
    DeterministicCase(
        "hybrid_multi_bit_feedback",
        "hybrid",
        hybrid_source(
            "if (c[0] != c[1]) { r1 = 1; } else { r1 = 0; }\n"
            "if (r1 == 1) { r2 = c[2] + 8; } else { r2 = c[2] - 8; }",
            qubits=3,
            bits=3,
            before=(
                "measure q[0] -> c[0]; measure q[1] -> c[1]; "
                "measure q[2] -> c[2];\n"
            ),
            after="ccx q[0], q[1], q[2];\n",
        ),
        (
            measurement(0, 0),
            measurement(1, 1),
            measurement(2, 2),
            gate("ccx", 0, 1, 2),
        ),
        (
            outcome((0, 0, 1), r1=0, r2=-7),
            outcome((0, 1, 1), r1=1, r2=9),
        ),
    ),
    DeterministicCase(
        "boundary_empty_branches",
        "boundary",
        hybrid_source(
            "if (c[0] == 0) { } else { r1 = 1; }\n"
            "if (c[0] != 0) { } else { r2 = 2; }",
            qubits=1,
            bits=1,
        ),
        (),
        (outcome((0,), r1=0, r2=2), outcome((1,), r1=1, r2=0)),
    ),
    DeterministicCase(
        "boundary_whitespace_comments",
        "boundary",
        (
            'OPENQASM 2.0; include "qelib1.inc"; qreg q[2]; creg c[1];\n'
            "ry ( - pi / 4 ) q [ 1 ] ; // whitespace must preserve angle semantics\n"
            "classical/*gap*/{r1=-3+c[0];}\n"
        ),
        (gate("ry", 1, parameter=-math.pi / 4.0),),
        (outcome((0,), r1=-3), outcome((1,), r1=-2)),
    ),
    DeterministicCase(
        "boundary_invalid_variable",
        "boundary",
        hybrid_source("result = 1;", qubits=1, bits=1),
        expected_error=True,
    ),
    DeterministicCase(
        "boundary_unsupported_return",
        "boundary",
        hybrid_source("r1 = 1; return r1;", qubits=1, bits=1),
        expected_error=True,
    ),
    DeterministicCase(
        "boundary_unsupported_multiply",
        "boundary",
        hybrid_source("r1 = c[0] * 2;", qubits=1, bits=1),
        expected_error=True,
    ),
    DeterministicCase(
        "boundary_keyword_case",
        "boundary",
        (
            'OPENQASM 2.0; include "qelib1.inc"; qreg q[1]; creg c[1];\n'
            "Classical { r1 = 1; }\n"
        ),
        expected_error=True,
    ),
)


def _random_gate(
    rng: random.Random,
    qubit_count: int,
) -> tuple[str, QuantumExpectation]:
    choices = ["h", "x", "ry", "rz"]
    if qubit_count >= 2:
        choices.extend(("cx", "swap"))
    if qubit_count >= 3:
        choices.append("ccx")
    name = rng.choice(choices)
    if name in ("h", "x"):
        qubit = rng.randrange(qubit_count)
        return "%s q[%d];" % (name, qubit), gate(name, qubit)
    if name in ("ry", "rz"):
        parameter_text, parameter = rng.choice(
            (
                ("-pi/2", -math.pi / 2.0),
                ("-.5", -0.5),
                ("0.25", 0.25),
                ("pi/4", math.pi / 4.0),
            )
        )
        qubit = rng.randrange(qubit_count)
        return (
            "%s(%s) q[%d];" % (name, parameter_text, qubit),
            gate(name, qubit, parameter=parameter),
        )
    count = 2 if name in ("cx", "swap") else 3
    qubits = tuple(rng.sample(range(qubit_count), count))
    return (
        "%s %s;" % (name, ",".join("q[%d]" % item for item in qubits)),
        gate(name, *qubits),
    )


def _build_random_case(seed: int) -> RandomCase:
    rng = random.Random(seed)
    qubit_count = rng.randint(1, 5)
    classical_bit_count = rng.randint(1, 3)
    quantum_depth = rng.randint(3, 8)
    measurement_count = rng.randint(1, min(classical_bit_count, quantum_depth))
    measurement_positions = set(rng.sample(range(quantum_depth), measurement_count))
    source_operations: list[str] = []
    expected_operations: list[QuantumExpectation] = []
    for index in range(quantum_depth):
        if index in measurement_positions:
            qubit = rng.randrange(qubit_count)
            classical_bit = rng.randrange(classical_bit_count)
            source_operations.append(
                "measure q[%d] -> c[%d];" % (qubit, classical_bit)
            )
            expected_operations.append(measurement(qubit, classical_bit))
        else:
            source_operation, expected_operation = _random_gate(rng, qubit_count)
            source_operations.append(source_operation)
            expected_operations.append(expected_operation)

    base = rng.randint(-6, 6)
    offset = rng.randint(-4, 4)
    delta = rng.randint(1, 5)
    first_bit = rng.randrange(classical_bit_count)
    second_bit = rng.randrange(classical_bit_count)
    expected_bit = rng.randint(0, 1)
    nested = rng.random() < 0.5
    if nested:
        body = (
            "r1 = %d;\n" % base
            + "r2 = r1 + c[%d] - (%d);\n" % (first_bit, offset)
            + "if (c[%d] == %d) {\n" % (second_bit, expected_bit)
            + "  if (c[%d] != 0) { r3 = r2 + %d; } " % (first_bit, delta)
            + "else { r3 = r2 - %d; }\n" % delta
            + "} else { r3 = r2 - %d; }\n" % (delta + 1)
            + "r4 = r3 + c[%d];" % first_bit
        )
    else:
        body = (
            "r1 = %d;\n" % base
            + "r2 = r1 + c[%d] - (%d);\n" % (first_bit, offset)
            + "if (c[%d] == %d) { r3 = r2 + %d; } "
            "else { r3 = r2 - %d; }\n"
            % (second_bit, expected_bit, delta, delta)
            + "r4 = r3 + c[%d];" % first_bit
        )

    split = rng.randint(1, quantum_depth - 1)
    source = hybrid_source(
        body,
        qubits=qubit_count,
        bits=classical_bit_count,
        before="\n".join(source_operations[:split]) + "\n",
        after="\n".join(source_operations[split:]) + "\n",
    )
    inputs = tuple(itertools.product((0, 1), repeat=classical_bit_count))
    expected_registers = []
    for bits in inputs:
        r1 = base
        r2 = r1 + bits[first_bit] - offset
        if bits[second_bit] == expected_bit:
            if nested:
                r3 = r2 + delta if bits[first_bit] != 0 else r2 - delta
            else:
                r3 = r2 + delta
        else:
            r3 = r2 - (delta + 1 if nested else delta)
        r4 = r3 + bits[first_bit]
        expected_registers.append({1: r1, 2: r2, 3: r3, 4: r4})
    return RandomCase(
        seed=seed,
        source=source,
        qubit_count=qubit_count,
        classical_bit_count=classical_bit_count,
        quantum_depth=quantum_depth,
        expected_quantum_ops=tuple(expected_operations),
        measurement_inputs=inputs,
        expected_registers=tuple(expected_registers),
    )


RANDOM_CASES = tuple(_build_random_case(seed) for seed in RANDOM_SEEDS)


def _angle_value(text: str) -> float:
    """测试侧独立计算有限角表达式，不调用 production expression parser。"""
    tree = ast.parse(text.strip(), mode="eval")

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id == "pi":
            return math.pi
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
        ):
            left = visit(node.left)
            right = visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            return left / right
        raise ValueError("unsupported independent angle expression")

    value = visit(tree)
    if not math.isfinite(value):
        raise ValueError("non-finite angle")
    return value


def _parse_quantum_op(text: str) -> QuantumExpectation:
    measurement_match = _MEASUREMENT_RE.fullmatch(text.strip().lower())
    if measurement_match is not None:
        return measurement(
            int(measurement_match.group(1)),
            int(measurement_match.group(2)),
        )
    match = _GATE_RE.fullmatch(text.strip().lower())
    if match is None:
        raise ValueError("unrecognized compiled quantum operation")
    qubits = []
    for raw_operand in match.group(3).split(","):
        qubit_match = _QUBIT_RE.fullmatch(raw_operand.strip())
        if qubit_match is None:
            raise ValueError("unrecognized compiled qubit operand")
        qubits.append(int(qubit_match.group(1)))
    parameter = _angle_value(match.group(2)) if match.group(2) is not None else None
    return QuantumExpectation(match.group(1), tuple(qubits), parameter, None)


def _quantum_mismatch(
    expected: Sequence[QuantumExpectation],
    actual: Sequence[QuantumExpectation],
) -> str | None:
    if len(expected) != len(actual):
        return "quantum operation count: expected %d, actual %d" % (
            len(expected),
            len(actual),
        )
    for index, (wanted, observed) in enumerate(zip(expected, actual)):
        if (
            wanted.gate != observed.gate
            or wanted.qubits != observed.qubits
            or wanted.classical_bit != observed.classical_bit
        ):
            return "quantum operation %d structure mismatch" % index
        if wanted.parameter is None or observed.parameter is None:
            if wanted.parameter != observed.parameter:
                return "quantum operation %d parameter presence mismatch" % index
        elif not math.isclose(
            wanted.parameter,
            observed.parameter,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            return "quantum operation %d parameter mismatch" % index
    return None


def _execute_assembly(assembly: str, bits: Sequence[int]) -> dict[int, int]:
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    for index, value in enumerate(bits):
        emulator.set_register("x%d" % (10 + index), value)
    state = emulator.execute()
    return {index: state.get("x%d" % index, 0) for index in range(1, 10)}


def _validate_assembly(assembly: str) -> str | None:
    for line_number, line in enumerate(assembly.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.endswith(":"):
            continue
        instruction = stripped.split()[0].lower()
        if instruction not in _ALLOWED_INSTRUCTIONS:
            return "unsupported assembly instruction at line %d" % line_number
    return None


def _expectation_payload(
    operations: Sequence[QuantumExpectation],
    inputs: Sequence[Sequence[int]],
    registers: Sequence[Mapping[int, int]],
) -> dict[str, Any]:
    return {
        "quantum_ops": [asdict(operation) for operation in operations],
        "classical_outcomes": [
            {
                "bits": list(bits),
                "registers": {"r%d" % key: value for key, value in expected.items()},
            }
            for bits, expected in zip(inputs, registers)
        ],
    }


def _compiled_payload(quantum_ops: Sequence[str], assembly: str) -> dict[str, Any]:
    return {"quantum_ops": list(quantum_ops), "assembly": assembly}


def _evaluate_case(
    *,
    case_id: str,
    kind: str,
    source: str,
    expected_operations: Sequence[QuantumExpectation],
    inputs: Sequence[Sequence[int]],
    expected_registers: Sequence[Mapping[int, int]],
    expected_error: bool = False,
    seed: int | None = None,
    group: str | None = None,
) -> tuple[dict[str, Any], int]:
    started = time.perf_counter()
    entry: dict[str, Any] = {
        "case_id": case_id,
        "kind": kind,
        "group": group,
        "seed": seed,
        "source": source,
        "status": "FAIL",
        "mismatch": None,
        "root_cause": None,
        "expected": (
            {"error": "unsupported_or_invalid_source"}
            if expected_error
            else _expectation_payload(
                expected_operations,
                inputs,
                expected_registers,
            )
        ),
        "compiled_ir": None,
    }
    executions = 0
    try:
        quantum_ops, assembly = adapter.compile_hybrid(source)
        entry["compiled_ir"] = _compiled_payload(quantum_ops, assembly)
        if expected_error:
            entry["mismatch"] = "invalid source compiled successfully"
            entry["root_cause"] = "parser"
            return entry, executions
        assembly_mismatch = _validate_assembly(assembly)
        if assembly_mismatch is not None:
            entry["mismatch"] = assembly_mismatch
            entry["root_cause"] = "serializer"
            return entry, executions
        actual_operations = tuple(_parse_quantum_op(item) for item in quantum_ops)
        mismatch = _quantum_mismatch(expected_operations, actual_operations)
        if mismatch is not None:
            entry["mismatch"] = mismatch
            entry["root_cause"] = "AST extraction"
            return entry, executions
        for bits, expected in zip(inputs, expected_registers):
            actual = _execute_assembly(assembly, bits)
            executions += 1
            expected_all = {
                index: expected.get(index, 0) for index in range(1, 10)
            }
            if actual != expected_all:
                entry["mismatch"] = (
                    "classical registers differ for measurement input %s" % (tuple(bits),)
                )
                entry["root_cause"] = "IR generation or runtime"
                return entry, executions
        entry["status"] = "PASS"
        return entry, executions
    except Exception as exc:
        if expected_error:
            entry["status"] = "PASS"
            entry["compiled_ir"] = {"rejected_by": type(exc).__name__}
        else:
            entry["mismatch"] = "%s during compilation or validation" % type(exc).__name__
            entry["root_cause"] = "parser or IR generation"
        return entry, executions
    finally:
        entry["elapsed_seconds"] = round(time.perf_counter() - started, 6)


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


def build_report() -> dict[str, Any]:
    started = time.perf_counter()
    repository = _repository_state()
    entries: list[dict[str, Any]] = []
    measurement_executions = 0
    for case in DETERMINISTIC_CASES:
        entry, executions = _evaluate_case(
            case_id=case.case_id,
            kind="deterministic",
            group=case.group,
            source=case.source,
            expected_operations=case.expected_quantum_ops,
            inputs=tuple(item.bits for item in case.outcomes),
            expected_registers=tuple(item.registers for item in case.outcomes),
            expected_error=case.expected_error,
        )
        entries.append(entry)
        measurement_executions += executions
    for case in RANDOM_CASES:
        entry, executions = _evaluate_case(
            case_id="random_%d" % case.seed,
            kind="random",
            seed=case.seed,
            source=case.source,
            expected_operations=case.expected_quantum_ops,
            inputs=case.measurement_inputs,
            expected_registers=case.expected_registers,
        )
        entries.append(entry)
        measurement_executions += executions
    passed = sum(entry["status"] == "PASS" for entry in entries)
    failed = len(entries) - passed
    return {
        "suite": "l3-hidden-like-differential",
        "case_set_version": CASE_SET_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": repository["source_commit"],
        "dirty": repository["dirty"],
        "status": "PASS" if failed == 0 else "FAIL",
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "summary": {
            "passed": passed,
            "failed": failed,
            "total": len(entries),
            "deterministic": len(DETERMINISTIC_CASES),
            "random": len(RANDOM_CASES),
        },
        "random_seeds": list(RANDOM_SEEDS),
        "measurement_executions": measurement_executions,
        "cases": entries,
        "uncovered_risks": [
            "quantum_ops are structurally audited but are not executed as a unified hybrid runtime",
            "official material does not define c[22+] mapping beyond x31",
            "Hybrid-QASM is the official input; Python return semantics are intentionally unsupported",
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)
    report = build_report()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(rendered + "\n", encoding="utf-8")
        print(
            "[%s] %s: %d pass, %d fail, %d measurement executions"
            % (
                report["status"],
                CASE_SET_VERSION,
                report["summary"]["passed"],
                report["summary"]["failed"],
                report["measurement_executions"],
            )
        )
    else:
        print(rendered)
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CASE_SET_VERSION",
    "DETERMINISTIC_CASES",
    "RANDOM_CASES",
    "RANDOM_SEEDS",
    "build_report",
    "main",
]
