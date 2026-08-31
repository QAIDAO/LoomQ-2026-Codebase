"""Recursive-descent parser for the official Hybrid-QASM mini grammar."""

from __future__ import annotations

from typing import List, Sequence, Tuple

from .ast import (
    Assignment,
    BinaryExpression,
    ClassicalBlock,
    ClassicalStatement,
    Condition,
    Expression,
    HybridProgram,
    IfStatement,
    IntegerLiteral,
    MeasurementReference,
    ProgramSegment,
    QuantumStatement,
    RegisterReference,
    UnaryExpression,
)
from .tokens import HybridLexer, HybridSyntaxError, Token, TokenKind


_NON_OPERATION_DIRECTIVES = frozenset({"openqasm", "include", "qreg", "creg"})


class HybridParser:
    """Parse quantum statements and classical blocks from one token stream."""

    def __init__(self, source: str):
        self._tokens = HybridLexer(source).tokenize()
        self._position = 0
        self._declared_measurements: set[int] = set()

    def parse(self) -> HybridProgram:
        segments: List[ProgramSegment] = []
        while not self._at(TokenKind.EOF):
            if self._at_identifier("classical") and self._peek(1).kind is TokenKind.LBRACE:
                segments.append(self._parse_classical_block())
                # A trailing semicolon is harmless and makes the parser tolerant
                # of block syntax copied from C-like languages.
                self._match(TokenKind.SEMICOLON)
            else:
                segments.append(self._parse_quantum_statement())
        return HybridProgram(tuple(segments), tuple(sorted(self._declared_measurements)))

    def _parse_quantum_statement(self) -> QuantumStatement:
        tokens: List[Token] = []
        while not self._at(TokenKind.SEMICOLON):
            token = self._current()
            if token.kind is TokenKind.EOF:
                self._error(token, "expected ';' after OpenQASM statement")
            if token.kind in (TokenKind.LBRACE, TokenKind.RBRACE):
                self._error(token, "braces are only supported inside a classical block")
            tokens.append(token)
            self._advance()
        semicolon = self._expect(TokenKind.SEMICOLON, "expected ';'")
        tokens.append(semicolon)
        if len(tokens) == 1:
            self._error(semicolon, "empty OpenQASM statement")
        first = tokens[0]
        self._record_measurement_declaration(tokens)
        directive = (
            first.kind is TokenKind.IDENTIFIER
            and first.text.lower() in _NON_OPERATION_DIRECTIVES
        )
        return QuantumStatement(_format_quantum_tokens(tokens), not directive)

    def _record_measurement_declaration(self, tokens: Sequence[Token]) -> None:
        """Reserve every bit in an exact ``creg c[n];`` declaration.

        Even an unreferenced measurement bit may have been injected by the
        evaluator, so using its x-register as scratch state would corrupt the
        architectural input.  Other OpenQASM declarations remain the quantum
        parser's responsibility and are intentionally not interpreted here.
        """

        if not tokens or tokens[0].kind is not TokenKind.IDENTIFIER:
            return
        if tokens[0].text.lower() != "creg":
            return
        expected_kinds = (
            TokenKind.IDENTIFIER,
            TokenKind.IDENTIFIER,
            TokenKind.LBRACKET,
            TokenKind.NUMBER,
            TokenKind.RBRACKET,
            TokenKind.SEMICOLON,
        )
        if tuple(token.kind for token in tokens) != expected_kinds:
            return
        if tokens[1].text != "c" or not tokens[3].text.isdigit():
            return
        size = int(tokens[3].text, 10)
        if size < 1:
            self._error(tokens[3], "creg c size must be positive")
        if size > 22:
            self._error(
                tokens[3],
                "creg c has more than 22 bits; c[22] would map beyond x31",
            )
        self._declared_measurements.update(range(size))

    def _parse_classical_block(self) -> ClassicalBlock:
        self._expect_identifier("classical")
        statements = self._parse_statement_block()
        return ClassicalBlock(statements)

    def _parse_statement_block(self) -> Tuple[ClassicalStatement, ...]:
        self._expect(TokenKind.LBRACE, "expected '{' to start classical block")
        statements: List[ClassicalStatement] = []
        while not self._at(TokenKind.RBRACE):
            if self._at(TokenKind.EOF):
                self._error(self._current(), "unterminated classical block")
            statements.append(self._parse_classical_statement())
        self._advance()
        return tuple(statements)

    def _parse_classical_statement(self) -> ClassicalStatement:
        if self._at_identifier("if"):
            return self._parse_if_statement()
        return self._parse_assignment()

    def _parse_assignment(self) -> Assignment:
        target_token = self._expect(
            TokenKind.IDENTIFIER, "expected r1..r9 assignment target or 'if'"
        )
        target = self._register_from_token(target_token)
        self._expect(TokenKind.ASSIGN, "expected '=' in assignment")
        value = self._parse_expression()
        self._expect(TokenKind.SEMICOLON, "expected ';' after assignment")
        return Assignment(target, value)

    def _parse_if_statement(self) -> IfStatement:
        self._expect_identifier("if")
        self._expect(TokenKind.LPAREN, "expected '(' after 'if'")
        condition = self._parse_condition()
        self._expect(TokenKind.RPAREN, "expected ')' after if condition")
        then_body = self._parse_statement_block()
        else_body: Tuple[ClassicalStatement, ...] = ()
        has_else = False
        if self._at_identifier("else"):
            self._advance()
            has_else = True
            if self._at_identifier("if"):
                else_body = (self._parse_if_statement(),)
            else:
                else_body = self._parse_statement_block()
        return IfStatement(condition, then_body, else_body, has_else)

    def _parse_condition(self) -> Condition:
        left = self._parse_expression()
        operator = self._current()
        if operator.kind not in (TokenKind.EQUAL, TokenKind.NOT_EQUAL):
            self._error(operator, "expected '==' or '!=' in condition")
        self._advance()
        right = self._parse_expression()
        return Condition(operator.text, left, right)

    def _parse_expression(self) -> Expression:
        """Parse left-associative addition and subtraction."""

        expression = self._parse_unary()
        while self._current().kind in (TokenKind.PLUS, TokenKind.MINUS):
            operator = self._advance().text
            right = self._parse_unary()
            expression = BinaryExpression(operator, expression, right)
        return expression

    def _parse_unary(self) -> Expression:
        if self._current().kind in (TokenKind.PLUS, TokenKind.MINUS):
            operator = self._advance().text
            return UnaryExpression(operator, self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self) -> Expression:
        token = self._current()
        if token.kind is TokenKind.NUMBER:
            self._advance()
            if not token.text.isdigit():
                self._error(token, "classical literals must be decimal integers")
            return IntegerLiteral(int(token.text, 10))
        if token.kind is TokenKind.IDENTIFIER:
            if token.text == "c":
                return self._parse_measurement_reference()
            self._advance()
            return self._register_from_token(token)
        if self._match(TokenKind.LPAREN):
            expression = self._parse_expression()
            self._expect(TokenKind.RPAREN, "expected ')' after expression")
            return expression
        self._error(token, "expected integer, r1..r9, c[k], or parenthesized expression")
        raise AssertionError("unreachable")

    def _parse_measurement_reference(self) -> MeasurementReference:
        c_token = self._expect_identifier("c")
        self._expect(TokenKind.LBRACKET, "expected '[' after 'c'")
        index_token = self._expect(TokenKind.NUMBER, "expected measurement bit index")
        if not index_token.text.isdigit():
            self._error(index_token, "measurement bit index must be a non-negative integer")
        self._expect(TokenKind.RBRACKET, "expected ']' after measurement bit index")
        index = int(index_token.text, 10)
        if index > 21:
            self._error(
                c_token,
                f"c[{index}] maps beyond x31; supported measurement indices are 0..21",
            )
        return MeasurementReference(index)

    def _register_from_token(self, token: Token) -> RegisterReference:
        text = token.text
        if len(text) == 2 and text[0] == "r" and text[1] in "123456789":
            return RegisterReference(int(text[1]))
        self._error(token, "expected classical register r1..r9")
        raise AssertionError("unreachable")

    def _current(self) -> Token:
        return self._tokens[self._position]

    def _peek(self, offset: int) -> Token:
        position = min(self._position + offset, len(self._tokens) - 1)
        return self._tokens[position]

    def _advance(self) -> Token:
        token = self._current()
        if token.kind is not TokenKind.EOF:
            self._position += 1
        return token

    def _at(self, kind: TokenKind) -> bool:
        return self._current().kind is kind

    def _at_identifier(self, text: str) -> bool:
        token = self._current()
        return token.kind is TokenKind.IDENTIFIER and token.text == text

    def _match(self, kind: TokenKind) -> bool:
        if self._at(kind):
            self._advance()
            return True
        return False

    def _expect(self, kind: TokenKind, message: str) -> Token:
        token = self._current()
        if token.kind is not kind:
            self._error(token, message)
        return self._advance()

    def _expect_identifier(self, text: str) -> Token:
        token = self._current()
        if not self._at_identifier(text):
            self._error(token, f"expected {text!r}")
        return self._advance()

    @staticmethod
    def _error(token: Token, message: str) -> None:
        found = "end of input" if token.kind is TokenKind.EOF else repr(token.text)
        raise HybridSyntaxError(
            f"line {token.line}, column {token.column}: {message}; found {found}"
        )


def _format_quantum_tokens(tokens: Sequence[Token]) -> str:
    """Serialize one quantum-side statement with deterministic whitespace."""

    output = ""
    previous: Token | None = None
    operators = {
        TokenKind.PLUS,
        TokenKind.MINUS,
        TokenKind.STAR,
        TokenKind.SLASH,
        TokenKind.ASSIGN,
        TokenKind.EQUAL,
        TokenKind.NOT_EQUAL,
        TokenKind.ARROW,
    }
    for token in tokens:
        kind = token.kind
        if kind is TokenKind.SEMICOLON:
            output = output.rstrip() + ";"
        elif kind is TokenKind.COMMA:
            output = output.rstrip() + ", "
        elif kind in (TokenKind.RPAREN, TokenKind.RBRACKET):
            output = output.rstrip() + token.text
        elif kind is TokenKind.LBRACKET:
            output = output.rstrip() + "["
        elif kind is TokenKind.LPAREN:
            if previous is not None and previous.kind is TokenKind.IDENTIFIER:
                output = output.rstrip() + "("
            else:
                output = output.rstrip() + " ("
        elif kind in operators:
            unary_sign = kind in (TokenKind.PLUS, TokenKind.MINUS) and (
                previous is None
                or previous.kind
                in operators
                | {TokenKind.LPAREN, TokenKind.LBRACKET, TokenKind.COMMA}
            )
            if unary_sign:
                output = output.rstrip() + token.text + " "
            else:
                output = output.rstrip() + f" {token.text} "
        else:
            if output and not output.endswith((" ", "(", "[")):
                output += " "
            output += token.text
        previous = token
    return output.strip()


def parse_hybrid_program(source: str) -> HybridProgram:
    """Parse *source* into an immutable :class:`HybridProgram`."""

    return HybridParser(source).parse()
