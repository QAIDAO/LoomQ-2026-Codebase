#!/usr/bin/env python3
"""L3 fuzz self-test: randomized Hybrid-QASM against a reference interpreter.

Generates grammar-valid classical blocks (nested if/else, multi-cbit
conditions, chained +/- expressions, random registers/constants), compiles
them to RISC-V, then exhaustively injects every measurement-bit
combination into the official TinyRISCVEmulator and compares ALL r1..r9
final values with a direct Python interpreter over the same AST.

This mirrors the organizer's randomized validation (register final states
must match 100%) at larger scale than the fixed selftest_l3 cases.
Exit code 0 = all cases pass.
"""

import itertools
import random
import sys

try:
    from .hybrid_parser import split_hybrid, parse_classic, Assign, If, Cond
    from .riscv_emulator import TinyRISCVEmulator
    from . import adapter
except ImportError:  # standalone-module fallback
    from hybrid_parser import split_hybrid, parse_classic, Assign, If, Cond
    from riscv_emulator import TinyRISCVEmulator
    import adapter

NUM_CASES = 150
MAX_CBITS = 5
MAX_DEPTH = 5
SEED = 20260807


# --- Reference interpreter (mirrors selftest_l3.py) --------------------------

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


# --- Random grammar-valid classical block generator ---------------------------

def gen_operand(rng, n_cbits):
    choice = rng.random()
    if choice < 0.4:
        return ("imm", rng.randint(-50, 500))
    if choice < 0.75:
        return ("reg", rng.randint(1, 9))
    return ("cbit", rng.randrange(n_cbits))


def gen_expr(rng, n_cbits):
    expr = [("=", gen_operand(rng, n_cbits))]
    for _ in range(rng.randint(0, 3)):
        expr.append((rng.choice(("+", "-")), gen_operand(rng, n_cbits)))
    return expr


def gen_cond(rng, n_cbits):
    return Cond(
        left=gen_operand(rng, n_cbits),
        op=rng.choice(("==", "!=")),
        right=gen_operand(rng, n_cbits),
    )


def gen_block(rng, n_cbits, depth):
    stmts = []
    for _ in range(rng.randint(1, 4)):
        if depth <= 0 or rng.random() < 0.6:
            stmts.append(Assign(target=rng.randint(1, 9), expr=gen_expr(rng, n_cbits)))
        else:
            stmts.append(gen_if(rng, n_cbits, depth - 1))
    return stmts


def gen_if(rng, n_cbits, depth):
    cond = gen_cond(rng, n_cbits)
    then_body = gen_block(rng, n_cbits, depth)
    else_body = gen_block(rng, n_cbits, depth) if rng.random() < 0.7 else None
    return If(cond=cond, then_body=then_body, else_body=else_body)


def render(stmts, indent=0):
    pad = "  " * indent
    lines = []
    for stmt in stmts:
        if isinstance(stmt, Assign):
            expr = " ".join(
                ("%s %s" % (op, _fmt_op(operand))) for op, operand in stmt.expr
            )
            lines.append("%sr%d = %s;" % (pad, stmt.target, expr[2:]))
        elif isinstance(stmt, If):
            lines.append(
                "%sif (%s %s %s) {" % (
                    pad,
                    _fmt_op(stmt.cond.left), stmt.cond.op, _fmt_op(stmt.cond.right),
                )
            )
            lines.extend(render(stmt.then_body, indent + 1))
            if stmt.else_body is not None:
                lines.append("%s} else {" % pad)
                lines.extend(render(stmt.else_body, indent + 1))
            lines.append("%s}" % pad)
    return lines


def _fmt_op(operand):
    kind, value = operand
    if kind == "imm":
        return str(value)
    if kind == "reg":
        return "r%d" % value
    return "c[%d]" % value


def build_hybrid(num_cbits, classic_lines):
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % max(1, num_cbits),
        "creg c[%d];" % num_cbits,
    ]
    for k in range(num_cbits):
        lines.append("measure q[%d] -> c[%d];" % (k, k))
    lines.append("classical {")
    lines.extend(classic_lines)
    lines.append("}")
    return "\n".join(lines) + "\n"


def run_case(index, num_cbits, stmts):
    qasm = build_hybrid(num_cbits, render(stmts))
    quantum_ops, assembly = adapter.compile_hybrid(qasm)
    if not isinstance(quantum_ops, list) or not assembly.strip():
        raise AssertionError("invalid compile_hybrid contract shape")
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
                "case%d cbits=%s r%d: emulator=%d reference=%d\nqasm:\n%s\nasm:\n%s"
                % (index, values, reg_index, got, want, qasm, assembly)
            )


def main() -> int:
    rng = random.Random(SEED)
    failures = 0
    for index in range(NUM_CASES):
        num_cbits = rng.randrange(1, MAX_CBITS + 1)
        try:
            stmts = gen_block(rng, num_cbits, MAX_DEPTH)
            run_case(index, num_cbits, stmts)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print("[FAIL] fuzz:case%d - %s: %s" % (index, type(exc).__name__, exc))
    if failures:
        print("L3 fuzz: %d/%d failed" % (failures, NUM_CASES), file=sys.stderr)
        return 1
    print("L3 fuzz: all %d randomized cases passed (exhaustive injection)" % NUM_CASES)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover - top-level guard
        print("L3 fuzz failed: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(1)
