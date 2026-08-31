#!/usr/bin/env python3
"""Hidden-test oriented local checks for the Hybrid-QASM compiler."""

from __future__ import annotations

import itertools
import math
import os
import random
import re
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import adapter  # noqa: E402
import l3_hybrid_compiler as l3  # noqa: E402
from riscv_emulator import TinyRISCVEmulator  # noqa: E402


RANDOM_SEEDS = [17, 101, 2026, 658]
PROGRAMS_PER_SEED = 302


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def hybrid(
    classical: str,
    quantum_before: str = "measure q[0] -> c[0];",
    quantum_after: str = "",
    q: int = 1,
    c: int = 1,
) -> str:
    return f"""OPENQASM 2.0;
include "qelib1.inc";
qreg q[{q}];
creg c[{c}];
{quantum_before}
classical {{
{classical}
}}
{quantum_after}
"""


def full_qasm_from_ops(ops: list[str], q: int, c: int) -> str:
    return "\n".join(
        [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            f"qreg q[{q}];",
            f"creg c[{c}];",
            *ops,
        ]
    )


def run_assembly(assembly: str, measurements: dict[int, int]) -> dict[int, int]:
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    for index, value in measurements.items():
        emulator.set_register(f"x{10 + index}", value)
    return emulator.execute()


def used_cbits(source: str) -> list[int]:
    return sorted({int(index) for index in re.findall(r"c\[(\d+)\]", source)})


def compare_classical(classical: str, measurements: dict[int, int], c: int | None = None) -> str:
    bits = used_cbits(classical)
    max_cbit = max(bits + list(measurements.keys()), default=0)
    creg_size = c if c is not None else max(1, max_cbit + 1)
    measure_lines = "\n".join(f"measure q[{i}] -> c[{i}];" for i in range(creg_size))
    source = hybrid(classical, quantum_before=measure_lines, q=creg_size, c=creg_size)
    _, assembly = adapter.compile_hybrid(source)
    program = l3.parse_classical_program(classical)
    expected = l3.interpret_program(program, measurements)
    actual_state = run_assembly(assembly, measurements)
    actual = {
        idx: actual_state.get(f"x{idx}", 0)
        for idx in range(1, 10)
        if actual_state.get(f"x{idx}", 0) != 0
    }
    require(
        actual == expected,
        "classical mismatch\n"
        f"source={classical}\n"
        f"asm={assembly}\n"
        f"measurements={measurements}\n"
        f"expected={expected}\n"
        f"actual={actual}",
    )
    return assembly


def assert_classical_result(
    classical: str,
    measurements: dict[int, int],
    expected: dict[int, int],
    c: int | None = None,
) -> None:
    bits = used_cbits(classical)
    max_cbit = max(bits + list(measurements.keys()), default=0)
    creg_size = c if c is not None else max(1, max_cbit + 1)
    measure_lines = "\n".join(f"measure q[{i}] -> c[{i}];" for i in range(creg_size))
    source = hybrid(classical, quantum_before=measure_lines, q=creg_size, c=creg_size)
    _, assembly = adapter.compile_hybrid(source)
    actual_state = run_assembly(assembly, measurements)
    actual = {index: actual_state.get(f"x{index}", 0) for index in range(1, 10)}
    for index, value in expected.items():
        require(
            actual[index] == value,
            f"expected r{index}={value}, got {actual[index]}\nsource={classical}\nasm={assembly}",
        )
    compare_classical(classical, measurements, c=creg_size)


def compare_all_measurements(classical: str, c: int | None = None) -> int:
    bits = used_cbits(classical)
    combinations = 0
    for values in itertools.product((0, 1), repeat=len(bits)):
        compare_classical(classical, dict(zip(bits, values)), c=c)
        combinations += 1
    return combinations


def written_registers(assembly: str) -> set[int]:
    writes: set[int] = set()
    for raw_line in assembly.splitlines():
        line = raw_line.strip()
        if not line or line.endswith(":"):
            continue
        parts = line.replace(",", " ").split()
        if parts[0] in {"li", "add", "sub", "addi"} and len(parts) > 1:
            writes.add(int(parts[1][1:]))
    return writes


def expect_compile_error(source: str, message: str) -> None:
    try:
        adapter.compile_hybrid(source)
    except ValueError:
        return
    raise AssertionError(f"expected compile error did not happen: {message}")


def test_public_case() -> None:
    source = hybrid("if (c[0] == 1) { r1 = 7; } else { r1 = 3; }")
    quantum_ops, assembly = adapter.compile_hybrid(source)
    require(quantum_ops == ["measure q[0] -> c[0];"], "public quantum ops mismatch")
    require(run_assembly(assembly, {0: 0}).get("x1") == 3, "public c0=0 mismatch")
    require(run_assembly(assembly, {0: 1}).get("x1") == 7, "public c0=1 mismatch")


def test_handwritten_edges() -> tuple[int, int]:
    cases = [
        # EDGE 1: three sequential if/else blocks.
        "if (c[0] == 1) { r1 = 1; } else { r1 = 2; } "
        "if (c[1] == 1) { r2 = r1 + 3; } else { r2 = r1 - 3; } "
        "if (c[2] != 0) { r3 = r2 + r1; } else { r3 = r2 - r1; }",
        # EDGE 2: two-level nested if.
        "if (c[0] == 1) { if (c[1] == 1) { r1 = 11; } else { r1 = 10; } } else { r1 = 0; }",
        # EDGE 3: three-level nested if.
        "if (c[0] == 1) { if (c[1] == 1) { if (c[2] == 1) { r1 = 7; } else { r1 = 6; } } else { r1 = 5; } } else { r1 = 4; }",
        # EDGE 4: condition with both sides register.
        "r1 = 5; r2 = 5; if (r1 == r2) { r3 = 1; } else { r3 = 2; }",
        # EDGE 5: condition with both sides cbit.
        "if (c[0] != c[1]) { r1 = 9; } else { r1 = 8; }",
        # EDGE 6: register vs cbit.
        "r1 = c[0]; if (r1 == c[1]) { r2 = 3; } else { r2 = 4; }",
        # EDGE 7: negative result.
        "r1 = 3; r2 = 10; r3 = r1 - r2;",
        # EDGE 8: immediate - register.
        "r1 = 4; r3 = 10 - r1;",
        # EDGE 9: cbit arithmetic.
        "r1 = c[0] + r2; r2 = c[1] - r1;",
        # EDGE 10: r1..r9 written and read.
        "r1 = 1; r2 = r1 + 1; r3 = r2 + 1; r4 = r3 + 1; r5 = r4 + 1; "
        "r6 = r5 + 1; r7 = r6 + 1; r8 = r7 + 1; r9 = r8 + 1;",
        # EDGE 11: literal 0.
        "r1 = 0; if (r1 == 0) { r2 = 1; } else { r2 = 2; }",
        # EDGE 12: multiple measurement inputs and all combinations.
        "r1 = c[0]; r2 = c[1]; r3 = c[2]; r4 = c[3]; r5 = c[4];",
        # Extra immediate/register forms from the supported expression set.
        "r1 = 4; r2 = r1; r3 = c[0]; r4 = r1 + 3; r5 = 3 + r1; r6 = r1 + r2;",
        "r1 = 8; r2 = 2; r3 = r1 - 3; r4 = r1 - r2; r5 = c[0] - r1;",
        # Regression: destination aliases the right operand in immediate - register.
        "r2 = 5; r2 = 1 - r2;",
    ]
    combinations = 0
    for classical in cases:
        combinations += compare_all_measurements(classical)
    return len(cases), combinations


def test_arithmetic_conditions() -> tuple[int, int]:
    cases = [
        (
            """
r1 = 1;
r2 = 2;
r3 = 1;
r4 = 1;
if (r1 + r2 == r3 + r4 + 1) { r5 = 7; } else { r5 = 9; }
""",
            {},
            {5: 7},
        ),
        (
            """
r1 = 5;
r2 = 2;
r3 = 1;
if (r1 - r2 != r3 + 1) { r4 = 11; } else { r4 = 12; }
""",
            {},
            {4: 11},
        ),
        (
            """
r1 = 1;
if (c[0] + c[1] == r1 + 1) { r4 = 21; } else { r4 = 22; }
""",
            None,
            None,
        ),
        (
            """
r1 = 5;
r2 = 4;
r3 = 8;
if (r1 + r2 - c[0] == r3 + c[1] - 2) { r6 = 31; } else { r6 = 32; }
""",
            None,
            None,
        ),
        (
            """
r3 = 1;
if (1 - 1 != c[0] - r3 + 1 - 0) { r7 = 41; } else { r7 = 42; }
""",
            None,
            None,
        ),
        (
            """
r1 = 2;
r2 = 3;
if (r1 + r2 == 5) {
    if (c[0] + r1 != r2 - 1) { r8 = 51; } else { r8 = 52; }
} else {
    r8 = 53;
}
""",
            None,
            None,
        ),
    ]
    combinations = 0
    for classical, measurements, expected in cases:
        if measurements is None:
            combinations += compare_all_measurements(classical)
        else:
            assert_classical_result(classical, measurements, expected or {})
            combinations += 1
    return len(cases), combinations


def test_one_scratch_chain() -> None:
    assert_classical_result(
        "r2 = 1; r3 = 2; r4 = 3; r1 = r2 + r3 + r4;",
        {},
        {1: 6},
        c=21,
    )


def test_splitter_comments() -> int:
    prefix_comment = """// classical will appear below
OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
classical { r1 = 1; }
"""
    adapter.compile_hybrid(prefix_comment)

    suffix_comment = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
classical { r1 = 1; }
// classical finished
"""
    adapter.compile_hybrid(suffix_comment)

    comment_between = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
classical // begin block
{
  r1 = 1;
}
"""
    adapter.compile_hybrid(comment_between)

    fake_brace = """// classical { fake }
OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
classical { if (c[0] == 1) { r1 = 1; } else { r1 = 2; } }
"""
    adapter.compile_hybrid(fake_brace)

    string_keyword = """OPENQASM 2.0;
include "classical.inc";
qreg q[1];
creg c[1];
classical { r1 = 1; }
"""
    _, classical_source = l3.split_hybrid_qasm(string_keyword)
    require("r1 = 1" in classical_source, "classical keyword inside a string confused splitter")

    true_multiple = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
classical { r1 = 1; }
classical { r2 = 2; }
"""
    expect_compile_error(true_multiple, "true multiple classical blocks")
    return 6


def test_quantum_ops() -> int:
    cases = []
    cases.append(
        (
            hybrid(
                "r1 = c[0];",
                quantum_before="h q[0];\nmeasure q[0] -> c[0];",
                quantum_after="cx q[0], q[1];",
                q=2,
                c=2,
            ),
            ["h q[0];", "measure q[0] -> c[0];", "cx q[0], q[1];"],
        )
    )
    cases.append(
        (
            hybrid(
                "r1 = 1;",
                quantum_before="x q[0];\nh q[1];\nmeasure q[1] -> c[1];",
                quantum_after="swap q[0], q[1];\nmeasure q[0] -> c[0];",
                q=2,
                c=2,
            ),
            ["x q[0];", "h q[1];", "measure q[1] -> c[1];", "swap q[0], q[1];", "measure q[0] -> c[0];"],
        )
    )
    param_source = hybrid(
        "r1 = 1;",
        quantum_before="rz(pi/4) q[0];\nry(pi/2) q[1];\ncu1(pi/3) q[0], q[1];",
        q=2,
        c=1,
    )
    param_ops, _ = adapter.compile_hybrid(param_source)
    parsed = adapter._parse_qasm(full_qasm_from_ops(param_ops, q=2, c=1))
    gates = [op for op in parsed.ops if isinstance(op, adapter.GateOp)]
    require([gate.name for gate in gates] == ["rz", "ry", "cu1"], "parameter gate order changed")
    require(math.isclose(gates[0].params[0], math.pi / 4, rel_tol=1e-12), "rz parameter changed")
    require(math.isclose(gates[1].params[0], math.pi / 2, rel_tol=1e-12), "ry parameter changed")
    require(math.isclose(gates[2].params[0], math.pi / 3, rel_tol=1e-12), "cu1 parameter changed")
    cases.append((param_source, param_ops))
    cases.append(
        (
            hybrid(
                "r1 = c[2];",
                quantum_before="measure q[2] -> c[0];\nmeasure q[0] -> c[2];\nmeasure q[1] -> c[1];",
                q=3,
                c=3,
            ),
            ["measure q[2] -> c[0];", "measure q[0] -> c[2];", "measure q[1] -> c[1];"],
        )
    )
    whitelist_source = hybrid(
        "r1 = 1;",
        quantum_before=(
            "s q[0];\nsdg q[0];\nt q[1];\ntdg q[1];\n"
            "rz(pi/4) q[0];\nry(pi/2) q[1];\ncu1(pi/3) q[0], q[1];\n"
            "swap q[0], q[1];\nccx q[0], q[1], q[2];"
        ),
        q=3,
        c=1,
    )
    whitelist_ops, _ = adapter.compile_hybrid(whitelist_source)
    adapter._parse_qasm(full_qasm_from_ops(whitelist_ops, q=3, c=1))
    require(
        [op.split()[0].split("(")[0] for op in whitelist_ops]
        == ["s", "sdg", "t", "tdg", "rz", "ry", "cu1", "swap", "ccx"],
        "whitelist gate order changed",
    )
    cases.append((whitelist_source, whitelist_ops))

    for source, expected in cases:
        quantum_ops, _ = adapter.compile_hybrid(source)
        require(quantum_ops == expected, f"quantum ops mismatch\nexpected={expected}\nactual={quantum_ops}")
    return len(cases)


def test_scratch_edges() -> int:
    checks = [
        ("if (c[9] == 1) { r1 = 1; } else { r1 = 0; }", 10, set(range(10, 20))),
        ("if (c[19] == 1) { r1 = 1; } else { r1 = 0; }", 20, set(range(10, 30))),
        ("if (c[20] == 1) { r1 = 1; } else { r1 = 0; }", 21, set(range(10, 31))),
    ]
    for classical, creg_size, protected in checks:
        assembly = compare_classical(classical, {creg_size - 1: 1}, c=creg_size)
        require(
            written_registers(assembly).isdisjoint(protected),
            f"scratch register overwrote protected c register\nc={creg_size}\nasm={assembly}",
        )

    expect_compile_error(
        hybrid("if (r1 + r2 == r3) { r4 = 1; } else { r4 = 2; }", quantum_before="measure q[0] -> c[0];", q=22, c=22),
        "no scratch registers available",
    )
    expect_compile_error(
        hybrid("r1 = c[22];", quantum_before="measure q[22] -> c[22];", q=23, c=23),
        "c[22] maps beyond x31",
    )
    return len(checks) + 2


def test_invalid_inputs() -> int:
    invalid_sources = [
        hybrid("r10 = 1;"),
        hybrid("r1 = c[-1];"),
        hybrid("r1 = 1 * 2;"),
        hybrid("if (r1 = 3) { r2 = 1; } else { r2 = 2; }"),
        hybrid("r1 = 1"),
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
classical {
if (c[0] == 1 { r1 = 1; } else { r1 = 2; }
}
""",
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
classical {
if (c[0] == 1) { r1 = 1; } else { r1 = 2; }
""",
        """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
classical { r1 = 1; }
classical { r2 = 2; }
""",
    ]
    for index, source in enumerate(invalid_sources, start=1):
        expect_compile_error(source, f"invalid parser case {index}")
    return len(invalid_sources)


def literal(rng: random.Random) -> str:
    if rng.random() < 0.65:
        return str(rng.choice([0, 1, 2, 7, 10, 20]))
    return str(rng.randint(0, 100))


def rand_reg(rng: random.Random) -> str:
    return f"r{rng.randint(1, 9)}"


def rand_cbit(rng: random.Random) -> str:
    if rng.random() < 0.04:
        return f"c[{rng.choice([10, 19, 20])}]"
    return f"c[{rng.randint(0, 4)}]"


def rand_atom(rng: random.Random) -> str:
    choice = rng.random()
    if choice < 0.35:
        return literal(rng)
    if choice < 0.68:
        return rand_reg(rng)
    return rand_cbit(rng)


def rand_expr(rng: random.Random) -> str:
    term_count = rng.choices([1, 2, 3, 4, 5], weights=[35, 30, 18, 11, 6], k=1)[0]
    expr = rand_atom(rng)
    for _ in range(term_count - 1):
        expr = f"{expr} {rng.choice(['+', '-'])} {rand_atom(rng)}"
    return expr


def rand_condition(rng: random.Random) -> str:
    op = rng.choice(["==", "!="])
    if rng.random() < 0.6:
        return f"{rand_expr(rng)} {op} {rand_expr(rng)}"
    templates = [
        lambda: f"{rand_cbit(rng)} {op} 1",
        lambda: f"{rand_cbit(rng)} {op} {rand_cbit(rng)}",
        lambda: f"{rand_reg(rng)} {op} {rand_reg(rng)}",
        lambda: f"{rand_reg(rng)} {op} {literal(rng)}",
        lambda: f"{rand_reg(rng)} {op} {rand_cbit(rng)}",
    ]
    return rng.choice(templates)()


def rand_assignment(rng: random.Random) -> str:
    return f"{rand_reg(rng)} = {rand_expr(rng)};"


def rand_statement(rng: random.Random, depth: int, if_budget: list[int]) -> str:
    if depth < 3 and if_budget[0] > 0 and rng.random() < 0.38:
        if_budget[0] -= 1
        then_count = rng.randint(1, 3)
        else_count = rng.randint(1, 3)
        then_body = " ".join(rand_statement(rng, depth + 1, if_budget) for _ in range(then_count))
        else_body = " ".join(rand_statement(rng, depth + 1, if_budget) for _ in range(else_count))
        return f"if ({rand_condition(rng)}) {{ {then_body} }} else {{ {else_body} }}"
    return rand_assignment(rng)


def rand_program(rng: random.Random) -> str:
    if_budget = [rng.randint(0, 4)]
    statements = [rand_statement(rng, 0, if_budget) for _ in range(rng.randint(1, 10))]
    return "\n".join(statements)


def run_random_differential() -> tuple[int, int]:
    total_programs = 0
    total_combinations = 0
    for seed in RANDOM_SEEDS:
        rng = random.Random(seed)
        for program_index in range(PROGRAMS_PER_SEED):
            classical = rand_program(rng)
            bits = used_cbits(classical)
            if len(bits) > 7:
                continue
            creg_size = max(1, max(bits, default=0) + 1)
            try:
                combinations = compare_all_measurements(classical, c=creg_size)
            except Exception as exc:
                raise AssertionError(
                    f"random differential failure seed={seed} program_index={program_index} creg_size={creg_size}\n"
                    f"classical:\n{classical}\n{type(exc).__name__}: {exc}"
                ) from exc
            total_programs += 1
            total_combinations += combinations
    return total_programs, total_combinations


def main() -> int:
    print("Running L3 hidden-test hardening checks...")

    test_public_case()
    print("[PASS] public evaluator equivalent")

    edge_count, edge_combinations = test_handwritten_edges()
    print(f"[PASS] handwritten edge cases={edge_count} combinations={edge_combinations}")

    arithmetic_count, arithmetic_combinations = test_arithmetic_conditions()
    print(f"[PASS] arithmetic-condition regressions={arithmetic_count} combinations={arithmetic_combinations}")

    test_one_scratch_chain()
    print("[PASS] one-scratch chain regression")

    splitter_cases = test_splitter_comments()
    print(f"[PASS] splitter comment/string regressions={splitter_cases}")

    quantum_cases = test_quantum_ops()
    print(f"[PASS] quantum_ops cases={quantum_cases}")

    scratch_cases = test_scratch_edges()
    print(f"[PASS] scratch edge cases={scratch_cases}")

    invalid_cases = test_invalid_inputs()
    print(f"[PASS] invalid parser cases={invalid_cases}")

    total_programs, total_combinations = run_random_differential()
    print(
        "[PASS] randomized differential "
        f"seeds={RANDOM_SEEDS} programs={total_programs} combinations={total_combinations}"
    )

    print("All L3 local checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
