"""Parser for Hybrid-QASM — produces quantum ops list + classical AST."""
from dataclasses import dataclass, field
from typing import List, Optional, Union
from .lexer import Lexer, Token, TokenType


@dataclass
class NumberExpr:
    value: int


@dataclass
class RegisterExpr:
    name: str  # r1..r9
    index: int  # 1..9


@dataclass
class ClbitExpr:
    index: int  # c[0] → index 0, maps to x10


@dataclass
class BinaryOp:
    op: str  # "+", "-"
    left: 'Expr'
    right: 'Expr'


@dataclass
class Assignment:
    target: RegisterExpr
    value: 'Expr'


@dataclass
class IfStatement:
    condition_left: Union[ClbitExpr, RegisterExpr, NumberExpr]
    condition_right: Union[ClbitExpr, RegisterExpr, NumberExpr]
    cmp_op: str  # "==" or "!="
    then_body: list  # list of statements
    else_body: list  # list of statements


@dataclass
class QuantumOp:
    name: str
    qubits: list
    params: list
    is_measure: bool = False
    measure_clbit: int = -1


Expr = Union[NumberExpr, RegisterExpr, ClbitExpr, BinaryOp]


class HybridQASMParser:
    def __init__(self, tokens: list):
        self.tokens = tokens
        self.pos = 0

    def parse(self):
        quantum_ops = []
        classical_stmts = []

        while self._peek().type != TokenType.EOF:
            tok = self._peek()
            if tok.type in (TokenType.QASM_HEADER, TokenType.INCLUDE):
                self._skip_statement()
            elif tok.type == TokenType.QREG:
                self._skip_statement()
            elif tok.type == TokenType.CREG:
                self._skip_statement()
            elif tok.type == TokenType.MEASURE:
                op = self._parse_measure()
                quantum_ops.append(op)
            elif tok.type == TokenType.CLASSICAL:
                self._expect(TokenType.CLASSICAL)
                self._expect(TokenType.LBRACE)
                classical_stmts = self._parse_block()
                self._expect(TokenType.RBRACE)
            elif tok.type == TokenType.IDENT:
                op = self._parse_gate()
                quantum_ops.append(op)
            else:
                self._advance()

        return quantum_ops, classical_stmts

    def _parse_gate(self) -> QuantumOp:
        name_tok = self._expect(TokenType.IDENT)
        gate_name = name_tok.value.lower()

        params = []
        if self._peek().type == TokenType.LPAREN:
            self._expect(TokenType.LPAREN)
            param_parts = []
            while self._peek().type != TokenType.RPAREN:
                tok = self._advance()
                if tok.type == TokenType.COMMA:
                    param_parts.append("__SEP__")
                else:
                    param_parts.append(tok.value)
            self._expect(TokenType.RPAREN)
            param_str = " ".join(param_parts)
            for part in param_str.split("__SEP__"):
                part = part.strip()
                if part:
                    try:
                        val = float(eval(part, {"__builtins__": {"pi": 3.141592653589793}}, {}))
                        params.append(val)
                    except Exception:
                        params.append(float(part))

        qubits = []
        while True:
            if self._peek().type == TokenType.IDENT:
                self._advance()
                self._expect(TokenType.LBRACKET)
                idx = self._expect(TokenType.NUMBER)
                self._expect(TokenType.RBRACKET)
                qubits.append(int(float(idx.value)))
            if self._peek().type == TokenType.COMMA:
                self._advance()
                continue
            break
        self._expect(TokenType.SEMICOLON)
        return QuantumOp(name=gate_name, qubits=qubits, params=params)

    def _parse_measure(self) -> QuantumOp:
        self._expect(TokenType.MEASURE)
        self._expect(TokenType.IDENT)
        self._expect(TokenType.LBRACKET)
        q_idx = self._expect(TokenType.NUMBER)
        self._expect(TokenType.RBRACKET)
        self._expect(TokenType.ARROW)
        self._expect(TokenType.IDENT)
        self._expect(TokenType.LBRACKET)
        c_idx = self._expect(TokenType.NUMBER)
        self._expect(TokenType.RBRACKET)
        self._expect(TokenType.SEMICOLON)
        return QuantumOp(
            name="measure",
            qubits=[int(float(q_idx.value))],
            params=[],
            is_measure=True,
            measure_clbit=int(float(c_idx.value)),
        )

    def _parse_block(self) -> list:
        stmts = []
        while self._peek().type not in (TokenType.RBRACE, TokenType.EOF):
            if self._peek().type == TokenType.IF:
                stmts.append(self._parse_if())
            elif self._peek().type == TokenType.REGISTER:
                stmts.append(self._parse_assignment())
            elif self._peek().type == TokenType.SEMICOLON:
                self._advance()
            else:
                self._advance()
        return stmts

    def _parse_if(self) -> IfStatement:
        self._expect(TokenType.IF)
        self._expect(TokenType.LPAREN)

        left = self._parse_condition_operand()
        cmp = self._peek()
        if cmp.type == TokenType.EQ:
            cmp_op = "=="
        elif cmp.type == TokenType.NEQ:
            cmp_op = "!="
        else:
            raise SyntaxError(f"Expected == or !=, got {cmp}")
        self._advance()
        right = self._parse_condition_operand()

        self._expect(TokenType.RPAREN)
        self._expect(TokenType.LBRACE)
        then_body = self._parse_block()
        self._expect(TokenType.RBRACE)

        else_body = []
        if self._peek().type == TokenType.ELSE:
            self._expect(TokenType.ELSE)
            self._expect(TokenType.LBRACE)
            else_body = self._parse_block()
            self._expect(TokenType.RBRACE)

        return IfStatement(
            condition_left=left,
            condition_right=right,
            cmp_op=cmp_op,
            then_body=then_body,
            else_body=else_body,
        )

    def _parse_condition_operand(self):
        tok = self._peek()
        if tok.type == TokenType.NUMBER:
            self._advance()
            return NumberExpr(int(float(tok.value)))
        elif tok.type == TokenType.REGISTER:
            self._advance()
            return RegisterExpr(tok.value, int(tok.value[1:]))
        elif tok.type == TokenType.IDENT:
            self._advance()
            if self._peek().type == TokenType.LBRACKET:
                self._expect(TokenType.LBRACKET)
                idx = self._expect(TokenType.NUMBER)
                self._expect(TokenType.RBRACKET)
                return ClbitExpr(int(float(idx.value)))
            return RegisterExpr(tok.value, 0)
        raise SyntaxError(f"Unexpected token in condition: {tok}")

    def _parse_assignment(self) -> Assignment:
        reg_tok = self._expect(TokenType.REGISTER)
        target = RegisterExpr(reg_tok.value, int(reg_tok.value[1:]))
        self._expect(TokenType.ASSIGN)
        value = self._parse_expr()
        self._expect(TokenType.SEMICOLON)
        return Assignment(target=target, value=value)

    def _parse_expr(self) -> Expr:
        left = self._parse_primary()
        while self._peek().type in (TokenType.PLUS, TokenType.MINUS):
            op_tok = self._advance()
            right = self._parse_primary()
            op = "+" if op_tok.type == TokenType.PLUS else "-"
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_primary(self) -> Expr:
        tok = self._peek()
        if tok.type == TokenType.NUMBER:
            self._advance()
            return NumberExpr(int(float(tok.value)))
        elif tok.type == TokenType.REGISTER:
            self._advance()
            return RegisterExpr(tok.value, int(tok.value[1:]))
        elif tok.type == TokenType.IDENT:
            self._advance()
            if self._peek().type == TokenType.LBRACKET:
                self._expect(TokenType.LBRACKET)
                idx = self._expect(TokenType.NUMBER)
                self._expect(TokenType.RBRACKET)
                return ClbitExpr(int(float(idx.value)))
            return RegisterExpr(tok.value, 0)
        elif tok.type == TokenType.MINUS:
            self._advance()
            inner = self._parse_primary()
            return BinaryOp(op="-", left=NumberExpr(0), right=inner)
        raise SyntaxError(f"Unexpected token in expression: {tok}")

    def _skip_statement(self):
        while self._peek().type not in (TokenType.SEMICOLON, TokenType.EOF):
            self._advance()
        if self._peek().type == TokenType.SEMICOLON:
            self._advance()

    def _expect(self, ttype: TokenType) -> Token:
        tok = self._peek()
        if tok.type != ttype:
            raise SyntaxError(f"Expected {ttype.name}, got {tok.type.name} ('{tok.value}') at line {tok.line}")
        self._advance()
        return tok

    def _peek(self, offset=0) -> Token:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else Token(TokenType.EOF, "", 0, 0)

    def _advance(self) -> Token:
        tok = self._peek()
        self.pos += 1
        return tok
