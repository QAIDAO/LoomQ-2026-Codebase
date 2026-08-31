"""Hybrid-QASM parser and compiler for the LoomQ L3 classical subset."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

try:
    from .loomq_l1.parser import parse_qasm
except ImportError:
    from loomq_l1.parser import parse_qasm


_COMMENT = re.compile(r"//[^\r\n]*")
_CLASSICAL = re.compile(r"\bclassical\b")


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str
    position: int


@dataclass(frozen=True)
class _Number:
    value: int


@dataclass(frozen=True)
class _Register:
    index: int


@dataclass(frozen=True)
class _Measurement:
    index: int


@dataclass(frozen=True)
class _Binary:
    operator: str
    left: object
    right: object


@dataclass(frozen=True)
class _Assign:
    target: int
    expression: object


@dataclass(frozen=True)
class _If:
    condition: _Binary
    then_body: tuple[object, ...]
    else_body: tuple[object, ...]


def _error(message: str, position: int | None = None) -> ValueError:
    if position is None:
        return ValueError(message)
    return ValueError("%s at character %d" % (message, position + 1))


def _mask_comments(text: str) -> str:
    return _COMMENT.sub(lambda match: re.sub(r"[^\r\n]", " ", match.group(0)), text)


def _extract_classical_block(source: str) -> tuple[str, str]:
    masked = _mask_comments(source)
    matches = list(_CLASSICAL.finditer(masked))
    if len(matches) != 1:
        raise _error("Hybrid-QASM must contain exactly one classical block")
    marker = matches[0]
    cursor = marker.end()
    while cursor < len(masked) and masked[cursor].isspace():
        cursor += 1
    if cursor == len(masked) or masked[cursor] != "{":
        raise _error("classical must be followed by an opening brace", cursor)
    start = cursor
    depth = 0
    for cursor in range(start, len(masked)):
        if masked[cursor] == "{":
            depth += 1
        elif masked[cursor] == "}":
            depth -= 1
            if depth == 0:
                return source[: marker.start()] + source[cursor + 1 :], source[start + 1 : cursor]
    raise _error("unclosed classical block", start)


def _normalise_statement(statement: str) -> str:
    statement = " ".join(statement.split())
    statement = re.sub(r"\s*,\s*", ", ", statement)
    statement = re.sub(r"\s*->\s*", " -> ", statement)
    return statement + ";"


def _quantum_operations(source: str) -> tuple[list[str], int]:
    stripped = _COMMENT.sub("", source)
    parts = stripped.split(";")
    if parts[-1].strip():
        raise _error("quantum statement is missing a semicolon")
    statements = [_normalise_statement(part) for part in parts[:-1] if part.strip()]
    if not statements:
        raise _error("missing OpenQASM program")
    headers: list[str] = []
    declarations: list[str] = []
    gates: list[str] = []
    measurements: list[str] = []
    operations: list[str] = []
    for statement in statements:
        bare = statement[:-1].strip()
        if bare.startswith("OPENQASM") or bare.startswith("include"):
            headers.append(statement)
        elif bare.startswith("qreg") or bare.startswith("creg"):
            declarations.append(statement)
        elif bare == "measure" or (bare.startswith("measure") and len(bare) > 7 and bare[7].isspace()):
            measurements.append(statement)
            operations.append(statement)
        else:
            gates.append(statement)
            operations.append(statement)
    validation_source = "\n".join(headers + declarations + gates + measurements)
    try:
        circuit = parse_qasm(validation_source)
    except Exception as exc:
        raise _error("invalid quantum OpenQASM: %s" % exc) from exc
    if not operations:
        raise _error("Hybrid-QASM contains no quantum operations")
    return operations, circuit.num_clbits


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if text.startswith("==", index) or text.startswith("!=", index):
            tokens.append(_Token("COMPARE", text[index : index + 2], index))
            index += 2
            continue
        if char in "+-={}()[];":
            kinds = {"+": "PLUS", "-": "MINUS", "=": "ASSIGN", "{": "LBRACE", "}": "RBRACE", "(": "LPAREN", ")": "RPAREN", "[": "LBRACKET", "]": "RBRACKET", ";": "SEMICOLON"}
            tokens.append(_Token(kinds[char], char, index))
            index += 1
            continue
        if char.isdigit():
            end = index + 1
            while end < len(text) and text[end].isdigit():
                end += 1
            tokens.append(_Token("INTEGER", text[index:end], index))
            index = end
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                end += 1
            word = text[index:end]
            if word in ("if", "else"):
                kind = word.upper()
            elif word == "c":
                kind = "CLASSICAL"
            elif re.fullmatch(r"r[1-9]", word):
                kind = "REGISTER"
            elif word.startswith("r") and word[1:].isdigit():
                raise _error("register must be r1 through r9", index)
            else:
                raise _error("unsupported identifier %s" % word, index)
            tokens.append(_Token(kind, word, index))
            index = end
            continue
        raise _error("unsupported character %r" % char, index)
    tokens.append(_Token("EOF", "", len(text)))
    return tokens


class _ClassicalParser:
    def __init__(self, text: str):
        self.tokens = _tokenize(text)
        self.index = 0

    def _peek(self) -> _Token:
        return self.tokens[self.index]

    def _take(self, kind: str) -> _Token:
        token = self._peek()
        if token.kind != kind:
            raise _error("expected %s, got %s" % (kind, token.kind), token.position)
        self.index += 1
        return token

    def parse(self) -> tuple[object, ...]:
        body = self._statements("EOF")
        self._take("EOF")
        if not body:
            raise _error("classical block must contain at least one statement")
        return body

    def _statements(self, terminator: str) -> tuple[object, ...]:
        result = []
        while self._peek().kind != terminator:
            if self._peek().kind == "EOF":
                raise _error("unexpected end of classical block", self._peek().position)
            result.append(self._statement())
        return tuple(result)

    def _statement(self) -> object:
        token = self._peek()
        if token.kind == "IF":
            return self._if_statement()
        target = self._take("REGISTER")
        self._take("ASSIGN")
        expression = self._expression()
        self._take("SEMICOLON")
        return _Assign(int(target.text[1:]), expression)

    def _if_statement(self) -> _If:
        self._take("IF")
        self._take("LPAREN")
        left = self._expression()
        compare = self._take("COMPARE")
        right = self._expression()
        self._take("RPAREN")
        self._take("LBRACE")
        then_body = self._statements("RBRACE")
        self._take("RBRACE")
        else_body: tuple[object, ...] = ()
        if self._peek().kind == "ELSE":
            self._take("ELSE")
            self._take("LBRACE")
            else_body = self._statements("RBRACE")
            self._take("RBRACE")
        return _If(_Binary(compare.text, left, right), then_body, else_body)

    def _expression(self) -> object:
        result = self._atom()
        while self._peek().kind in ("PLUS", "MINUS"):
            operator = self._peek().text
            self.index += 1
            result = _Binary(operator, result, self._atom())
        return result

    def _atom(self) -> object:
        token = self._peek()
        if token.kind == "MINUS":
            self.index += 1
            number = self._take("INTEGER")
            return _Number(-int(number.text))
        if token.kind == "INTEGER":
            self.index += 1
            return _Number(int(token.text))
        if token.kind == "REGISTER":
            self.index += 1
            return _Register(int(token.text[1:]))
        if token.kind == "CLASSICAL":
            self.index += 1
            self._take("LBRACKET")
            bit = self._take("INTEGER")
            self._take("RBRACKET")
            return _Measurement(int(bit.text))
        raise _error("expected integer, register, or c[k]", token.position)


def _validate_measurements(node: object, clbit_count: int) -> None:
    if isinstance(node, _Measurement):
        if node.index < 0 or node.index >= clbit_count or node.index + 10 > 31:
            raise _error("measurement bit c[%d] cannot map to a RISC-V register" % node.index)
    elif isinstance(node, _Binary):
        _validate_measurements(node.left, clbit_count)
        _validate_measurements(node.right, clbit_count)
    elif isinstance(node, _Assign):
        _validate_measurements(node.expression, clbit_count)
    elif isinstance(node, _If):
        _validate_measurements(node.condition, clbit_count)
        for statement in node.then_body + node.else_body:
            _validate_measurements(statement, clbit_count)


class _CodeGenerator:
    _SCRATCH = ("x28", "x29", "x30", "x31")

    def __init__(self):
        self.lines: list[str] = []
        self.label_number = 0

    def compile(self, statements: Sequence[object]) -> str:
        for statement in statements:
            self._statement(statement)
        return "\n".join(self.lines)

    def _new_label(self, prefix: str) -> str:
        label = "%s_%d" % (prefix, self.label_number)
        self.label_number += 1
        return label

    @staticmethod
    def _reg(index: int) -> str:
        return "x%d" % index

    def _emit_expression(self, expression: object, target: str, blocked: Iterable[str] = ()) -> None:
        if isinstance(expression, _Number):
            self.lines.append("li %s, %d" % (target, expression.value))
            return
        if isinstance(expression, _Register):
            self.lines.append("addi %s, %s, 0" % (target, self._reg(expression.index)))
            return
        if isinstance(expression, _Measurement):
            self.lines.append("addi %s, x%d, 0" % (target, expression.index + 10))
            return
        if not isinstance(expression, _Binary) or expression.operator not in ("+", "-"):
            raise _error("invalid arithmetic expression")
        self._emit_expression(expression.left, target, blocked)
        if isinstance(expression.right, _Number):
            immediate = expression.right.value if expression.operator == "+" else -expression.right.value
            self.lines.append("addi %s, %s, %d" % (target, target, immediate))
            return
        temporary = next(register for register in self._SCRATCH if register != target and register not in blocked)
        self._emit_expression(expression.right, temporary, tuple(blocked) + (target,))
        instruction = "add" if expression.operator == "+" else "sub"
        self.lines.append("%s %s, %s, %s" % (instruction, target, target, temporary))

    def _statement(self, statement: object) -> None:
        if isinstance(statement, _Assign):
            self._emit_expression(statement.expression, "x28")
            self.lines.append("addi x%d, x28, 0" % statement.target)
            return
        if not isinstance(statement, _If):
            raise _error("invalid classical statement")
        self._emit_expression(statement.condition.left, "x28")
        self._emit_expression(statement.condition.right, "x29", ("x28",))
        else_label = self._new_label("ELSE")
        end_label = self._new_label("END")
        inverse = "bne" if statement.condition.operator == "==" else "beq"
        self.lines.append("%s x28, x29, %s" % (inverse, else_label))
        for child in statement.then_body:
            self._statement(child)
        if statement.else_body:
            self.lines.append("j %s" % end_label)
            self.lines.append(else_label + ":")
            for child in statement.else_body:
                self._statement(child)
            self.lines.append(end_label + ":")
        else:
            self.lines.append(else_label + ":")


def compile_hybrid(hybrid_qasm_str: str) -> tuple[list[str], str]:
    """Compile the contest Hybrid-QASM subset into operations and RISC-V assembly."""
    if type(hybrid_qasm_str) is not str:
        raise ValueError("Hybrid-QASM source must be a string")
    quantum_source, classical_source = _extract_classical_block(hybrid_qasm_str)
    operations, clbit_count = _quantum_operations(quantum_source)
    statements = _ClassicalParser(classical_source).parse()
    for statement in statements:
        _validate_measurements(statement, clbit_count)
    assembly = _CodeGenerator().compile(statements)
    return operations, assembly


__all__ = ["compile_hybrid"]
