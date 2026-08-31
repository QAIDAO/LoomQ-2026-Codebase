#!/usr/bin/env python3
"""Differential tests for the L3 Hybrid-QASM compiler.

Two independent properties are checked, mirroring how the official grader works
(randomised programs, every measurement-value combination injected):

1. **Parser round-trip** - a randomly generated AST is rendered to source text,
   parsed back, and compared for structural equality.
2. **Codegen equivalence** - the emitted assembly is executed on the official
   ``TinyRISCVEmulator`` for all measurement combinations and compared against a
   reference interpreter that never touches the code generator.
"""

from __future__ import annotations

import itertools
import os
import random
import sys
from typing import Dict, List, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loomq.hybrid import (  # noqa: E402
    Assign,
    BinOp,
    CBitRef,
    Compare,
    If,
    Literal,
    Stmt,
    VarRef,
    compile_hybrid,
    interpret_classical,
    parse_hybrid,
)
from riscv_emulator import TinyRISCVEmulator  # noqa: E402

MAX_VAR = 9


# ---------------------------------------------------------------------------
# Rendering an AST back to Hybrid-QASM source
# ---------------------------------------------------------------------------


def render_expr(expr, parens: bool = True, nested: bool = False) -> str:
    """Render an expression.

    ``parens=True`` brackets nested arithmetic so the text maps back to exactly
    one tree, which is what the AST round-trip check needs. ``parens=False``
    produces flat chains like ``r1 + 5 - r2``, matching how the grader writes
    programs; those only round-trip up to left-associativity.
    """
    if isinstance(expr, Literal):
        return str(expr.value)
    if isinstance(expr, VarRef):
        return f"r{expr.index}"
    if isinstance(expr, CBitRef):
        return f"{expr.name}[{expr.index}]"
    if isinstance(expr, BinOp):
        left = render_expr(expr.left, parens, nested=True)
        right = render_expr(expr.right, parens, nested=True)
        text = f"{left} {expr.op} {right}"
        return f"({text})" if parens and nested else text
    raise TypeError(expr)


def render_stmts(body: Sequence[Stmt], indent: int = 1, parens: bool = True) -> str:
    pad = "  " * indent
    lines: List[str] = []
    for stmt in body:
        if isinstance(stmt, Assign):
            lines.append(f"{pad}r{stmt.target} = {render_expr(stmt.value, parens)};")
        elif isinstance(stmt, If):
            cond = stmt.cond
            left = render_expr(cond.left, parens)
            right = render_expr(cond.right, parens)
            lines.append(f"{pad}if ({left} {cond.op} {right}) {{")
            lines.append(render_stmts(stmt.then_body, indent + 1, parens))
            if stmt.else_body:
                lines.append(f"{pad}}} else {{")
                lines.append(render_stmts(stmt.else_body, indent + 1, parens))
            lines.append(f"{pad}}}")
        else:
            raise TypeError(stmt)
    return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------------------
# Random program generation
# ---------------------------------------------------------------------------


def random_expr(
    rng: random.Random, n_cbits: int, depth: int = 0, allow_negative: bool = False
):
    choices = ["lit", "var"]
    if n_cbits:
        choices.append("cbit")
    if depth < 2:
        choices.append("binop")
    kind = rng.choice(choices)
    if kind == "lit":
        # A bare negative literal renders as unary minus, which parses to
        # ``0 - n``; keep it out of the tree when AST equality is being checked.
        return Literal(rng.randint(-20 if allow_negative else 0, 120))
    if kind == "var":
        return VarRef(rng.randint(1, MAX_VAR))
    if kind == "cbit":
        slot = rng.randrange(n_cbits)
        return CBitRef(name="c", index=slot, slot=slot)
    return BinOp(
        op=rng.choice(["+", "-"]),
        left=random_expr(rng, n_cbits, depth + 1, allow_negative),
        right=random_expr(rng, n_cbits, depth + 1, allow_negative),
    )


def random_body(
    rng: random.Random, n_cbits: int, depth: int = 0, allow_negative: bool = False
) -> Tuple[Stmt, ...]:
    body: List[Stmt] = []
    for _ in range(rng.randint(1, 3)):
        if depth < 2 and rng.random() < 0.45:
            cond = Compare(
                op=rng.choice(["==", "!="]),
                left=random_expr(rng, n_cbits, allow_negative=allow_negative),
                right=random_expr(rng, n_cbits, allow_negative=allow_negative),
            )
            then_body = random_body(rng, n_cbits, depth + 1, allow_negative)
            else_body = (
                random_body(rng, n_cbits, depth + 1, allow_negative)
                if rng.random() < 0.6
                else ()
            )
            body.append(If(cond=cond, then_body=then_body, else_body=else_body))
        else:
            body.append(
                Assign(
                    target=rng.randint(1, MAX_VAR),
                    value=random_expr(rng, n_cbits, allow_negative=allow_negative),
                )
            )
    return tuple(body)


def build_source(
    body: Sequence[Stmt], n_qubits: int, n_cbits: int, parens: bool = True
) -> str:
    measures = "\n".join(
        f"measure q[{index}] -> c[{index}];" for index in range(n_cbits)
    )
    gates = "\n".join(f"h q[{index}];" for index in range(n_qubits))
    return (
        'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
        f"qreg q[{n_qubits}];\ncreg c[{n_cbits}];\n"
        f"{gates}\n{measures}\n"
        "classical {\n" + render_stmts(body, parens=parens) + "\n}\n"
    )


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def run_assembly(assembly: str, cbits: Dict[int, int]) -> Dict[int, int]:
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    # Mirrors the grader: measurement values are injected after the reset.
    for slot, value in cbits.items():
        emulator.set_register(f"x{10 + slot}", value)
    state = emulator.execute()
    return {index: state.get(f"x{index}", 0) for index in range(1, MAX_VAR + 1)}


def check_case(
    source: str,
    expected_ast: Sequence[Stmt],
    n_cbits: int,
    check_ast: bool = True,
) -> None:
    quantum_ops, parsed_ast, parsed_cbits = parse_hybrid(source)
    assert parsed_cbits == n_cbits, f"cbit count mismatch: {parsed_cbits} != {n_cbits}"
    if check_ast:
        assert tuple(parsed_ast) == tuple(expected_ast), (
            "parser round-trip mismatch\n"
            f"source:\n{source}\nparsed:\n{parsed_ast}\nexpected:\n{expected_ast}"
        )
    assert all(op.endswith(";") for op in quantum_ops), quantum_ops

    _, assembly = compile_hybrid(source)
    for combo in itertools.product((0, 1), repeat=n_cbits):
        cbits = {slot: value for slot, value in enumerate(combo)}
        actual = run_assembly(assembly, cbits)
        expected = interpret_classical(parsed_ast, cbits)
        assert actual == expected, (
            f"codegen mismatch for cbits={combo}\nsource:\n{source}\n"
            f"assembly:\n{assembly}\nemulator={actual}\nreference={expected}"
        )


def test_public_evaluator_case() -> None:
    source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
classical { if (c[0] == 1) { r1 = 7; } else { r1 = 3; } }
"""
    quantum_ops, assembly = compile_hybrid(source)
    assert quantum_ops == ["measure q[0] -> c[0];"], quantum_ops
    for measured, expected in ((0, 3), (1, 7)):
        assert run_assembly(assembly, {0: measured})[1] == expected


def test_spec_example() -> None:
    source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q[0] -> c[0];
classical {                 // measurement c[0] is injected into x10
  if (c[0] == 1) {
    r1 = 100;
  } else {
    r1 = 10;
  }
  r1 = r1 + 5;
}
cx q[0], q[1];
"""
    quantum_ops, assembly = compile_hybrid(source)
    assert quantum_ops == [
        "h q[0];",
        "measure q[0] -> c[0];",
        "cx q[0], q[1];",
    ], quantum_ops
    assert run_assembly(assembly, {0: 1})[1] == 105
    assert run_assembly(assembly, {0: 0})[1] == 15


def test_aliasing_assignment() -> None:
    """``r1 = r2 + r1`` must not read a half-overwritten target register."""
    source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
classical {
  r1 = 4;
  r2 = 10;
  r1 = r2 - r1;
  r2 = r1 + r2;
}
"""
    _, assembly = compile_hybrid(source)
    state = run_assembly(assembly, {0: 0})
    assert state[1] == 6, state
    assert state[2] == 16, state


def test_measurement_register_never_written() -> None:
    source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
classical {
  r1 = c[0] + c[1];
  if (c[2] != 0) { r1 = r1 + 50; }
}
"""
    _, assembly = compile_hybrid(source)
    for line in assembly.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.endswith(":"):
            continue
        operands = stripped.replace(",", " ").split()
        if operands[0] in {"li", "add", "sub", "addi"}:
            assert operands[1] not in {"x10", "x11", "x12"}, (
                f"generated code writes a measurement register: {stripped}"
            )
    for combo in itertools.product((0, 1), repeat=3):
        expected = combo[0] + combo[1] + (50 if combo[2] else 0)
        cbits = {slot: value for slot, value in enumerate(combo)}
        assert run_assembly(assembly, cbits)[1] == expected, combo


def test_negative_literals_and_unary_minus() -> None:
    source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
classical {
  r1 = -12;
  r2 = 5 - -7;
  if (r1 != -12) { r3 = 1; } else { r3 = -(4 - 9); }
}
"""
    _, assembly = compile_hybrid(source)
    state = run_assembly(assembly, {0: 0})
    assert state[1] == -12, state
    assert state[2] == 12, state
    assert state[3] == 5, state


def test_randomized_differential(count: int = 300, seed: int = 20260801) -> None:
    """Parenthesised programs: parser round-trip plus codegen equivalence."""
    rng = random.Random(seed)
    for index in range(count):
        n_cbits = rng.randint(1, 4)
        n_qubits = max(n_cbits, rng.randint(1, 4))
        body = random_body(rng, n_cbits)
        source = build_source(body, n_qubits=n_qubits, n_cbits=n_cbits, parens=True)
        try:
            check_case(source, body, n_cbits, check_ast=True)
        except AssertionError as exc:
            raise AssertionError(f"random case #{index} (seed={seed}) failed:\n{exc}")


def test_randomized_flat_chains(count: int = 300, seed: int = 987654321) -> None:
    """Unparenthesised chains like the grader writes; semantics only."""
    rng = random.Random(seed)
    for index in range(count):
        n_cbits = rng.randint(1, 4)
        n_qubits = max(n_cbits, rng.randint(1, 4))
        body = random_body(rng, n_cbits, allow_negative=True)
        source = build_source(body, n_qubits=n_qubits, n_cbits=n_cbits, parens=False)
        try:
            check_case(source, body, n_cbits, check_ast=False)
        except AssertionError as exc:
            raise AssertionError(f"flat case #{index} (seed={seed}) failed:\n{exc}")


def main() -> int:
    tests = [
        test_public_evaluator_case,
        test_spec_example,
        test_aliasing_assignment,
        test_measurement_register_never_written,
        test_negative_literals_and_unary_minus,
        test_randomized_differential,
        test_randomized_flat_chains,
    ]
    failures = 0
    for test in tests:
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
