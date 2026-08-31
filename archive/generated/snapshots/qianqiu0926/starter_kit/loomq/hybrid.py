"""Recursive-descent Hybrid-QASM parser and deterministic RISC-V compiler."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Union

from .ir import QASMError, parse_qasm2, strip_comments


class HybridSyntaxError(ValueError):
    """Raised for source outside the published Hybrid-QASM mini grammar."""


@dataclass(frozen=True)
class Literal:
    value: int


@dataclass(frozen=True)
class RegisterValue:
    index: int


@dataclass(frozen=True)
class MeasurementValue:
    index: int


@dataclass(frozen=True)
class UnaryMinus:
    operand: "Expression"


@dataclass(frozen=True)
class BinaryExpression:
    operator: str
    left: "Expression"
    right: "Expression"


Expression = Union[Literal, RegisterValue, MeasurementValue, UnaryMinus, BinaryExpression]


@dataclass(frozen=True)
class Condition:
    operator: str
    left: Expression
    right: Expression


@dataclass(frozen=True)
class Assignment:
    register: int
    expression: Expression


@dataclass(frozen=True)
class IfStatement:
    condition: Condition
    then_body: tuple["Statement", ...]
    else_body: tuple["Statement", ...]


Statement = Union[Assignment, IfStatement]


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int


TOKEN_RE = re.compile(
    r"(?P<SPACE>\s+)|(?P<EQ>==)|(?P<NE>!=)|(?P<NUMBER>\d+)|"
    r"(?P<IDENT>[A-Za-z_]\w*)|(?P<PLUS>\+)|(?P<MINUS>-)|(?P<ASSIGN>=)|"
    r"(?P<LPAREN>\()|(?P<RPAREN>\))|(?P<LBRACE>\{)|(?P<RBRACE>\})|"
    r"(?P<LBRACKET>\[)|(?P<RBRACKET>\])|(?P<SEMICOLON>;)",
)


def _tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    position = 0
    while position < len(source):
        match = TOKEN_RE.match(source, position)
        if not match:
            excerpt = source[position : position + 20]
            raise HybridSyntaxError(f"unexpected token at character {position}: {excerpt!r}")
        if match.lastgroup != "SPACE":
            tokens.append(Token(match.lastgroup or "", match.group(), position))
        position = match.end()
    tokens.append(Token("EOF", "", position))
    return tokens


class ClassicalParser:
    def __init__(self, source: str):
        self.tokens = _tokenize(source)
        self.position = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.position]

    def accept(self, kind: str, value: Optional[str] = None) -> Optional[Token]:
        token = self.current
        if token.kind != kind or (value is not None and token.value.lower() != value.lower()):
            return None
        self.position += 1
        return token

    def expect(self, kind: str, value: Optional[str] = None) -> Token:
        token = self.accept(kind, value)
        if token is None:
            wanted = value if value is not None else kind
            raise HybridSyntaxError(
                f"expected {wanted!r} at character {self.current.position}, got {self.current.value!r}"
            )
        return token

    def parse(self) -> tuple[Statement, ...]:
        body = self.statements("EOF")
        self.expect("EOF")
        return body

    def statements(self, until: str) -> tuple[Statement, ...]:
        result: list[Statement] = []
        while self.current.kind != until:
            if self.current.kind == "EOF":
                raise HybridSyntaxError("unterminated classical block")
            result.append(self.statement())
        return tuple(result)

    def statement(self) -> Statement:
        if self.current.kind == "IDENT" and self.current.value.lower() == "if":
            return self.if_statement()
        target = self.expect("IDENT")
        register = self._program_register(target)
        self.expect("ASSIGN")
        expression = self.expression()
        self.expect("SEMICOLON")
        return Assignment(register, expression)

    def if_statement(self) -> IfStatement:
        self.expect("IDENT", "if")
        self.expect("LPAREN")
        left = self.expression()
        operator = self.current
        if not self.accept("EQ") and not self.accept("NE"):
            raise HybridSyntaxError("if condition must use == or !=")
        right = self.expression()
        self.expect("RPAREN")
        self.expect("LBRACE")
        then_body = self.statements("RBRACE")
        self.expect("RBRACE")
        else_body: tuple[Statement, ...] = ()
        if self.accept("IDENT", "else"):
            self.expect("LBRACE")
            else_body = self.statements("RBRACE")
            self.expect("RBRACE")
        return IfStatement(Condition(operator.value, left, right), then_body, else_body)

    def expression(self) -> Expression:
        value = self.primary()
        while self.current.kind in {"PLUS", "MINUS"}:
            operator = self.current.value
            self.position += 1
            value = BinaryExpression(operator, value, self.primary())
        return value

    def primary(self) -> Expression:
        if self.accept("MINUS"):
            return UnaryMinus(self.primary())
        number = self.accept("NUMBER")
        if number:
            return Literal(int(number.value))
        identifier = self.accept("IDENT")
        if identifier:
            lowered = identifier.value.lower()
            if re.fullmatch(r"r[1-9]", lowered):
                return RegisterValue(int(lowered[1:]))
            if lowered == "c":
                self.expect("LBRACKET")
                index = int(self.expect("NUMBER").value)
                self.expect("RBRACKET")
                return MeasurementValue(index)
            raise HybridSyntaxError(f"unknown classical identifier: {identifier.value}")
        if self.accept("LPAREN"):
            value = self.expression()
            self.expect("RPAREN")
            return value
        raise HybridSyntaxError(
            f"expected an integer, r1..r9, c[k], or expression at character {self.current.position}"
        )

    @staticmethod
    def _program_register(token: Token) -> int:
        if not re.fullmatch(r"r[1-9]", token.value.lower()):
            raise HybridSyntaxError("assignment target must be r1..r9")
        return int(token.value[1:])


def _extract_classical(source: str) -> tuple[str, str]:
    clean = strip_comments(source)
    match = re.search(r"\bclassical\s*\{", clean, flags=re.IGNORECASE)
    if not match:
        raise HybridSyntaxError("Hybrid-QASM requires one classical { ... } block")
    opening = clean.find("{", match.start())
    depth = 0
    closing = -1
    for position in range(opening, len(clean)):
        if clean[position] == "{":
            depth += 1
        elif clean[position] == "}":
            depth -= 1
            if depth == 0:
                closing = position
                break
    if closing < 0:
        raise HybridSyntaxError("unterminated classical block")
    if re.search(r"\bclassical\s*\{", clean[closing + 1 :], flags=re.IGNORECASE):
        raise HybridSyntaxError("only one classical block is supported")
    quantum_source = clean[: match.start()] + "\n" + clean[closing + 1 :]
    classical_source = clean[opening + 1 : closing]
    return quantum_source, classical_source


class TempAllocator:
    def __init__(self, cbit_count: int):
        measured = set(range(10, 10 + cbit_count))
        self.available = [index for index in range(31, 9, -1) if index not in measured]
        self.in_use: set[int] = set()
        self.ever_used: set[int] = set()

    def acquire(self) -> str:
        for index in self.available:
            if index not in self.in_use:
                self.in_use.add(index)
                self.ever_used.add(index)
                return f"x{index}"
        raise HybridSyntaxError("classical expression needs more temporary RISC-V registers")

    def release(self, register: str, owned: bool) -> None:
        if owned:
            self.in_use.discard(int(register[1:]))


class RiscVCompiler:
    def __init__(self, cbit_count: int):
        self.cbit_count = cbit_count
        self.temps = TempAllocator(cbit_count)
        self.lines: list[str] = ["# LoomQ Hybrid-QASM deterministic compilation"]
        self.label_counter = 0

    def label(self, prefix: str) -> str:
        self.label_counter += 1
        return f"LOOMQ_{prefix}_{self.label_counter}"

    def expression(self, value: Expression) -> tuple[str, bool]:
        if isinstance(value, Literal):
            target = self.temps.acquire()
            self.lines.append(f"li {target}, {value.value}")
            return target, True
        if isinstance(value, RegisterValue):
            return f"x{value.index}", False
        if isinstance(value, MeasurementValue):
            if value.index >= self.cbit_count:
                raise HybridSyntaxError(f"measurement bit c[{value.index}] is out of range")
            return f"x{10 + value.index}", False
        if isinstance(value, UnaryMinus):
            source, owned = self.expression(value.operand)
            if owned:
                self.lines.append(f"sub {source}, x0, {source}")
                return source, True
            target = self.temps.acquire()
            self.lines.append(f"sub {target}, x0, {source}")
            self.temps.release(source, owned)
            return target, True
        if isinstance(value, BinaryExpression):
            left, left_owned = self.expression(value.left)
            right, right_owned = self.expression(value.right)
            operation = "add" if value.operator == "+" else "sub"
            # Reuse a dead expression temporary. This lowers peak scratch
            # pressure from three registers to two for literal-heavy trees.
            if left_owned:
                target = left
            elif right_owned:
                target = right
            else:
                target = self.temps.acquire()
            self.lines.append(f"{operation} {target}, {left}, {right}")
            if left != target:
                self.temps.release(left, left_owned)
            if right != target:
                self.temps.release(right, right_owned)
            return target, True
        raise TypeError(f"unknown expression: {value!r}")

    def statement(self, statement: Statement) -> None:
        if isinstance(statement, Assignment):
            source, owned = self.expression(statement.expression)
            destination = f"x{statement.register}"
            if destination != source:
                self.lines.append(f"addi {destination}, {source}, 0")
            self.temps.release(source, owned)
            return
        if isinstance(statement, IfStatement):
            left, left_owned = self.expression(statement.condition.left)
            right, right_owned = self.expression(statement.condition.right)
            else_label, end_label = self.label("ELSE"), self.label("END")
            inverse = "bne" if statement.condition.operator == "==" else "beq"
            self.lines.append(f"{inverse} {left}, {right}, {else_label}")
            self.temps.release(left, left_owned)
            self.temps.release(right, right_owned)
            for child in statement.then_body:
                self.statement(child)
            self.lines.append(f"j {end_label}")
            self.lines.append(f"{else_label}:")
            for child in statement.else_body:
                self.statement(child)
            self.lines.append(f"{end_label}:")
            return
        raise TypeError(f"unknown statement: {statement!r}")

    def compile(self, statements: tuple[Statement, ...]) -> str:
        for statement in statements:
            self.statement(statement)
        # Scratch registers are an implementation detail, so leave no observable
        # residue that could be mistaken for a user-program result.
        for index in sorted(self.temps.ever_used):
            self.lines.append(f"li x{index}, 0")
        return "\n".join(self.lines) + "\n"


def compile_hybrid_program(source: str) -> tuple[list[str], str]:
    if not isinstance(source, str) or not source.strip():
        raise HybridSyntaxError("Hybrid-QASM source must be a non-empty string")
    quantum_source, classical_source = _extract_classical(source)
    try:
        circuit = parse_qasm2(quantum_source)
    except QASMError as exc:
        raise HybridSyntaxError(f"invalid quantum portion: {exc}") from exc
    if circuit.total_cbits > 22:
        raise HybridSyntaxError("Hybrid RISC-V mapping supports at most 22 classical measurement bits")
    statements = ClassicalParser(classical_source).parse()
    assembly = RiscVCompiler(circuit.total_cbits).compile(statements)
    return circuit.quantum_instruction_lines(), assembly
