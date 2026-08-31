"""Deterministic scanner and parser for the published Hybrid-QASM grammar."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .ast import (
    Assign,
    BinaryExpr,
    Condition,
    Expr,
    HybridProgram,
    IfStmt,
    IntLiteral,
    MeasurementRef,
    RegisterRef,
    Stmt,
)


class HybridParseError(ValueError):
    """Raised when Hybrid-QASM is malformed or outside the published grammar."""


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    value: str
    position: int


_DECLARATION_RE = re.compile(
    r"^(?:OPENQASM\s+2\.0|include\s+\"qelib1\.inc\"|[qc]reg\s+[A-Za-z_]\w*\s*\[\s*\d+\s*\])$",
    re.IGNORECASE,
)
_REGISTER_RE = re.compile(r"r([1-9])$", re.IGNORECASE)


def _strip_comments(source: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    while index < len(source):
        char = source[index]
        if in_string:
            output.append(char)
            if char == "\\" and index + 1 < len(source):
                index += 1
                output.append(source[index])
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if source.startswith("//", index):
            output.extend((" ", " "))
            index += 2
            while index < len(source) and source[index] not in "\r\n":
                output.append(" ")
                index += 1
            continue
        if source.startswith("/*", index):
            output.extend((" ", " "))
            index += 2
            while index < len(source) and not source.startswith("*/", index):
                output.append(source[index] if source[index] in "\r\n" else " ")
                index += 1
            if index >= len(source):
                raise HybridParseError("unterminated block comment")
            output.extend((" ", " "))
            index += 2
            continue
        output.append(char)
        index += 1
    if in_string:
        raise HybridParseError("unterminated string literal")
    return "".join(output)


def _matching_brace(source: str, opening: int) -> int:
    depth = 1
    index = opening + 1
    in_string = False
    while index < len(source):
        char = source[index]
        if in_string:
            if char == "\\" and index + 1 < len(source):
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise HybridParseError("unbalanced classical block braces")


def _split_hybrid(source: str) -> tuple[str, list[str]]:
    quantum_parts: list[str] = []
    classical_bodies: list[str] = []
    cursor = 0
    index = 0
    in_string = False
    while index < len(source):
        char = source[index]
        if in_string:
            if char == "\\" and index + 1 < len(source):
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < len(source) and (source[end].isalnum() or source[end] == "_"):
                end += 1
            word = source[index:end]
            if word.lower() != "classical":
                index = end
                continue
            quantum_parts.append(source[cursor:index])
            opening = end
            while opening < len(source) and source[opening].isspace():
                opening += 1
            if opening >= len(source) or source[opening] != "{":
                raise HybridParseError("`classical` must be followed by a braced block")
            closing = _matching_brace(source, opening)
            classical_bodies.append(source[opening + 1 : closing])
            index = closing + 1
            cursor = index
            continue
        if char in "{}":
            raise HybridParseError("braces are only valid inside a classical block")
        index += 1
    quantum_parts.append(source[cursor:])
    if not classical_bodies:
        raise HybridParseError("Hybrid-QASM requires at least one classical block")
    return "\n".join(quantum_parts), classical_bodies


def _qasm_statements(source: str) -> list[str]:
    statements: list[str] = []
    start = 0
    in_string = False
    for index, char in enumerate(source):
        if char == '"' and (index == 0 or source[index - 1] != "\\"):
            in_string = not in_string
        elif char == ";" and not in_string:
            statement = " ".join(source[start:index].split())
            if statement:
                statements.append(statement)
            start = index + 1
    if source[start:].strip():
        raise HybridParseError("every top-level QASM statement must end with a semicolon")
    if len(statements) < 4:
        raise HybridParseError("Hybrid-QASM is missing required OpenQASM declarations")
    if not re.fullmatch(r"OPENQASM\s+2\.0", statements[0], re.IGNORECASE):
        raise HybridParseError("first statement must be OPENQASM 2.0")
    if not re.fullmatch(r'include\s+"qelib1\.inc"', statements[1], re.IGNORECASE):
        raise HybridParseError('second statement must include "qelib1.inc"')
    if not any(re.match(r"qreg\s+", item, re.IGNORECASE) for item in statements[2:]):
        raise HybridParseError("Hybrid-QASM must declare a quantum register")
    if not any(re.match(r"creg\s+", item, re.IGNORECASE) for item in statements[2:]):
        raise HybridParseError("Hybrid-QASM must declare a classical register")
    return [item + ";" for item in statements if not _DECLARATION_RE.fullmatch(item)]


def _lex_classical(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    symbols = {
        "{": "LBRACE",
        "}": "RBRACE",
        "(": "LPAREN",
        ")": "RPAREN",
        "[": "LBRACKET",
        "]": "RBRACKET",
        ";": "SEMI",
        "=": "ASSIGN",
        "+": "PLUS",
        "-": "MINUS",
    }
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
            continue
        if source.startswith("==", index):
            tokens.append(_Token("EQ", "==", index))
            index += 2
            continue
        if source.startswith("!=", index):
            tokens.append(_Token("NE", "!=", index))
            index += 2
            continue
        if char in symbols:
            tokens.append(_Token(symbols[char], char, index))
            index += 1
            continue
        if char.isdigit():
            end = index + 1
            while end < len(source) and source[end].isdigit():
                end += 1
            tokens.append(_Token("INT", source[index:end], index))
            index = end
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < len(source) and (source[end].isalnum() or source[end] == "_"):
                end += 1
            value = source[index:end]
            keyword = value.lower()
            kind = "IF" if keyword == "if" else "ELSE" if keyword == "else" else "ID"
            tokens.append(_Token(kind, value, index))
            index = end
            continue
        raise HybridParseError(f"unsupported classical character `{char}` at offset {index}")
    tokens.append(_Token("EOF", "", len(source)))
    return tokens


class _ClassicalParser:
    def __init__(self, source: str):
        self.tokens = _lex_classical(source)
        self.index = 0
        self.measurement_indices: set[int] = set()

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def _take(self, kind: str) -> _Token:
        token = self.current
        if token.kind != kind:
            raise HybridParseError(
                f"expected {kind}, found `{token.value or token.kind}` at offset {token.position}"
            )
        self.index += 1
        return token

    def parse(self) -> tuple[tuple[Stmt, ...], frozenset[int]]:
        statements = self._statements("EOF")
        self._take("EOF")
        return statements, frozenset(self.measurement_indices)

    def _statements(self, stop: str) -> tuple[Stmt, ...]:
        statements: list[Stmt] = []
        while self.current.kind != stop:
            if self.current.kind == "EOF":
                raise HybridParseError(f"expected {stop} before end of classical block")
            statements.append(self._if_statement() if self.current.kind == "IF" else self._assignment())
        return tuple(statements)

    def _block(self) -> tuple[Stmt, ...]:
        self._take("LBRACE")
        statements = self._statements("RBRACE")
        self._take("RBRACE")
        return statements

    def _if_statement(self) -> IfStmt:
        self._take("IF")
        self._take("LPAREN")
        left = self._expr()
        operator = self.current
        if operator.kind not in {"EQ", "NE"}:
            raise HybridParseError("if condition must use == or !=")
        self.index += 1
        right = self._expr()
        self._take("RPAREN")
        then_body = self._block()
        self._take("ELSE")
        else_body = self._block()
        return IfStmt(Condition(operator.value, left, right), then_body, else_body)

    def _register_index(self, token: _Token) -> int:
        match = _REGISTER_RE.fullmatch(token.value)
        if match is None:
            raise HybridParseError(f"expected r1..r9, found `{token.value}`")
        return int(match.group(1))

    def _assignment(self) -> Assign:
        target = self._register_index(self._take("ID"))
        self._take("ASSIGN")
        value = self._expr()
        self._take("SEMI")
        return Assign(target, value)

    def _expr(self) -> Expr:
        expression = self._factor()
        while self.current.kind in {"PLUS", "MINUS"}:
            operator = self.current.value
            self.index += 1
            expression = BinaryExpr(operator, expression, self._factor())
        return expression

    def _factor(self) -> Expr:
        token = self.current
        if token.kind in {"PLUS", "MINUS"}:
            self.index += 1
            factor = self._factor()
            if token.kind == "PLUS":
                return factor
            if isinstance(factor, IntLiteral):
                return IntLiteral(-factor.value)
            return BinaryExpr("-", IntLiteral(0), factor)
        if token.kind == "INT":
            self.index += 1
            return IntLiteral(int(token.value))
        if token.kind == "LPAREN":
            self.index += 1
            expression = self._expr()
            self._take("RPAREN")
            return expression
        if token.kind != "ID":
            raise HybridParseError(f"expected expression at offset {token.position}")
        self.index += 1
        register = _REGISTER_RE.fullmatch(token.value)
        if register is not None:
            return RegisterRef(int(register.group(1)))
        if token.value.lower() != "c":
            raise HybridParseError(f"unknown classical name `{token.value}`")
        self._take("LBRACKET")
        raw_index = self._take("INT")
        self._take("RBRACKET")
        measurement_index = int(raw_index.value)
        if measurement_index > 21:
            raise HybridParseError("measurement c[k] cannot map beyond RISC-V x31")
        self.measurement_indices.add(measurement_index)
        return MeasurementRef(measurement_index)


def parse_hybrid(source: str) -> HybridProgram:
    """Parse Hybrid-QASM without evaluating or executing source text."""

    if not isinstance(source, str):
        raise HybridParseError("Hybrid-QASM source must be a string")
    cleaned = _strip_comments(source)
    quantum_source, classical_bodies = _split_hybrid(cleaned)
    quantum_ops = tuple(_qasm_statements(quantum_source))
    statements: list[Stmt] = []
    measurement_indices: set[int] = set()
    for body in classical_bodies:
        parsed, measured = _ClassicalParser(body).parse()
        statements.extend(parsed)
        measurement_indices.update(measured)
    if not statements:
        raise HybridParseError("classical blocks must contain at least one statement")
    return HybridProgram(quantum_ops, tuple(statements), frozenset(measurement_indices))
