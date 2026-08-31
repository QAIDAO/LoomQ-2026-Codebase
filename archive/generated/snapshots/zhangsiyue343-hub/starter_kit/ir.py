#!/usr/bin/env python3
"""Typed intermediate representation shared by every stage.

Front-end (parser.py) produces a Program of typed nodes; lowering expands
register broadcasts into bit-level ops and yields a flat Circuit that the
transpilers, executors and simulator all consume. Expression trees are
small ASTs evaluated by `eval_expr` with a whitelist of safe operations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------
# expressions
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Expr:
    pass


@dataclass(frozen=True)
class Num(Expr):
    value: float


@dataclass(frozen=True)
class Pi(Expr):
    pass


@dataclass(frozen=True)
class Unary(Expr):
    op: str            # "+" | "-"
    operand: Expr


@dataclass(frozen=True)
class Binary(Expr):
    op: str            # "+" | "-" | "*" | "/"
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Func(Expr):
    name: str          # cos sin tan exp ln sqrt
    args: tuple[Expr, ...]


@dataclass(frozen=True)
class RegRef(Expr):
    """Classical register variable r1..r9; invalid inside gate parameters."""
    index: int


_SAFE_FUNCTIONS = {
    "cos": math.cos, "sin": math.sin, "tan": math.tan,
    "exp": math.exp, "ln": math.log, "sqrt": math.sqrt,
}


def eval_expr(expr: Expr) -> float:
    if isinstance(expr, Num):
        return expr.value
    if isinstance(expr, Pi):
        return math.pi
    if isinstance(expr, Unary):
        value = eval_expr(expr.operand)
        return value if expr.op == "+" else -value
    if isinstance(expr, Binary):
        left, right = eval_expr(expr.left), eval_expr(expr.right)
        if expr.op == "+":
            return left + right
        if expr.op == "-":
            return left - right
        if expr.op == "*":
            return left * right
        if expr.op == "/":
            if right == 0:
                raise ValueError("division by zero in gate parameter")
            return left / right
        raise ValueError("unknown binary operator %r" % expr.op)
    if isinstance(expr, Func):
        fn = _SAFE_FUNCTIONS.get(expr.name.lower())
        if fn is None:
            raise ValueError("unsupported function %r" % expr.name)
        return fn(*(eval_expr(a) for a in expr.args))
    if isinstance(expr, RegRef):
        raise ValueError("register r%d is only valid inside classical blocks"
                         % expr.index)
    raise ValueError("malformed expression node %r" % expr)


def simplify(expr: Expr) -> float:
    """Convenience wrapper used wherever a parameter must be concrete."""
    return float(eval_expr(expr))


# --------------------------------------------------------------------------
# program structure
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class RegDecl:
    name: str
    size: int


@dataclass(frozen=True)
class BitRef:
    reg: str
    index: int


@dataclass(frozen=True)
class WholeReg:
    reg: str


QubitArg = object  # BitRef | WholeReg


@dataclass(frozen=True)
class GateCall:
    gate: str                       # canonical lowercase name from gates.py
    params: tuple[Expr, ...]
    qubits: tuple[object, ...]      # BitRef | WholeReg


@dataclass(frozen=True)
class MeasureBits:
    source: BitRef
    target: BitRef


@dataclass(frozen=True)
class MeasureReg:
    source: str                     # register name
    target: str


@dataclass(frozen=True)
class Assign:
    register: int                   # r1..r9 stored as 1..9
    value: Expr


@dataclass(frozen=True)
class Condition:
    cbit: BitRef
    comparator: str                 # "==" | "!="
    literal: int


@dataclass(frozen=True)
class IfBlock:
    cond: Condition
    then_body: tuple[object, ...]
    else_body: tuple[object, ...]


ClassicalStmt = object  # Assign | IfBlock


@dataclass(frozen=True)
class ClassicalBlock:
    body: tuple[ClassicalStmt, ...]


Statement = object  # GateCall | MeasureBits | MeasureReg | ClassicalBlock


@dataclass
class Program:
    qregs: list[RegDecl] = field(default_factory=list)
    cregs: list[RegDecl] = field(default_factory=list)
    statements: list[Statement] = field(default_factory=list)

    def qreg(self, name: str) -> Optional[RegDecl]:
        return next((r for r in self.qregs if r.name == name), None)

    def creg(self, name: str) -> Optional[RegDecl]:
        return next((r for r in self.cregs if r.name == name), None)

    @property
    def n_qubits(self) -> int:
        return sum(r.size for r in self.qregs)

    @property
    def n_clbits(self) -> int:
        return sum(r.size for r in self.cregs)

    def classical_blocks(self) -> list[ClassicalBlock]:
        return [s for s in self.statements if isinstance(s, ClassicalBlock)]


# --------------------------------------------------------------------------
# flat circuit after lowering
# --------------------------------------------------------------------------

@dataclass
class Circuit:
    n_qubits: int
    n_clbits: int
    ops: list[tuple[str, tuple[float, ...], tuple[int, ...]]]   # (gate, params, qubit indices)
    measures: list[tuple[int, int]]                             # (qubit index, clbit index)

    def signature(self) -> str:
        parts = ["q%d_c%d" % (self.n_qubits, self.n_clbits)]
        parts.extend("%s(%s)%s" % (
            g, ",".join(repr(p) for p in params), "".join(str(q) for q in qubits))
            for g, params, qubits in self.ops)
        parts.extend("m%d.%d" % m for m in self.measures)
        return "|".join(parts)


def _resolve_reg_offset(program: Program, name: str) -> int:
    offset = 0
    for decl in program.qregs:
        if decl.name == name:
            return offset
        offset += decl.size
    raise ValueError("undeclared quantum register %r" % name)


def _creg_offset(program: Program, name: str) -> int:
    offset = 0
    for decl in program.cregs:
        if decl.name == name:
            return offset
        offset += decl.size
    raise ValueError("undeclared classical register %r" % name)


def lower(program: Program) -> Circuit:
    """Expand whole-register broadcasts and collect the measure map."""
    circuit = Circuit(program.n_qubits, program.n_clbits, [], [])

    def qubit_index(arg: object) -> int:
        assert isinstance(arg, BitRef)
        base = _resolve_reg_offset(program, arg.reg)
        size = program.qreg(arg.reg).size
        if not 0 <= arg.index < size:
            raise ValueError("q[%s] index %d out of range (size %d)"
                             % (arg.reg, arg.index, size))
        return base + arg.index

    for statement in program.statements:
        if isinstance(statement, (ClassicalBlock,)):
            continue
        if isinstance(statement, MeasureReg):
            src = program.qreg(statement.source)
            dst = program.creg(statement.target)
            if src is None or dst is None:
                raise ValueError("measure %s -> %s: unknown register"
                                 % (statement.source, statement.target))
            if src.size != dst.size:
                raise ValueError("measure %s -> %s: register sizes differ (%d vs %d)"
                                 % (statement.source, statement.target,
                                    src.size, dst.size))
            base_s = _resolve_reg_offset(program, src.name)
            base_d = _creg_offset(program, dst.name)
            circuit.measures.extend(
                (base_s + i, base_d + i) for i in range(src.size))
            continue
        if isinstance(statement, MeasureBits):
            qi = qubit_index(statement.source)
            ci = _creg_offset(program, statement.target.reg) + statement.target.index
            csize = program.creg(statement.target.reg).size
            if not 0 <= statement.target.index < csize:
                raise ValueError("c[%s] index out of range" % statement.target.reg)
            circuit.measures.append((qi, ci))
            continue
        if isinstance(statement, GateCall):
            expanded: list[list[int]] = []
            for arg in statement.qubits:
                if isinstance(arg, WholeReg):
                    decl = program.qreg(arg.reg)
                    if decl is None:
                        raise ValueError("unknown quantum register %r" % arg.reg)
                    base = _resolve_reg_offset(program, arg.reg)
                    expanded.append([base + i for i in range(decl.size)])
                else:
                    expanded.append([qubit_index(arg)])
            widths = {len(group) for group in expanded}
            if len(widths) > 1:
                if 1 not in widths:
                    raise ValueError("register widths differ in gate arguments")
                width = max(widths)
                expanded = [
                    group if len(group) != 1 else [group[0]] * width
                    for group in expanded
                ]
            params = tuple(simplify(p) for p in statement.params)
            for combination in zip(*expanded):
                circuit.ops.append((statement.gate, params, tuple(combination)))
            continue
        raise ValueError("unexpected statement %r" % (statement,))
    return circuit
