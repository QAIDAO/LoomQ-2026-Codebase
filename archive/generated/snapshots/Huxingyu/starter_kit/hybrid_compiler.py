"""Parser and RISC-V code generator for the LoomQ Hybrid-QASM subset."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple, Union

try:
    from .qasm_core import Circuit, Operation, parse_qasm
except ImportError:
    from qasm_core import Circuit, Operation, parse_qasm


@dataclass(frozen=True)
class Atom:
    kind: str
    value: int


@dataclass(frozen=True)
class Binary:
    operator: str
    left: "Expression"
    right: "Expression"


Expression = Union[Atom, Binary]


@dataclass(frozen=True)
class Assignment:
    register: int
    expression: Expression


@dataclass(frozen=True)
class Branch:
    operator: str
    left: Expression
    right: Expression
    then_body: Tuple["Statement", ...]
    else_body: Tuple["Statement", ...]


Statement = Union[Assignment, Branch]


TOKEN_RE = re.compile(
    r"(?P<SPACE>\s+)|(?P<COMMENT>//[^\n]*|/\*.*?\*/)|"
    r"(?P<IF>\bif\b)|(?P<ELSE>\belse\b)|"
    r"(?P<REG>\br[1-9]\b)|(?P<CBIT>\bc\s*\[\s*\d+\s*\])|"
    r"(?P<INT>\d+)|(?P<EQ>==)|(?P<NE>!=)|(?P<PLUS>\+)|(?P<MINUS>-)|"
    r"(?P<ASSIGN>=)|(?P<LPAREN>\()|(?P<RPAREN>\))|"
    r"(?P<LBRACE>\{)|(?P<RBRACE>\})|(?P<SEMI>;)",
    re.DOTALL | re.IGNORECASE,
)


def _tokens(text: str) -> List[Tuple[str, str]]:
    result = []
    position = 0
    while position < len(text):
        match = TOKEN_RE.match(text, position)
        if not match:
            excerpt = text[position:position + 24].splitlines()[0]
            raise ValueError(f"invalid classical syntax near {excerpt!r}")
        position = match.end()
        if match.lastgroup not in {"SPACE", "COMMENT"}:
            result.append((match.lastgroup or "", match.group()))
    result.append(("EOF", ""))
    return result


class Parser:
    def __init__(self, text: str):
        self.tokens = _tokens(text)
        self.position = 0

    def current(self) -> str:
        return self.tokens[self.position][0]

    def accept(self, kind: str) -> str | None:
        if self.current() != kind:
            return None
        value = self.tokens[self.position][1]
        self.position += 1
        return value

    def expect(self, kind: str) -> str:
        value = self.accept(kind)
        if value is None:
            raise ValueError(f"expected {kind}, got {self.current()}")
        return value

    def parse(self) -> Tuple[Statement, ...]:
        statements = self.parse_statements("EOF")
        self.expect("EOF")
        return statements

    def parse_statements(self, terminator: str) -> Tuple[Statement, ...]:
        statements: List[Statement] = []
        while self.current() != terminator:
            if self.current() == "EOF":
                raise ValueError(f"expected {terminator}, got EOF")
            statements.append(self.parse_statement())
        return tuple(statements)

    def parse_statement(self) -> Statement:
        if self.accept("IF") is not None:
            return self.parse_branch()
        register = int(self.expect("REG")[1:])
        self.expect("ASSIGN")
        expression = self.parse_expression()
        self.expect("SEMI")
        return Assignment(register, expression)

    def parse_branch(self) -> Branch:
        self.expect("LPAREN")
        left = self.parse_expression()
        if self.accept("EQ") is not None:
            operator = "=="
        elif self.accept("NE") is not None:
            operator = "!="
        else:
            raise ValueError("if condition must use == or !=")
        right = self.parse_expression()
        self.expect("RPAREN")
        then_body = self.parse_block()
        self.expect("ELSE")
        else_body = self.parse_block()
        return Branch(operator, left, right, then_body, else_body)

    def parse_block(self) -> Tuple[Statement, ...]:
        self.expect("LBRACE")
        statements = self.parse_statements("RBRACE")
        self.expect("RBRACE")
        return statements

    def parse_expression(self) -> Expression:
        expression = self.parse_factor()
        while self.current() in {"PLUS", "MINUS"}:
            if self.accept("PLUS") is not None:
                operator = "+"
            else:
                self.expect("MINUS")
                operator = "-"
            expression = Binary(operator, expression, self.parse_factor())
        return expression

    def parse_factor(self) -> Expression:
        if self.accept("PLUS") is not None:
            return self.parse_factor()
        if self.accept("MINUS") is not None:
            return Binary("-", Atom("integer", 0), self.parse_factor())
        integer = self.accept("INT")
        if integer is not None:
            return Atom("integer", int(integer))
        register = self.accept("REG")
        if register is not None:
            return Atom("register", int(register[1:]))
        cbit = self.accept("CBIT")
        if cbit is not None:
            return Atom("cbit", int(re.search(r"\d+", cbit).group()))
        if self.accept("LPAREN") is not None:
            expression = self.parse_expression()
            self.expect("RPAREN")
            return expression
        raise ValueError(f"expected expression, got {self.current()}")


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return "\n".join(line.split("//", 1)[0] for line in text.splitlines())


def split_hybrid(source: str) -> Tuple[str, str]:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("hybrid QASM must be a non-empty string")
    text = _strip_comments(source)
    match = re.search(r"\bclassical\s*\{", text, flags=re.IGNORECASE)
    if not match:
        raise ValueError("Hybrid-QASM contains no classical block")
    opening = text.find("{", match.start())
    depth = 0
    closing = None
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                closing = index
                break
    if closing is None:
        raise ValueError("unterminated classical block")
    if re.search(r"\bclassical\s*\{", text[closing + 1:], flags=re.IGNORECASE):
        raise ValueError("only one classical block is allowed")
    quantum_source = text[:match.start()] + "\n" + text[closing + 1:]
    return quantum_source, text[opening + 1:closing]


def _collect_cbits(expression: Expression) -> Iterable[int]:
    if isinstance(expression, Atom):
        return (expression.value,) if expression.kind == "cbit" else ()
    return (*_collect_cbits(expression.left), *_collect_cbits(expression.right))


def _statement_cbits(statement: Statement) -> Iterable[int]:
    if isinstance(statement, Assignment):
        return _collect_cbits(statement.expression)
    nested = [*_collect_cbits(statement.left), *_collect_cbits(statement.right)]
    for child in (*statement.then_body, *statement.else_body):
        nested.extend(_statement_cbits(child))
    return nested


class CodeGenerator:
    def __init__(self, statements: Sequence[Statement]):
        measured_registers = {10 + index for statement in statements for index in _statement_cbits(statement)}
        self.available = [index for index in range(31, 9, -1) if index not in measured_registers]
        self.lines: List[str] = []
        self.label_counter = 0

    def allocate(self) -> int:
        if not self.available:
            raise ValueError("classical expression requires more temporary registers")
        return self.available.pop()

    def release(self, register: int) -> None:
        self.available.append(register)

    def label(self, prefix: str) -> str:
        self.label_counter += 1
        return f"LQ_{prefix}_{self.label_counter}"

    def expression(self, expression: Expression) -> Tuple[int, bool]:
        if isinstance(expression, Atom):
            if expression.kind == "register":
                return expression.value, False
            if expression.kind == "cbit":
                register = 10 + expression.value
                if register > 31:
                    raise ValueError("measurement cbit exceeds RISC-V register mapping")
                return register, False
            target = self.allocate()
            self.lines.append(f"li x{target}, {expression.value}")
            return target, True

        left, left_temporary = self.expression(expression.left)
        right, right_temporary = self.expression(expression.right)
        target = left if left_temporary else self.allocate()
        operation = "add" if expression.operator == "+" else "sub"
        self.lines.append(f"{operation} x{target}, x{left}, x{right}")
        if right_temporary and right != target:
            self.release(right)
        if left_temporary and left != target:
            self.release(left)
        return target, True

    def statement(self, statement: Statement) -> None:
        if isinstance(statement, Assignment):
            source, temporary = self.expression(statement.expression)
            self.lines.append(f"addi x{statement.register}, x{source}, 0")
            if temporary:
                self.release(source)
            return

        left, left_temporary = self.expression(statement.left)
        right, right_temporary = self.expression(statement.right)
        else_label = self.label("ELSE")
        end_label = self.label("END")
        branch = "bne" if statement.operator == "==" else "beq"
        self.lines.append(f"{branch} x{left}, x{right}, {else_label}")
        if left_temporary:
            self.release(left)
        if right_temporary:
            self.release(right)
        for child in statement.then_body:
            self.statement(child)
        self.lines.append(f"j {end_label}")
        self.lines.append(else_label + ":")
        for child in statement.else_body:
            self.statement(child)
        self.lines.append(end_label + ":")

    def generate(self, statements: Sequence[Statement]) -> str:
        for statement in statements:
            self.statement(statement)
        if not self.lines:
            self.lines.append("addi x0, x0, 0")
        return "\n".join(self.lines) + "\n"


def _format_angle(value: float) -> str:
    return f"{value:.12g}"


def quantum_operation_strings(circuit: Circuit) -> List[str]:
    result = []
    for operation in circuit.operations:
        if operation.name == "measure":
            result.append(f"measure q[{operation.qubits[0]}] -> c[{operation.cbits[0]}];")
            continue
        params = f"({_format_angle(operation.params[0])})" if operation.params else ""
        qubits = ", ".join(f"q[{index}]" for index in operation.qubits)
        result.append(f"{operation.name}{params} {qubits};")
    return result


def compile_hybrid(source: str) -> Tuple[List[str], str]:
    quantum_source, classical_source = split_hybrid(source)
    circuit = parse_qasm(quantum_source)
    statements = Parser(classical_source).parse()
    assembly = CodeGenerator(statements).generate(statements)
    return quantum_operation_strings(circuit), assembly
