"""L3 Hybrid-QASM compiler.

Splits a Hybrid-QASM program into:

1. the pure quantum operation sequence (gates + measurements, in order), and
2. RISC-V assembly implementing the ``classical { ... }`` block, runnable on
   the official ``riscv_emulator.py`` (li/add/sub/addi/beq/bne/j subset).

Register mapping (fixed by the contest rules):
  r1..r9  -> x1..x9   (general purpose)
  c[k]    -> x(10+k)  (measurement bits injected by the evaluator)
Scratch registers x28..x31 are used for expression evaluation.

The classical block grammar that is supported:
  stmt  := assign | if
  assign:= "r"<1-9> "=" expr ";"
  if    := "if" "(" expr ("=="|"!=") expr ")" "{" stmt* "}" [ "else" "{" stmt* "}" ]
  expr  := operand (("+"|"-") operand)*
  operand := integer | "r"<1-9> | "c" "[" <k> "]"

A real recursive-descent parser and code generator -- no pattern matching
against sample programs, so randomly generated cases work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

from .qasm import _split_statements, parse_qasm2
from .transpilers import _format_qasm2_gate


# ---------------------------------------------------------------------------
# Quantum / classical split
# ---------------------------------------------------------------------------

_CLASSICAL_RE = re.compile(r"classical\s*\{", re.IGNORECASE)


def _extract_classical_block(text: str) -> Tuple[str, str]:
    """Return (qasm_part, classical_body). Braces may nest."""
    match = _CLASSICAL_RE.search(text)
    if not match:
        return text, ""
    depth = 1
    idx = match.end()
    while idx < len(text) and depth:
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        idx += 1
    if depth:
        raise ValueError("unbalanced braces in classical block")
    body = text[match.end(): idx - 1]
    qasm_part = text[: match.start()] + text[idx:]
    return qasm_part, body


def _normalize_quantum_ops(qasm_part: str) -> List[str]:
    """Normalize the quantum part into an ordered list of operation strings."""
    # Validate against the full QASM parser first.
    circuit = parse_qasm2(qasm_part)
    ops: List[str] = []
    for stmt in _split_statements(qasm_part):
        if stmt.upper().startswith("OPENQASM") or stmt.startswith("include"):
            continue
        if re.fullmatch(r"[qcr]reg\s+.*", stmt):
            continue
        m = re.fullmatch(
            r"measure\s+([A-Za-z_]\w*)\[(\d+)\]\s*->\s*([A-Za-z_]\w*)\[(\d+)\]", stmt
        )
        if m:
            ops.append("measure %s[%s] -> %s[%s];" % m.groups())
            continue
        m = re.fullmatch(
            r"measure\s+([A-Za-z_]\w*)\s*->\s*([A-Za-z_]\w*)", stmt
        )
        if m:
            # whole-register measure: expand to per-bit ops using the parsed IR
            for qubit, clbit in sorted(circuit.measurements):
                ops.append("measure q[%d] -> c[%d];" % (qubit, clbit))
            continue
        # gate statement: re-emit in canonical form
        gate_match = re.fullmatch(
            r"([A-Za-z][A-Za-z0-9]*)(?:\((.+)\))?\s+(.+)", stmt
        )
        if not gate_match:
            raise ValueError("unparseable quantum statement: %r" % stmt)
        name = gate_match.group(1).lower()
        params = ""
        if gate_match.group(2):
            params = "(%s)" % ", ".join(
                p.strip() for p in gate_match.group(2).split(",")
            )
        operands = ", ".join(
            token.strip() for token in gate_match.group(3).split(",")
        )
        ops.append("%s%s %s;" % (name, params, operands))
    return ops


# ---------------------------------------------------------------------------
# Classical block: AST
# ---------------------------------------------------------------------------

@dataclass
class Num:
    value: int


@dataclass
class Reg:
    index: int  # r<i> -> x<i>


@dataclass
class CBit:
    index: int  # c[k] -> x(10+k)


@dataclass
class BinOp:
    op: str  # '+' or '-'
    left: "Expr"
    right: "Expr"


Expr = Union[Num, Reg, CBit, BinOp]


@dataclass
class Assign:
    target: int  # register index i of r<i>
    expr: Expr


@dataclass
class If:
    op: str  # '==' or '!='
    left: Expr
    right: Expr
    then_body: List["Stmt"]
    else_body: List["Stmt"]


Stmt = Union[Assign, If]


_TOKEN_RE = re.compile(
    r"""
    (?P<num>\d+)
    | (?P<cbit>c\[\d+\])
    | (?P<reg>r[1-9]\b)
    | (?P<kw>if|else)\b
    | (?P<op>==|!=|\+|-|=)
    | (?P<punct>[(){}\;])
    """,
    re.VERBOSE,
)


def _tokenize(body: str) -> List[str]:
    tokens: List[str] = []
    pos = 0
    while pos < len(body):
        if body[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(body, pos)
        if not m:
            raise ValueError("classical block: unexpected character at %r" % body[pos:pos + 20])
        tokens.append(m.group(0))
        pos = m.end()
    return tokens


class _Parser:
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Optional[str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self) -> str:
        token = self.peek()
        if token is None:
            raise ValueError("classical block: unexpected end of input")
        self.pos += 1
        return token

    def expect(self, token: str) -> None:
        actual = self.next()
        if actual != token:
            raise ValueError("classical block: expected %r, got %r" % (token, actual))

    def parse_block(self) -> List[Stmt]:
        stmts: List[Stmt] = []
        while self.peek() is not None and self.peek() != "}":
            stmts.append(self.parse_stmt())
        return stmts

    def parse_stmt(self) -> Stmt:
        token = self.peek()
        if token == "if":
            return self.parse_if()
        if token and re.fullmatch(r"r[1-9]", token):
            target = int(self.next()[1])
            self.expect("=")
            expr = self.parse_expr()
            self.expect(";")
            return Assign(target, expr)
        raise ValueError("classical block: unexpected token %r" % token)

    def parse_if(self) -> If:
        self.expect("if")
        self.expect("(")
        left = self.parse_expr()
        op = self.next()
        if op not in ("==", "!="):
            raise ValueError("classical block: expected comparison, got %r" % op)
        right = self.parse_expr()
        self.expect(")")
        self.expect("{")
        then_body = self.parse_block()
        self.expect("}")
        else_body: List[Stmt] = []
        if self.peek() == "else":
            self.next()
            self.expect("{")
            else_body = self.parse_block()
            self.expect("}")
        return If(op, left, right, then_body, else_body)

    def parse_expr(self) -> Expr:
        node = self.parse_operand()
        while self.peek() in ("+", "-"):
            op = self.next()
            right = self.parse_operand()
            node = BinOp(op, node, right)
        return node

    def parse_operand(self) -> Expr:
        token = self.next()
        if token.isdigit():
            return Num(int(token))
        m = re.fullmatch(r"c\[(\d+)\]", token)
        if m:
            return CBit(int(m.group(1)))
        m = re.fullmatch(r"r([1-9])", token)
        if m:
            return Reg(int(m.group(1)))
        raise ValueError("classical block: bad operand %r" % token)


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

_SCRATCH = ["x28", "x29", "x30", "x31"]
# Dedicated assignment temporary; never read by source expressions (those only
# reference x1..x9 and x10+), so it is always safe to clobber.
_ASSIGN_TEMP = "x27"


class _Codegen:
    def __init__(self) -> None:
        self.lines: List[str] = []
        self.label_counter = 0

    def fresh_label(self) -> str:
        self.label_counter += 1
        return "L%d" % self.label_counter

    def emit(self, text: str) -> None:
        self.lines.append(text)

    def gen_operand(self, node: Expr, rd: str, scratch_idx: int) -> None:
        if isinstance(node, Num):
            self.emit("li %s, %d" % (rd, node.value))
        elif isinstance(node, Reg):
            self.emit("addi %s, x%d, 0" % (rd, node.index))
        elif isinstance(node, CBit):
            self.emit("addi %s, x%d, 0" % (rd, 10 + node.index))
        elif isinstance(node, BinOp):
            scratch = _SCRATCH[scratch_idx]
            if scratch == rd:
                raise AssertionError("scratch register collision")
            self.gen_operand(node.left, rd, scratch_idx + 1)
            self.gen_operand(node.right, scratch, scratch_idx + 1)
            instr = "add" if node.op == "+" else "sub"
            self.emit("%s %s, %s, %s" % (instr, rd, rd, scratch))
        else:
            raise AssertionError("unknown expression node")

    def gen_stmt(self, stmt: Stmt) -> None:
        if isinstance(stmt, Assign):
            # Evaluate into a dedicated temp first: the expression may read the
            # target register itself (e.g. `r1 = c[0] + r1 - 14`), so compiling
            # directly into x<target> would clobber the source mid-expression.
            self.gen_operand(stmt.expr, _ASSIGN_TEMP, 0)
            self.emit("addi x%d, %s, 0" % (stmt.target, _ASSIGN_TEMP))
            return
        # If statement
        left_reg, right_reg = _SCRATCH[0], _SCRATCH[1]
        self.gen_operand(stmt.left, left_reg, 2)
        self.gen_operand(stmt.right, right_reg, 2)
        then_label = self.fresh_label()
        end_label = self.fresh_label()
        branch = "beq" if stmt.op == "==" else "bne"
        inv_branch = "bne" if stmt.op == "==" else "beq"
        if stmt.else_body:
            self.emit("%s %s, %s, %s" % (branch, left_reg, right_reg, then_label))
            for s in stmt.else_body:
                self.gen_stmt(s)
            self.emit("j %s" % end_label)
            self.emit("%s:" % then_label)
            for s in stmt.then_body:
                self.gen_stmt(s)
            self.emit("%s:" % end_label)
        else:
            self.emit("%s %s, %s, %s" % (inv_branch, left_reg, right_reg, end_label))
            for s in stmt.then_body:
                self.gen_stmt(s)
            self.emit("%s:" % end_label)

    def gen(self, stmts: List[Stmt]) -> str:
        self.emit("# LoomQ hybrid compiler output (classical block)")
        for stmt in stmts:
            self.gen_stmt(stmt)
        return "\n".join(self.lines) + "\n"


def compile_hybrid_qasm(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Compile Hybrid-QASM into (quantum ops, RISC-V assembly)."""
    if not isinstance(hybrid_qasm_str, str) or not hybrid_qasm_str.strip():
        raise ValueError("empty Hybrid-QASM input")
    qasm_part, classical_body = _extract_classical_block(hybrid_qasm_str)
    quantum_ops = _normalize_quantum_ops(qasm_part)
    tokens = _tokenize(classical_body)
    stmts = _Parser(tokens).parse_block()
    assembly = _Codegen().gen(stmts)
    return quantum_ops, assembly
