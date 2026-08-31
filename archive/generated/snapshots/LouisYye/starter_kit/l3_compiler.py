"""Compiler for LoomQ's small quantum/classical hybrid language.

The quantum prefix is ordinary OpenQASM 2.0.  A trailing ``classical`` block
is parsed into a deliberately small, deterministic language and lowered to
the instruction subset implemented by :mod:`riscv_emulator`.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional, Sequence, Tuple, Union

try:
    from .parser import parse_qasm
    from .riscv_emulator import encode_quantum_instruction
except ImportError:
    from parser import parse_qasm
    from riscv_emulator import encode_quantum_instruction


class HybridSyntaxError(ValueError):
    """Raised when a hybrid program is outside the supported L3 subset."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int


@dataclass(frozen=True)
class Value:
    kind: str
    value: int


@dataclass(frozen=True)
class Binary:
    operator: str
    left: "Expression"
    right: "Expression"


Expression = Union[Value, Binary]


@dataclass(frozen=True)
class Assignment:
    register: int
    expression: Expression


@dataclass(frozen=True)
class IfStatement:
    left: Expression
    operator: str
    right: Expression
    then_body: Sequence["Statement"]
    else_body: Sequence["Statement"]


Statement = Union[Assignment, IfStatement]


_TOKEN_RE = re.compile(
    r"(?P<space>\s+)|(?P<comment>//[^\n]*|\#[^\n]*)|"
    r"(?P<compare>==|!=)|(?P<integer>\d+)|(?P<register>r\d+)|"
    r"(?P<cbit>c\[\d+\])|(?P<name>[A-Za-z_]\w*)|"
    r"(?P<symbol>[+\-={}();])"
)


def _tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    position = 0
    while position < len(source):
        match = _TOKEN_RE.match(source, position)
        if match is None:
            raise HybridSyntaxError(
                f"unsupported character at offset {position}: {source[position]!r}"
            )
        kind = match.lastgroup or ""
        value = match.group()
        if kind not in ("space", "comment"):
            tokens.append(Token(kind, value, position))
        position = match.end()
    tokens.append(Token("eof", "", len(source)))
    return tokens


class _Parser:
    def __init__(self, source: str):
        self.tokens = _tokenize(source)
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def accept(self, value: str) -> bool:
        if self.current.value == value:
            self.index += 1
            return True
        return False

    def expect(self, value: str) -> None:
        if not self.accept(value):
            raise HybridSyntaxError(
                f"expected {value!r} at offset {self.current.position}, "
                f"got {self.current.value!r}"
            )

    def parse(self) -> Sequence[Statement]:
        statements = self.parse_statements(stop=None)
        if self.current.kind != "eof":
            raise HybridSyntaxError(f"unexpected token {self.current.value!r}")
        return statements

    def parse_statements(self, stop: Optional[str]) -> Sequence[Statement]:
        result: List[Statement] = []
        while self.current.kind != "eof" and self.current.value != stop:
            result.append(self.parse_statement())
        return result

    def parse_statement(self) -> Statement:
        if self.current.value == "if":
            return self.parse_if()
        token = self.current
        if token.kind != "register":
            raise HybridSyntaxError(
                f"expected assignment or if at offset {token.position}"
            )
        register = self.parse_register(token)
        self.index += 1
        self.expect("=")
        expression = self.parse_expression()
        self.expect(";")
        return Assignment(register, expression)

    def parse_if(self) -> IfStatement:
        self.expect("if")
        self.expect("(")
        left = self.parse_expression()
        if self.current.value not in ("==", "!="):
            raise HybridSyntaxError(
                f"expected == or != at offset {self.current.position}"
            )
        operator = self.current.value
        self.index += 1
        right = self.parse_expression()
        self.expect(")")
        then_body = self.parse_block()
        else_body: Sequence[Statement] = []
        if self.accept("else"):
            else_body = self.parse_block()
        return IfStatement(left, operator, right, then_body, else_body)

    def parse_block(self) -> Sequence[Statement]:
        self.expect("{")
        body = self.parse_statements(stop="}")
        self.expect("}")
        return body

    def parse_expression(self) -> Expression:
        expression = self.parse_atom()
        while self.current.value in ("+", "-"):
            operator = self.current.value
            self.index += 1
            expression = Binary(operator, expression, self.parse_atom())
        return expression

    def parse_atom(self) -> Expression:
        token = self.current
        if token.value == "-":
            self.index += 1
            value = self.current
            if value.kind != "integer":
                raise HybridSyntaxError(
                    f"negative sign must precede an integer at offset {value.position}"
                )
            self.index += 1
            return Value("integer", -int(value.value))
        if token.kind == "integer":
            self.index += 1
            return Value("integer", int(token.value))
        if token.kind == "register":
            register = self.parse_register(token)
            self.index += 1
            return Value("register", register)
        if token.kind == "cbit":
            bit = int(token.value[2:-1])
            if bit > 21:
                raise HybridSyntaxError("c[k] maps to x10+k, so k must be in 0..21")
            self.index += 1
            return Value("cbit", bit)
        if self.accept("("):
            expression = self.parse_expression()
            self.expect(")")
            return expression
        raise HybridSyntaxError(
            f"expected integer, r1..r9, or c[k] at offset {token.position}"
        )

    @staticmethod
    def parse_register(token: Token) -> int:
        register = int(token.value[1:])
        if register < 1 or register > 9:
            raise HybridSyntaxError("classical registers are limited to r1..r9")
        return register


def _used_cbits(statements: Sequence[Statement]) -> set[int]:
    result: set[int] = set()

    def expression(expr: Expression) -> None:
        if isinstance(expr, Value) and expr.kind == "cbit":
            result.add(expr.value)
        elif isinstance(expr, Binary):
            expression(expr.left)
            expression(expr.right)

    for statement in statements:
        if isinstance(statement, Assignment):
            expression(statement.expression)
        else:
            expression(statement.left)
            expression(statement.right)
            result.update(_used_cbits(statement.then_body))
            result.update(_used_cbits(statement.else_body))
    return result


class _Compiler:
    def __init__(self, statements: Sequence[Statement]):
        reserved = set(range(1, 10))
        reserved.update(10 + bit for bit in _used_cbits(statements))
        self.scratch = [register for register in range(31, 9, -1) if register not in reserved]
        self.lines: List[str] = []
        self.label_counter = 0

    def new_label(self, stem: str) -> str:
        self.label_counter += 1
        return f"LQ_{stem}_{self.label_counter}"

    def acquire(self) -> int:
        if not self.scratch:
            raise HybridSyntaxError("expression requires more scratch registers")
        return self.scratch.pop()

    def release(self, register: int) -> None:
        self.scratch.append(register)

    def compile(self, statements: Sequence[Statement]) -> str:
        self.compile_statements(statements)
        return "\n".join(self.lines) + ("\n" if self.lines else "")

    def compile_statements(self, statements: Sequence[Statement]) -> None:
        for statement in statements:
            if isinstance(statement, Assignment):
                self.compile_expression(statement.expression, statement.register)
            else:
                self.compile_if(statement)

    def compile_expression(self, expression: Expression, destination: int) -> None:
        if isinstance(expression, Value):
            if expression.kind == "integer":
                self.lines.append(f"li x{destination}, {expression.value}")
            else:
                source = expression.value if expression.kind == "register" else 10 + expression.value
                if source != destination:
                    self.lines.append(f"addi x{destination}, x{source}, 0")
            return

        constant = self.constant_value(expression)
        if constant is not None:
            self.lines.append(f"li x{destination}, {constant}")
            return

        base, terms = self.flatten_chain(expression)
        destination_uses = self.register_uses(expression, destination)
        in_place = (
            destination_uses == 0
            or (
                isinstance(base, Value)
                and base.kind == "register"
                and base.value == destination
                and destination_uses == 1
            )
        )
        accumulator = destination if in_place else self.acquire()
        try:
            # The common register +/- register form lowers to one instruction.
            if (
                len(terms) == 1
                and isinstance(base, Value)
                and base.kind != "integer"
                and isinstance(terms[0][1], Value)
                and terms[0][1].kind != "integer"
            ):
                operator, right = terms[0]
                left_register = base.value if base.kind == "register" else 10 + base.value
                right_register = right.value if right.kind == "register" else 10 + right.value
                operation = "add" if operator == "+" else "sub"
                self.lines.append(
                    f"{operation} x{accumulator}, x{left_register}, x{right_register}"
                )
            else:
                self.compile_expression(base, accumulator)
                for operator, term in terms:
                    if isinstance(term, Value) and term.kind == "integer":
                        immediate = term.value if operator == "+" else -term.value
                        self.lines.append(
                            f"addi x{accumulator}, x{accumulator}, {immediate}"
                        )
                    elif isinstance(term, Value):
                        source = term.value if term.kind == "register" else 10 + term.value
                        operation = "add" if operator == "+" else "sub"
                        self.lines.append(
                            f"{operation} x{accumulator}, x{accumulator}, x{source}"
                        )
                    else:
                        scratch = self.acquire()
                        try:
                            self.compile_expression(term, scratch)
                            operation = "add" if operator == "+" else "sub"
                            self.lines.append(
                                f"{operation} x{accumulator}, x{accumulator}, x{scratch}"
                            )
                        finally:
                            self.release(scratch)
            if accumulator != destination:
                self.lines.append(f"addi x{destination}, x{accumulator}, 0")
        finally:
            if accumulator != destination:
                self.release(accumulator)

    @staticmethod
    def flatten_chain(expression: Binary) -> Tuple[Expression, List[Tuple[str, Expression]]]:
        terms: List[Tuple[str, Expression]] = []
        current: Expression = expression
        while isinstance(current, Binary):
            terms.append((current.operator, current.right))
            current = current.left
        terms.reverse()
        return current, terms

    @staticmethod
    def register_uses(expression: Expression, register: int) -> int:
        if isinstance(expression, Value):
            return int(expression.kind == "register" and expression.value == register)
        return _Compiler.register_uses(
            expression.left, register
        ) + _Compiler.register_uses(expression.right, register)

    @staticmethod
    def constant_value(expression: Expression) -> Optional[int]:
        if isinstance(expression, Value):
            return expression.value if expression.kind == "integer" else None
        left = _Compiler.constant_value(expression.left)
        right = _Compiler.constant_value(expression.right)
        if left is None or right is None:
            return None
        return left + right if expression.operator == "+" else left - right

    def compile_if(self, statement: IfStatement) -> None:
        false_label = self.new_label("ELSE")
        end_label = self.new_label("END")
        left = self.acquire()
        right = self.acquire()
        try:
            self.compile_expression(statement.left, left)
            self.compile_expression(statement.right, right)
            inverse_branch = "bne" if statement.operator == "==" else "beq"
            self.lines.append(f"{inverse_branch} x{left}, x{right}, {false_label}")
        finally:
            self.release(right)
            self.release(left)
        self.compile_statements(statement.then_body)
        if statement.else_body:
            self.lines.append(f"j {end_label}")
        self.lines.append(f"{false_label}:")
        self.compile_statements(statement.else_body)
        if statement.else_body:
            self.lines.append(f"{end_label}:")


def _split_hybrid(source: str) -> Tuple[str, Optional[str]]:
    # Keep character offsets stable while preventing a commented example from
    # being mistaken for the real block.
    searchable = re.sub(
        r"//[^\n]*|\#[^\n]*",
        lambda match: " " * len(match.group()),
        source,
    )
    match = re.search(r"\bclassical\s*\{", searchable, re.IGNORECASE)
    if match is None:
        return source.strip(), None
    open_brace = source.find("{", match.start())
    depth = 0
    close_brace = -1
    for index in range(open_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                close_brace = index
                break
    if close_brace < 0:
        raise HybridSyntaxError("unterminated classical block")
    quantum = source[: match.start()] + "\n" + source[close_brace + 1 :]
    return quantum.strip(), source[open_brace + 1 : close_brace]


def _quantum_operations(qasm: str) -> List[str]:
    # Validate the quantum portion with the same parser used by L1.
    parse_qasm(qasm)
    without_comments = re.sub(r"//[^\n]*|\#[^\n]*", "", qasm)
    operations: List[str] = []
    declarations = ("openqasm", "include", "qreg", "creg")
    for fragment in without_comments.split(";"):
        statement = " ".join(fragment.split())
        if statement and not statement.lower().startswith(declarations):
            operations.append(statement + ";")
    return operations


def compile_hybrid(source: str) -> Tuple[List[str], str]:
    """Compile a hybrid OpenQASM/classical source program."""
    if not isinstance(source, str):
        raise TypeError("hybrid source must be a string")
    if not source.strip():
        raise HybridSyntaxError("hybrid source must not be empty")
    qasm, classical = _split_hybrid(source)
    if classical is None:
        return _quantum_operations(qasm), ""
    statements = _Parser(classical).parse()
    if not statements:
        raise HybridSyntaxError("classical block must contain at least one statement")
    return _quantum_operations(qasm), _Compiler(statements).compile(statements)


def emit_quantum_riscv(operations: Sequence[str]) -> str:
    """Lower parameter-free quantum operations to custom-0 machine words."""
    output: List[str] = []
    gate_pattern = re.compile(r"^(\w+)\s+q\[(\d+)\](?:\s*,\s*q\[(\d+)\])?(?:\s*,\s*q\[(\d+)\])?;$")
    measure_pattern = re.compile(r"^measure\s+q\[(\d+)\]\s*->\s*c\[(\d+)\];$")
    for operation in operations:
        measurement = measure_pattern.fullmatch(operation.strip())
        if measurement:
            decoded = {"op": "measure", "qubit": int(measurement.group(1)), "bit": int(measurement.group(2))}
            output.append(f".word 0x{encode_quantum_instruction(decoded):08x} # {operation.strip()}")
            continue
        gate = gate_pattern.fullmatch(operation.strip())
        if not gate:
            raise HybridSyntaxError(f"operation has no custom encoding: {operation}")
        operands = [int(value) for value in gate.groups()[1:] if value is not None]
        decoded = {"op": "gate", "gate": gate.group(1).lower(), "qubits": operands}
        output.append(f".word 0x{encode_quantum_instruction(decoded):08x} # {operation.strip()}")
    return "\n".join(output) + ("\n" if output else "")
