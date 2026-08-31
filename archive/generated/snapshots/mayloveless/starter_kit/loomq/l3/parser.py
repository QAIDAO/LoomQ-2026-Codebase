"""Hybrid-QASM 顶层结构与经典子语言递归下降 parser。"""

import re
from typing import List, Sequence, Tuple

from .ast import (
    Assignment,
    BinaryExpr,
    ClassicalBitRef,
    Comparison,
    Expression,
    IfElse,
    IntegerLiteral,
    Program,
    RegisterRef,
    Statement,
)
from .lexer import HybridQASMError, Token, tokenize


_REGISTER_RE = re.compile(r"r([0-9]+)\Z")


class HybridParser:
    def __init__(self, source: str) -> None:
        self.tokens = tokenize(source)
        self.position = 0
        self.classical_bit_count = -1
        self.classical_blocks = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.position]

    def error(self, message: str, token: Token = None) -> HybridQASMError:
        item = self.current if token is None else token
        return HybridQASMError(
            "line %d, column %d: %s" % (item.line, item.column, message)
        )

    def advance(self) -> Token:
        token = self.current
        if token.kind != "EOF":
            self.position += 1
        return token

    def match(self, value: str) -> bool:
        if self.current.value == value:
            self.advance()
            return True
        return False

    def expect(self, value: str) -> Token:
        if self.current.value != value:
            raise self.error("expected %r, found %r" % (value, self.current.value))
        return self.advance()

    def parse(self) -> Program:
        quantum_operations: List[str] = []
        statements: Tuple[Statement, ...] = ()
        saw_openqasm = False

        while self.current.kind != "EOF":
            if self.current.value == "classical":
                if self.classical_blocks:
                    raise self.error("only one classical block is allowed")
                self.advance()
                statements = self.parse_block()
                self.classical_blocks += 1
                self.match(";")
                continue

            statement_tokens = self.parse_top_level_statement()
            first = statement_tokens[0]
            keyword = first.value.lower() if first.kind == "IDENT" else ""
            if not saw_openqasm and keyword != "openqasm":
                raise self.error("OPENQASM 2.0 declaration must be first", first)
            if keyword == "openqasm":
                if saw_openqasm:
                    raise self.error("duplicate OPENQASM declaration", first)
                self.validate_openqasm(statement_tokens)
                saw_openqasm = True
            elif keyword == "creg":
                self.record_creg(statement_tokens)
            elif keyword == "qreg":
                self.validate_register_declaration(statement_tokens, "qreg")
            elif keyword == "include":
                self.validate_include(statement_tokens)
            else:
                if first.kind != "IDENT":
                    raise self.error("quantum operation must start with a gate name", first)
                quantum_operations.append(format_quantum_statement(statement_tokens))

        if not saw_openqasm:
            raise self.error("missing OPENQASM 2.0 declaration")
        if not self.classical_blocks:
            raise self.error("missing classical block")
        if self.classical_bit_count < 0:
            raise self.error("missing creg c declaration")

        program = Program(
            quantum_operations=tuple(quantum_operations),
            statements=statements,
            classical_bit_count=self.classical_bit_count,
        )
        self.validate_classical_bits(program.statements)
        return program

    def parse_top_level_statement(self) -> List[Token]:
        start = self.current
        result: List[Token] = []
        paren_depth = 0
        bracket_depth = 0
        while self.current.kind != "EOF":
            token = self.advance()
            if token.value == "{":
                raise self.error("unexpected '{' outside classical block", token)
            if token.value == "}":
                raise self.error("unexpected '}' outside classical block", token)
            if token.value == "(":
                paren_depth += 1
            elif token.value == ")":
                paren_depth -= 1
            elif token.value == "[":
                bracket_depth += 1
            elif token.value == "]":
                bracket_depth -= 1
            if paren_depth < 0 or bracket_depth < 0:
                raise self.error("unbalanced delimiter", token)
            if token.value == ";" and paren_depth == 0 and bracket_depth == 0:
                if not result:
                    raise self.error("empty top-level statement", start)
                return result
            result.append(token)
        raise self.error("top-level statement is missing ';'", start)

    def validate_openqasm(self, tokens: Sequence[Token]) -> None:
        values = [token.value for token in tokens]
        if values != ["OPENQASM", "2.0"]:
            raise self.error("expected exact 'OPENQASM 2.0;' declaration", tokens[0])

    def record_creg(self, tokens: Sequence[Token]) -> None:
        name, size = self.validate_register_declaration(tokens, "creg")
        if name != "c":
            return
        if size > 22:
            raise self.error("creg c exceeds RISC-V mapping x10..x31", tokens[3])
        if self.classical_bit_count >= 0:
            raise self.error("duplicate creg c declaration", tokens[1])
        self.classical_bit_count = size

    def validate_register_declaration(
        self, tokens: Sequence[Token], kind: str
    ) -> Tuple[str, int]:
        values = [token.value for token in tokens]
        if len(values) != 5 or values[2] != "[" or values[4] != "]":
            raise self.error("malformed %s declaration" % kind, tokens[0])
        if tokens[1].kind != "IDENT" or tokens[3].kind != "INTEGER":
            raise self.error("malformed %s declaration" % kind, tokens[0])
        size = int(values[3])
        if size <= 0:
            raise self.error("%s size must be positive" % kind, tokens[3])
        return values[1], size

    def validate_include(self, tokens: Sequence[Token]) -> None:
        if len(tokens) != 2 or tokens[1].kind != "STRING":
            raise self.error("malformed include declaration", tokens[0])

    def parse_block(self) -> Tuple[Statement, ...]:
        self.expect("{")
        result: List[Statement] = []
        while self.current.value != "}":
            if self.current.kind == "EOF":
                raise self.error("unterminated classical block")
            result.append(self.parse_statement())
        self.advance()
        return tuple(result)

    def parse_statement(self) -> Statement:
        if self.current.value == "if":
            return self.parse_if_else()
        target = self.parse_register()
        self.expect("=")
        expression = self.parse_expression()
        self.expect(";")
        return Assignment(target, expression)

    def parse_if_else(self) -> IfElse:
        self.expect("if")
        self.expect("(")
        left = self.parse_expression()
        if self.current.value not in ("==", "!="):
            raise self.error("condition requires '==' or '!='")
        operator = self.advance().value
        right = self.parse_expression()
        self.expect(")")
        then_body = self.parse_block()
        self.expect("else")
        else_body = self.parse_block()
        return IfElse(Comparison(operator, left, right), then_body, else_body)

    def parse_expression(self) -> Expression:
        expression = self.parse_unary()
        while self.current.value in ("+", "-"):
            operator = self.advance().value
            expression = BinaryExpr(operator, expression, self.parse_unary())
        return expression

    def parse_unary(self) -> Expression:
        if self.match("+"):
            return self.parse_unary()
        if self.match("-"):
            operand = self.parse_unary()
            if isinstance(operand, IntegerLiteral):
                return IntegerLiteral(-operand.value)
            return BinaryExpr("-", IntegerLiteral(0), operand)
        if self.match("("):
            expression = self.parse_expression()
            self.expect(")")
            return expression
        if self.current.kind == "INTEGER":
            return IntegerLiteral(int(self.advance().value))
        if self.current.value == "c":
            self.advance()
            self.expect("[")
            if self.current.kind != "INTEGER":
                raise self.error("classical bit index must be a non-negative integer")
            index = int(self.advance().value)
            self.expect("]")
            return ClassicalBitRef(index)
        if self.current.kind == "IDENT":
            return self.parse_register()
        raise self.error("expected integer, r1..r9, c[k], or parenthesized expression")

    def parse_register(self) -> RegisterRef:
        token = self.current
        if token.kind != "IDENT":
            raise self.error("assignment target must be r1..r9")
        match = _REGISTER_RE.fullmatch(token.value)
        if match is None:
            raise self.error("unknown classical identifier %r" % token.value)
        self.advance()
        index = int(match.group(1))
        if not 1 <= index <= 9:
            raise self.error("register %r is outside r1..r9" % token.value, token)
        return RegisterRef(index)

    def validate_classical_bits(self, statements: Sequence[Statement]) -> None:
        def check_expression(expression: Expression) -> None:
            if isinstance(expression, ClassicalBitRef):
                if expression.index >= self.classical_bit_count:
                    raise HybridQASMError(
                        "classical bit c[%d] is outside declared creg c[%d]"
                        % (expression.index, self.classical_bit_count)
                    )
            elif isinstance(expression, BinaryExpr):
                check_expression(expression.left)
                check_expression(expression.right)

        for statement in statements:
            if isinstance(statement, Assignment):
                check_expression(statement.expression)
            else:
                check_expression(statement.condition.left)
                check_expression(statement.condition.right)
                self.validate_classical_bits(statement.then_body)
                self.validate_classical_bits(statement.else_body)


def format_quantum_statement(tokens: Sequence[Token]) -> str:
    """将量子语句归一化为空白稳定、信息无损的单行文本。"""
    output = ""
    previous = ""
    for token in tokens:
        value = token.value
        if value in ("]", ")"):
            output = output.rstrip() + value
        elif value in ("[", "("):
            if value == "(" and previous in ("]", ")"):
                output += " "
            output = output.rstrip() + value
        elif value == ",":
            output = output.rstrip() + ", "
        elif value in ("+", "-", "*", "/", "==", "!=", "->"):
            output = output.rstrip() + " " + value + " "
        else:
            if output and not output.endswith((" ", "[", "(")):
                output += " "
            output += value
        previous = value
    return output.strip() + ";"


def parse_hybrid(source: str) -> Program:
    """解析完整 Hybrid-QASM 程序。"""
    return HybridParser(source).parse()
