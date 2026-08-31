"""Hybrid-QASM extraction and deterministic RISC-V compilation."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence, Tuple

try:
    from ..loomq_core.model import Circuit
    from ..loomq_core.qasm2 import parse_qasm2
except ImportError:
    from loomq_core.model import Circuit
    from loomq_core.qasm2 import parse_qasm2

from .model import (
    Assignment,
    BinaryExpression,
    ClassicalReference,
    Expression,
    IfStatement,
    IntegerLiteral,
    RegisterReference,
    Statement,
    UnaryExpression,
)
from .parser import parse_classical_block


_DECLARATION = re.compile(r"^(?:qreg|creg)\s+[A-Za-z_]\w*\s*\[", re.I)
_CLASSICAL_KEYWORD = re.compile(r"\bclassical\b", re.I)
_MAX_SOURCE_LENGTH = 1_000_000


def compile_hybrid_program(source: str) -> Tuple[List[str], str]:
    """Return ordered quantum statements and classical RISC-V assembly."""
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Hybrid-QASM source must be a non-empty string")
    if len(source) > _MAX_SOURCE_LENGTH:
        raise ValueError("Hybrid-QASM source is too large")

    uncommented = _strip_comments(source)
    quantum_source, block_sources = _extract_classical_blocks(uncommented)
    circuit = parse_qasm2(quantum_source)
    statements = tuple(
        statement
        for block in block_sources
        for statement in parse_classical_block(block)
    )
    quantum_operations = _ordered_quantum_operations(quantum_source)
    assembly = _AssemblyCompiler(circuit).compile(statements)
    return quantum_operations, assembly


def _strip_comments(source: str) -> str:
    output: List[str] = []
    index = 0
    quote = ""
    while index < len(source):
        current = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if quote:
            output.append(current)
            if current == quote and (index == 0 or source[index - 1] != "\\"):
                quote = ""
            index += 1
            continue
        if current in {'"', "'"}:
            quote = current
            output.append(current)
            index += 1
            continue
        if current == "/" and following == "/":
            index += 2
            while index < len(source) and source[index] not in "\r\n":
                output.append(" ")
                index += 1
            continue
        if current == "/" and following == "*":
            output.extend((" ", " "))
            index += 2
            while index + 1 < len(source) and source[index : index + 2] != "*/":
                output.append("\n" if source[index] == "\n" else " ")
                index += 1
            if index + 1 >= len(source):
                raise ValueError("Unterminated block comment")
            output.extend((" ", " "))
            index += 2
            continue
        output.append(current)
        index += 1
    return "".join(output)


def _extract_classical_blocks(source: str) -> Tuple[str, Tuple[str, ...]]:
    quantum = list(source)
    blocks = []
    search_from = 0
    while True:
        match = _CLASSICAL_KEYWORD.search(source, search_from)
        if match is None:
            break
        brace = match.end()
        while brace < len(source) and source[brace].isspace():
            brace += 1
        if brace >= len(source) or source[brace] != "{":
            raise ValueError("classical must be followed by a braced block")
        end = _matching_brace(source, brace)
        blocks.append(source[brace + 1 : end])
        for index in range(match.start(), end + 1):
            if quantum[index] not in "\r\n":
                quantum[index] = " "
        search_from = end + 1
    return "".join(quantum), tuple(blocks)


def _matching_brace(source: str, opening: int) -> int:
    depth = 0
    quote = ""
    for index in range(opening, len(source)):
        current = source[index]
        if quote:
            if current == quote and source[index - 1] != "\\":
                quote = ""
            continue
        if current in {'"', "'"}:
            quote = current
        elif current == "{":
            depth += 1
        elif current == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("Unterminated classical block")


def _ordered_quantum_operations(source: str) -> List[str]:
    operations = []
    for raw_statement in source.split(";"):
        statement = re.sub(r"\s+", " ", raw_statement).strip()
        lowered = statement.lower()
        if not statement:
            continue
        if lowered == "openqasm 2.0" or lowered.startswith("include "):
            continue
        if _DECLARATION.match(statement):
            continue
        operations.append(statement + ";")
    return operations


class _AssemblyCompiler:
    def __init__(self, circuit: Circuit):
        self.circuit = circuit
        self.lines: List[str] = []
        self.label_index = 0
        self.scratch: Tuple[str, str] = ("", "")
        self.classical_registers: Dict[str, Tuple[int, int]] = {
            register.name: (register.offset, register.size)
            for register in circuit.classical_registers
        }

    def compile(self, statements: Sequence[Statement]) -> str:
        used_user, used_classical = self._used_registers(statements)
        measurement_registers = set(
            range(10, 10 + self.circuit.classical_bit_count)
        )
        if measurement_registers and max(measurement_registers) > 31:
            raise ValueError("Measurement bit cannot be mapped beyond RISC-V x31")
        reserved = used_user | used_classical | measurement_registers
        available = [index for index in range(31, 0, -1) if index not in reserved]
        if len(available) < 2:
            raise ValueError("Hybrid-QASM requires two RISC-V scratch registers")
        self.scratch = (f"x{available[0]}", f"x{available[1]}")
        self._statements(statements)
        if not self.lines:
            self.lines.append("addi x0, x0, 0")
        for scratch in self.scratch:
            if int(scratch[1:]) <= 9:
                self.lines.append(f"li {scratch}, 0")
        return "\n".join(self.lines) + "\n"

    def _used_registers(self, statements: Sequence[Statement]) -> Tuple[set, set]:
        user = set()
        classical = set()

        def expression(item: Expression) -> None:
            if isinstance(item, RegisterReference):
                user.add(item.index)
            elif isinstance(item, ClassicalReference):
                classical.add(self._classical_register_index(item))
            elif isinstance(item, UnaryExpression):
                expression(item.operand)
            elif isinstance(item, BinaryExpression):
                expression(item.left)
                expression(item.right)

        def statement(item: Statement) -> None:
            if isinstance(item, Assignment):
                user.add(item.target)
                expression(item.expression)
            else:
                expression(item.condition.left)
                expression(item.condition.right)
                for child in item.then_body + item.else_body:
                    statement(child)

        for item in statements:
            statement(item)
        return user, classical

    def _statements(self, statements: Iterable[Statement]) -> None:
        for statement in statements:
            if isinstance(statement, Assignment):
                self._assignment(statement)
            else:
                self._if_statement(statement)

    def _assignment(self, statement: Assignment) -> None:
        target = f"x{statement.target}"
        self._expression(statement.expression, self.scratch[0])
        self.lines.append(f"addi {target}, {self.scratch[0]}, 0")

    def _if_statement(self, statement: IfStatement) -> None:
        self.label_index += 1
        else_label = f"L3_ELSE_{self.label_index}"
        end_label = f"L3_END_{self.label_index}"
        self._expression(statement.condition.left, self.scratch[0])
        self._expression(statement.condition.right, self.scratch[1])
        branch = "bne" if statement.condition.operator == "==" else "beq"
        self.lines.append(f"{branch} {self.scratch[0]}, {self.scratch[1]}, {else_label}")
        self._statements(statement.then_body)
        self.lines.append(f"j {end_label}")
        self.lines.append(f"{else_label}:")
        self._statements(statement.else_body)
        self.lines.append(f"{end_label}:")

    def _expression(self, expression: Expression, target: str) -> None:
        atoms = list(self._flatten(expression))
        if not atoms:
            raise ValueError("Classical expression cannot be empty")
        first_sign, first = atoms[0]
        if isinstance(first, IntegerLiteral):
            self.lines.append(f"li {target}, {first_sign * first.value}")
        else:
            source = self._source_register(first)
            instruction = "addi" if first_sign == 1 else "sub"
            if instruction == "addi":
                self.lines.append(f"addi {target}, {source}, 0")
            else:
                self.lines.append(f"sub {target}, x0, {source}")
        for sign, atom in atoms[1:]:
            if isinstance(atom, IntegerLiteral):
                value = sign * atom.value
                if value:
                    self.lines.append(f"addi {target}, {target}, {value}")
            else:
                instruction = "add" if sign == 1 else "sub"
                self.lines.append(
                    f"{instruction} {target}, {target}, {self._source_register(atom)}"
                )

    def _flatten(self, expression: Expression, sign: int = 1):
        if isinstance(expression, (IntegerLiteral, RegisterReference, ClassicalReference)):
            yield sign, expression
            return
        if isinstance(expression, UnaryExpression):
            unary_sign = sign if expression.operator == "+" else -sign
            yield from self._flatten(expression.operand, unary_sign)
            return
        if isinstance(expression, BinaryExpression):
            yield from self._flatten(expression.left, sign)
            right_sign = sign if expression.operator == "+" else -sign
            yield from self._flatten(expression.right, right_sign)
            return
        raise TypeError(f"Unsupported classical expression: {type(expression).__name__}")

    def _source_register(self, expression: Expression) -> str:
        if isinstance(expression, RegisterReference):
            return f"x{expression.index}"
        if not isinstance(expression, ClassicalReference):
            raise TypeError("Expected register expression")
        return f"x{self._classical_register_index(expression)}"

    def _classical_register_index(self, expression: ClassicalReference) -> int:
        metadata = self.classical_registers.get(expression.register)
        if metadata is None:
            raise ValueError(f"Unknown classical register: {expression.register}")
        offset, size = metadata
        if not 0 <= expression.index < size:
            raise ValueError(
                f"Index outside classical register {expression.register}: {expression.index}"
            )
        register_index = 10 + offset + expression.index
        if register_index > 31:
            raise ValueError("Measurement bit cannot be mapped beyond RISC-V x31")
        return register_index
