"""Hybrid-QASM parser and Tiny RISC-V lowering for LoomQ L3."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence, Tuple, Union

try:
    from .loomq_l1 import emit_spinq, parse_qasm
except ImportError:
    from loomq_l1 import emit_spinq, parse_qasm


class HybridQASMError(ValueError):
    pass


@dataclass(frozen=True)
class Atom:
    kind: str
    value: int


@dataclass(frozen=True)
class Binary:
    op: str
    left: "Expr"
    right: "Expr"


Expr = Union[Atom, Binary]


@dataclass(frozen=True)
class Assign:
    register: int
    expression: Expr


@dataclass(frozen=True)
class IfElse:
    op: str
    left: Expr
    right: Expr
    then_body: Tuple["Statement", ...]
    else_body: Tuple["Statement", ...]


Statement = Union[Assign, IfElse]


TOKEN = re.compile(r"\s*(?:(//[^\n]*\n)|([A-Za-z_]\w*)|(\d+)|(==|!=|[+\-=(){};\[\]]))")


def _tokenize(source: str) -> List[str]:
    result, pos = [], 0
    while pos < len(source):
        match = TOKEN.match(source, pos)
        if not match:
            if source[pos:].strip():
                raise HybridQASMError("invalid classical token at offset %d" % pos)
            break
        pos = match.end()
        if match.group(1) is None:
            result.append(match.group(2) or match.group(3) or match.group(4))
    return result


class _Parser:
    def __init__(self, tokens: Sequence[str], classical_width: int):
        self.tokens, self.pos, self.classical_width = list(tokens), 0, classical_width

    def peek(self) -> str:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else "<eof>"

    def take(self, expected: str | None = None) -> str:
        token = self.peek()
        if expected is not None and token != expected:
            raise HybridQASMError("expected %r, got %r" % (expected, token))
        self.pos += 1
        return token

    def atom(self) -> Expr:
        token = self.peek()
        if token == "-":
            self.take()
            return Binary("-", Atom("constant", 0), self.atom())
        if token == "+":
            self.take()
            return self.atom()
        if token == "(":
            self.take()
            value = self.expression()
            self.take(")")
            return value
        self.take()
        if token.isdigit():
            return Atom("constant", int(token))
        match = re.fullmatch(r"r([1-9])", token)
        if match:
            return Atom("register", int(match.group(1)))
        if token == "c":
            self.take("[")
            index = self.take()
            if not index.isdigit():
                raise HybridQASMError("classical index must be an integer")
            self.take("]")
            value = int(index)
            if value >= self.classical_width or value > 21:
                raise HybridQASMError("classical bit c[%d] cannot map to x10..x31" % value)
            return Atom("measurement", value)
        raise HybridQASMError("invalid expression atom %r" % token)

    def expression(self) -> Expr:
        value = self.atom()
        while self.peek() in ("+", "-"):
            value = Binary(self.take(), value, self.atom())
        return value

    def block(self) -> Tuple[Statement, ...]:
        self.take("{")
        statements: List[Statement] = []
        while self.peek() != "}":
            if self.peek() == "<eof>":
                raise HybridQASMError("unterminated classical block")
            statements.append(self.statement())
        self.take("}")
        return tuple(statements)

    def statement(self) -> Statement:
        if self.peek() == "if":
            self.take(); self.take("(")
            left = self.expression()
            op = self.take()
            if op not in ("==", "!="):
                raise HybridQASMError("if condition requires == or !=")
            right = self.expression(); self.take(")")
            then_body = self.block(); self.take("else"); else_body = self.block()
            return IfElse(op, left, right, then_body, else_body)
        target = self.take()
        match = re.fullmatch(r"r([1-9])", target)
        if not match:
            raise HybridQASMError("assignment target must be r1..r9")
        self.take("="); expression = self.expression(); self.take(";")
        return Assign(int(match.group(1)), expression)


def _extract_classical(source: str) -> Tuple[str, str]:
    matches = list(re.finditer(r"\bclassical\s*\{", source))
    if len(matches) != 1:
        raise HybridQASMError("exactly one classical block is required")
    start, depth, pos = matches[0].start(), 1, matches[0].end()
    while pos < len(source) and depth:
        if source.startswith("//", pos):
            end = source.find("\n", pos)
            pos = len(source) if end < 0 else end + 1
            continue
        depth += (source[pos] == "{") - (source[pos] == "}")
        pos += 1
    if depth:
        raise HybridQASMError("unterminated classical block")
    return source[:start] + source[pos:], source[matches[0].end():pos - 1]


Linear = Tuple[int, dict[int, int]]


def _combine(left: Linear, right: Linear, sign: int = 1) -> Linear:
    """Return ``left + sign * right`` without mutating either operand."""

    constant = left[0] + sign * right[0]
    terms = dict(left[1])
    for register, coefficient in right[1].items():
        terms[register] = terms.get(register, 0) + sign * coefficient
        if not terms[register]:
            del terms[register]
    return constant, terms


def _runtime_linear(
    expr: Expr, measurement_constants: dict[int, int] | None = None
) -> Linear:
    """Lower an expression to the architectural registers it reads now."""

    if isinstance(expr, Atom):
        if expr.kind == "constant":
            return expr.value, {}
        if expr.kind == "measurement":
            if (
                measurement_constants is not None
                and expr.value in measurement_constants
            ):
                return measurement_constants[expr.value], {}
            return 0, {10 + expr.value: 1}
        return 0, {expr.value: 1}
    sign = 1 if expr.op == "+" else -1
    return _combine(
        _runtime_linear(expr.left, measurement_constants),
        _runtime_linear(expr.right, measurement_constants),
        sign,
    )


class _EmitterBase:
    def __init__(self):
        self.lines: List[str] = []
        self.labels = 0

    def materialize(self, target: int, value: Linear) -> None:
        """Materialize a linear value without changing any source register.

        A joint binary expansion emits every coefficient in logarithmic depth.
        Callers must choose a target that is absent from ``value`` so resetting
        and accumulating it cannot alias an input.
        """

        constant, terms = value
        if target in terms:
            raise HybridQASMError("internal L3 register-allocation conflict")
        width = max(
            [abs(constant).bit_length()]
            + [abs(coefficient).bit_length() for coefficient in terms.values()]
        )
        self.lines.append("li x%d, 0" % target)
        for bit in range(width - 1, -1, -1):
            if bit != width - 1:
                self.lines.append("add x%d, x%d, x%d" % (target, target, target))
            if (abs(constant) >> bit) & 1:
                self.lines.append(
                    "addi x%d, x%d, %d"
                    % (target, target, 1 if constant > 0 else -1)
                )
            for register, coefficient in sorted(terms.items()):
                if (abs(coefficient) >> bit) & 1:
                    operation = "add" if coefficient > 0 else "sub"
                    self.lines.append(
                        "%s x%d, x%d, x%d"
                        % (operation, target, target, register)
                    )


class _SharedCFGEmitter(_EmitterBase):
    """Lower against live r-registers with x31 as compiler scratch."""

    SCRATCH = 31

    def __init__(self, measurement_constants: dict[int, int] | None = None):
        super().__init__()
        self.measurement_constants = dict(measurement_constants or {})

    def linear(self, expression: Expr) -> Linear:
        return _runtime_linear(expression, self.measurement_constants)

    def body(self, statements: Sequence[Statement]) -> None:
        for statement in statements:
            if isinstance(statement, Assign):
                self.materialize(self.SCRATCH, self.linear(statement.expression))
                self.lines.append(
                    "add x%d, x%d, x0" % (statement.register, self.SCRATCH)
                )
                continue

            difference = _combine(
                self.linear(statement.left),
                self.linear(statement.right),
                -1,
            )
            constant, terms = difference
            if not terms:
                equal = constant == 0
                selected = (
                    statement.then_body
                    if equal == (statement.op == "==")
                    else statement.else_body
                )
                self.body(selected)
                continue

            ident = self.labels
            self.labels += 1
            self.materialize(self.SCRATCH, difference)
            branch = "bne" if statement.op == "==" else "beq"
            self.lines.append(
                "%s x%d, x0, L3_ELSE_%d" % (branch, self.SCRATCH, ident)
            )
            self.body(statement.then_body)
            self.lines.append("j L3_END_%d" % ident)
            self.lines.append("L3_ELSE_%d:" % ident)
            self.body(statement.else_body)
            self.lines.append("L3_END_%d:" % ident)


def compile_hybrid(source: str) -> Tuple[List[str], str]:
    if not isinstance(source, str):
        raise HybridQASMError("Hybrid-QASM input must be text")
    quantum_source, classical_source = _extract_classical(source)
    circuit = parse_qasm(quantum_source)
    cregs = dict(circuit.cregs)
    if set(cregs) != {"c"}:
        raise HybridQASMError("L3 requires exactly one classical register named c")
    classical_width = cregs["c"]
    if classical_width > 22:
        raise HybridQASMError(
            "L3 supports at most 22 classical bits mapped to x10..x31"
        )
    parser = _Parser(_tokenize(classical_source), classical_width)
    statements = []
    while parser.peek() != "<eof>":
        statements.append(parser.statement())
    if classical_width <= 21:
        shared_emitter = _SharedCFGEmitter()
        shared_emitter.body(statements)
        if not shared_emitter.lines:
            # Preserve the non-empty assembly contract for an empty classical
            # block without touching any contestant-visible r-register.
            shared_emitter.lines.append("li x31, 0")
        emitter = shared_emitter
    elif classical_width == 22:
        # Specialize c[21] on entry so each copy can use x31 as scratch.  Both
        # copies retain shared joins internally, and the original measurement
        # bit is restored before either path exits.
        emitter = _SharedCFGEmitter({21: 1})
        emitter.lines.append("beq x31, x0, L3_C21_ZERO")
        emitter.body(statements)
        emitter.lines.extend(
            ("li x31, 1", "j L3_C21_END", "L3_C21_ZERO:")
        )
        emitter.measurement_constants[21] = 0
        emitter.body(statements)
        emitter.lines.extend(("li x31, 0", "L3_C21_END:"))
    else:  # Defensive guard if the L1 parser ever admits a non-positive width.
        raise HybridQASMError("L3 classical register width must be positive")
    # Parse each operation with the shared L1 parser so register-wide expansion
    # and validation remain identical while source order is retained.
    base = ['OPENQASM 2.0;', 'include "qelib1.inc";']
    base += ["qreg %s[%d];" % item for item in circuit.qregs]
    base += ["creg %s[%d];" % item for item in circuit.cregs]
    quantum_ops: List[str] = []
    cleaned = re.sub(r"//[^\r\n]*", "", quantum_source)
    action = re.compile(r"^(?:h|x|s|sdg|t|tdg|rz|ry|cx|cu1|swap|ccx|measure)\b", re.I)
    for statement in (item.strip() for item in cleaned.split(";") if item.strip()):
        if not action.match(statement):
            continue
        fragment = parse_qasm("\n".join(base + [statement + ";"]))
        quantum_ops.extend(
            line for line in emit_spinq(fragment).splitlines() if action.match(line)
        )
    return quantum_ops, "\n".join(emitter.lines) + "\n"
