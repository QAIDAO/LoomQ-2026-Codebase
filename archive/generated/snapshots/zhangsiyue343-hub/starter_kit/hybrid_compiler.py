#!/usr/bin/env python3
"""L3: Hybrid-QASM -> (quantum ops, RISC-V assembly).

The hybrid source is parsed by the SAME front-end as ordinary QASM —
`classical { ... }` blocks are just statements in the grammar, so no regex
splitting and any number of blocks interleaved with gates is accepted.

Classical statements lower to riscv_model instruction objects through a
declarative rule table: expressions fold at compile time (constants never
reach the CPU), each remaining shape maps to exactly one addressing form.
A reference interpreter mirrors the AST semantics; `verify_hybrid` proves
compiled output equals interpreted semantics for EVERY measurement injection.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable

try:
    from .gates import GATES
    from .ir import (Assign, Binary, BitRef, ClassicalBlock, Condition,
                     IfBlock, Num, RegRef, Unary)
    from .parser import parse_source
    from .riscv_model import (Add, Addi, Beq, Bne, Instruction, Jmp, Label,
                              Li, Sub, execute, link, parse_program,
                              render_program)
    from .targets import format_decimal
except ImportError:
    from gates import GATES
    from ir import (Assign, Binary, BitRef, ClassicalBlock, Condition,
                    IfBlock, Num, RegRef, Unary)
    from parser import parse_source
    from riscv_model import (Add, Addi, Beq, Bne, Instruction, Jmp, Label,
                             Li, Sub, execute, link, parse_program,
                             render_program)
    from targets import format_decimal

SCRATCH = "x20"
REG_BASE = 1            # r1..r9  -> x1..x9
CBIT_BASE = 10          # c[k]    -> x10+k


class HybridError(ValueError):
    pass


# --------------------------------------------------------------------------
# expression folding: Expr tree -> ('const', v) | ('reg', n) | (op, l, r)
# --------------------------------------------------------------------------

def _fold(expr) -> tuple:
    if isinstance(expr, Num):
        value = expr.value
        if value != int(value):
            raise HybridError("classical literals must be integers")
        return ("const", int(value))
    if isinstance(expr, RegRef):
        return ("reg", expr.index)
    if isinstance(expr, Unary):
        operand = _fold(expr.operand)
        if operand[0] != "const":
            raise HybridError("unary %s needs a constant operand" % expr.op)
        return ("const", operand[1] if expr.op == "+" else -operand[1])
    if isinstance(expr, Binary):
        left, right = _fold(expr.left), _fold(expr.right)
        if left[0] == "const" and right[0] == "const":
            folded = left[1] + right[1] if expr.op == "+" else left[1] - right[1]
            return ("const", folded)
        return (expr.op, left, right)
    raise HybridError("unsupported classical expression node %r" % (expr,))


# --------------------------------------------------------------------------
# statement lowering: AST -> instruction list (declarative rules)
# --------------------------------------------------------------------------

@dataclass
class _Lowering:
    out: list = None
    counter: int = 0

    def __post_init__(self):
        if self.out is None:
            self.out = []

    def fresh_label(self, hint: str) -> str:
        name = "L%d_%s" % (self.counter, hint)
        self.counter += 1
        return name

    # -- assignment ---------------------------------------------------------

    def assign(self, register: int, folded: tuple) -> None:
        rd = "x%d" % register
        kind = folded[0]
        if kind == "const":
            self.out.append(Li(rd, folded[1]))
        elif kind == "reg":
            self.out.append(Add(rd, "x%d" % folded[1], "x0"))
        elif kind == "+":
            lhs, rhs = folded[1], folded[2]
            if lhs[0] == "reg" and rhs[0] == "reg":
                self.out.append(Add(rd, "x%d" % lhs[1], "x%d" % rhs[1]))
            elif rhs[0] == "const":                      # reg + const
                self.out.append(Addi(rd, "x%d" % lhs[1], rhs[1]))
            else:                                        # const + reg
                self._load_scratch(lhs[1])
                self.out.append(Add(rd, SCRATCH, "x%d" % rhs[1]))
        elif kind == "-":
            lhs, rhs = folded[1], folded[2]
            if lhs[0] == "reg" and rhs[0] == "reg":
                self.out.append(Sub(rd, "x%d" % lhs[1], "x%d" % rhs[1]))
            elif rhs[0] == "const":                      # reg - const
                self.out.append(Addi(rd, "x%d" % lhs[1], -rhs[1]))
            else:                                        # const - reg
                self._load_scratch(lhs[1])
                self.out.append(Sub(rd, SCRATCH, "x%d" % rhs[1]))
        else:
            raise HybridError("cannot lower expression %r" % (folded,))

    def _load_scratch(self, const_value: int) -> None:
        self.out.append(Li(SCRATCH, const_value))

    # -- conditionals ---------------------------------------------------------

    def if_block(self, stmt: IfBlock) -> None:
        cond = stmt.cond
        creg = "x%d" % (CBIT_BASE + cond.cbit.index)
        else_label = self.fresh_label("ELSE")
        end_label = self.fresh_label("END")
        branch = Bne if cond.comparator == "==" else Beq
        self.out.append(Li(SCRATCH, cond.literal))
        self.out.append(branch(creg, SCRATCH, else_label))
        self.statements(stmt.then_body)
        if stmt.else_body:
            self.out.append(Jmp(end_label))
            self.out.append(Label(else_label))
            self.statements(stmt.else_body)
            self.out.append(Label(end_label))
        else:
            self.out.append(Label(else_label))

    def statements(self, stmts: Iterable) -> None:
        for stmt in stmts:
            if isinstance(stmt, Assign):
                self.assign(stmt.register, _fold(stmt.value))
            elif isinstance(stmt, IfBlock):
                self.if_block(stmt)
            else:
                raise HybridError("unknown classical statement %r" % (stmt,))


# --------------------------------------------------------------------------
# reference interpreter (semantics mirror)
# --------------------------------------------------------------------------

def interpret_classical(stmts: tuple, cvalues: dict[int, int]) -> dict[int, int]:
    regs = {i: 0 for i in range(REG_BASE, REG_BASE + 9)}

    def eval_value(folded) -> int:
        if folded[0] == "const":
            return folded[1]
        if folded[0] == "reg":
            return regs[folded[1]]
        left, right = eval_value(folded[1]), eval_value(folded[2])
        return left + right if folded[0] == "+" else left - right

    def run(block) -> None:
        for stmt in block:
            if isinstance(stmt, Assign):
                regs[stmt.register] = eval_value(_fold(stmt.value))
            elif isinstance(stmt, IfBlock):
                observed = cvalues.get(stmt.cond.cbit.index, 0)
                holds = (observed == stmt.cond.literal if stmt.cond.comparator == "=="
                         else observed != stmt.cond.literal)
                run(stmt.then_body if holds else stmt.else_body)

    run(stmts)
    return regs


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------

def _quantum_op_strings(program) -> list[str]:
    """Canonical OriginIR-style op list for evaluator semantic checks."""
    names = {name: defn.dialect["originir"] for name, defn in GATES.items()}
    try:
        from .ir import lower as _lower
    except ImportError:
        from ir import lower as _lower
    circuit = _lower(program)
    ops = []
    for gate, params, qubits in circuit.ops:
        head = names[gate]
        if params:
            head += "(%s)" % ",".join(format_decimal(p) for p in params)
        ops.append("%s %s" % (head, ", ".join("q[%d]" % q for q in qubits)))
    measures = circuit.measures or [(i, i) for i in range(circuit.n_qubits)]
    ops.extend("MEASURE q[%d], c[%d]" % m for m in measures)
    return ops


def compile_hybrid(source: str) -> tuple[list[str], str]:
    """Contract entry point: quantum op list + RISC-V assembly text."""
    program = parse_source(source, GATES)
    blocks = program.classical_blocks()
    lowering = _Lowering()
    for block in blocks:
        lowering.statements(block.body)
    instructions = tuple(lowering.out)
    assembly = render_program(instructions) if instructions else ""
    return _quantum_op_strings(program), assembly


def referenced_cbits(stmts: Iterable) -> set[int]:
    found = set()
    for stmt in stmts:
        if isinstance(stmt, IfBlock):
            found.add(stmt.cond.cbit.index)
            found |= referenced_cbits(stmt.then_body)
            found |= referenced_cbits(stmt.else_body)
    return found


def verify_hybrid(source: str) -> dict:
    """Exhaustively cross-check compiled code against the interpreter.

    Returns a report dict; raises HybridError on any mismatch. Used by the
    test-suite, the CLI and CI.
    """
    program = parse_source(source, GATES)
    blocks = program.classical_blocks()
    flat_stmts = tuple(stmt for block in blocks for stmt in block.body)
    cbits = sorted(referenced_cbits(flat_stmts))

    quantum_ops, assembly = compile_hybrid(source)
    linked = link(parse_program(assembly)) if assembly else None

    mismatches = []
    for assignment in product((0, 1), repeat=len(cbits)):
        cvalues = dict(zip(cbits, assignment))
        expected = interpret_classical(flat_stmts, cvalues)
        injections = {"x%d" % (CBIT_BASE + k): v for k, v in cvalues.items()}
        final = execute(linked, injections) if linked else (0,) * 32
        for rid in range(REG_BASE, REG_BASE + 9):
            if final[rid] != expected[rid]:
                mismatches.append({
                    "injection": cvalues, "register": "r%d" % rid,
                    "expected": expected[rid], "actual": final[rid],
                })
    report = {
        "cases": 1 << len(cbits),
        "registers_checked": 9,
        "instructions": len(link(parse_program(assembly)).instructions) if assembly else 0,
        "mismatches": mismatches,
        "ok": not mismatches,
    }
    if mismatches:
        raise HybridError("verification failed: %s" % mismatches[:4])
    return report
