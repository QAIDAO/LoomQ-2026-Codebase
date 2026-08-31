#!/usr/bin/env python3
"""L3 self-test: Hybrid-QASM -> RISC-V against a reference interpreter.

For each case we compile the classical block, then exhaustively inject
every measurement-bit combination into the official TinyRISCVEmulator
(c[k] -> x10+k) and compare all r1..r9 final values with a direct Python
interpreter over the same AST. This mirrors the organizer's randomized
validation (100% register-state correctness) without needing their runner.

Exit code 0 = all cases pass.
"""

import itertools
import sys

try:
    from .hybrid_parser import split_hybrid, parse_classic, Assign, If
    from .riscv_codegen import compile_classic_block
    from .riscv_emulator import TinyRISCVEmulator
    from . import adapter
except ImportError:  # standalone-module fallback
    from hybrid_parser import split_hybrid, parse_classic, Assign, If
    from riscv_codegen import compile_classic_block
    from riscv_emulator import TinyRISCVEmulator
    import adapter


# --- Reference interpreter over the same AST ------------------------------

def _operand_value(operand, cbits, regs):
    kind, value = operand
    if kind == "imm":
        return value
    if kind == "reg":
        return regs.get(value, 0)
    if kind == "cbit":
        return cbits.get(value, 0)
    raise ValueError("unknown operand %r" % (operand,))


def _eval_expr(expr, cbits, regs):
    value = _operand_value(expr[0][1], cbits, regs)
    for op, operand in expr[1:]:
        if op == "+":
            value += _operand_value(operand, cbits, regs)
        elif op == "-":
            value -= _operand_value(operand, cbits, regs)
    return value


def eval_ast(stmts, cbits, regs):
    for stmt in stmts:
        if isinstance(stmt, Assign):
            regs[stmt.target] = _eval_expr(stmt.expr, cbits, regs)
        elif isinstance(stmt, If):
            left = _operand_value(stmt.cond.left, cbits, regs)
            right = _operand_value(stmt.cond.right, cbits, regs)
            taken = left == right if stmt.cond.op == "==" else left != right
            body = stmt.then_body if taken else (stmt.else_body or [])
            eval_ast(body, cbits, regs)


# --- Test cases --------------------------------------------------------------

def _hybrid(num_cbits, classic_block, extra_quantum=""):
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % max(1, num_cbits),
        "creg c[%d];" % num_cbits,
    ]
    for k in range(num_cbits):
        lines.append("measure q[%d] -> c[%d];" % (k, k))
    if extra_quantum:
        lines.append(extra_quantum)
    lines.append("classical { " + classic_block + " }")
    return "\n".join(lines) + "\n"


CASES = [
    # (classic block, num_cbits)
    ("if (c[0] == 1) { r1 = 7; } else { r1 = 3; }", 1),
    ("r1 = 5; r2 = r1 + 3;", 0),
    ("if (c[0] == 0) { r1 = 100; } else { r1 = 200; } r1 = r1 + 5;", 1),
    (
        "if (c[0] == 1) { if (c[1] == 1) { r1 = 1; } else { r1 = 2; } } "
        "else { r1 = 3; }",
        2,
    ),
    ("r1 = 10; r2 = 50; r3 = r2 - r1; r4 = r3 + 1;", 0),
    ("r1 = 5; if (r1 == 5) { r2 = 1; } else { r2 = 0; }", 1),
    ("if (c[0] != 0) { r1 = 9; } if (c[1] == 1) { r2 = r1 + 1; } else { r2 = 0; }", 2),
    ("r9 = 11; r1 = r9 - 3; r2 = r1 + r9;", 0),
    (
        "if (c[2] == 1) { r1 = 42; r2 = 43; } else { r1 = 24; } r3 = r1 + r2;",
        3,
    ),
    ("if (c[0] == 0) { r1 = 1; } else { r1 = 2; } if (c[0] == 0) { r2 = r1 + 10; }", 1),
]


def run_case(classic: str, num_cbits: int) -> None:
    qasm = _hybrid(num_cbits, classic)
    quantum_ops, assembly = adapter.compile_hybrid(qasm)
    if not isinstance(quantum_ops, list) or not assembly.strip():
        raise AssertionError("compile_hybrid returned an invalid contract shape")
    stmts = parse_classic(split_hybrid(qasm).classic_text)

    for values in itertools.product((0, 1), repeat=num_cbits):
        cbits = {k: values[k] for k in range(num_cbits)}
        expected = {}
        eval_ast(stmts, cbits, expected)

        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        for k, value in cbits.items():
            emulator.set_register("x%d" % (10 + k), value)
        state = emulator.execute()

        for reg_index in range(1, 10):
            want = expected.get(reg_index, 0)
            got = state.get("x%d" % reg_index, 0)
            assert got == want, (
                "cbits=%s r%d: emulator=%d reference=%d\nasm:\n%s"
                % (values, reg_index, got, want, assembly)
            )


def main() -> int:
    failures = 0
    for index, (classic, num_cbits) in enumerate(CASES):
        try:
            run_case(classic, num_cbits)
            print("[PASS] l3:case%d (cbits=%d, injections=2^%d)" % (index, num_cbits, num_cbits))
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print("[FAIL] l3:case%d - %s: %s" % (index, type(exc).__name__, exc))
    if failures:
        print("L3 self-test: %d failure(s)" % failures, file=sys.stderr)
        return 1
    print("L3 self-test: all %d cases passed (exhaustive injection)" % len(CASES))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover - top-level guard
        print("L3 self-test failed: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(1)
