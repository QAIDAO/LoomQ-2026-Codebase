#!/usr/bin/env python3
"""Recursive-descent parser: OpenQASM 2.0 (+ classical blocks) -> Program.

Unlike line-regex front-ends, this parser is token-driven and therefore
indifferent to whitespace/newlines/comments; it accepts arbitrary register
names (not just q/c), register-broadcast gate calls, nested parenthesised
parameter expressions, and inline `classical { ... }` blocks — the same
front-end serves L1 parsing and L3 hybrid compilation.
"""

from __future__ import annotations

from typing import Optional

try:
    from .lexer import LexError, Token, TokenStream, tokenize
    from .ir import (Assign, Binary, BitRef, ClassicalBlock, Condition,
                     Func, GateCall, IfBlock, MeasureBits, MeasureReg, Num,
                     Pi, Program, RegDecl, RegRef, Unary, WholeReg)
except ImportError:
    from lexer import LexError, Token, TokenStream, tokenize
    from ir import (Assign, Binary, BitRef, ClassicalBlock, Condition,
                    Func, GateCall, IfBlock, MeasureBits, MeasureReg, Num,
                    Pi, Program, RegDecl, RegRef, Unary, WholeReg)


class ParseError(ValueError):
    pass


def _fail(message: str, token: Optional[Token]) -> "ParseError":
    if token is None:
        return ParseError("unexpected end of input: %s" % message)
    return ParseError("line %d col %d: %s" % (token.line, token.col, message))


def _validate_gate_call(call: GateCall, gate_table) -> None:
    definition = gate_table.get(call.gate)
    if definition is None:
        raise ParseError("gate %r is outside the 12-gate whitelist" % call.gate)
    if len(call.params) != definition.n_params:
        raise _fail("%s expects %d parameter(s), got %d"
                    % (call.gate, definition.n_params, len(call.params)),
                    None)
    if len(call.qubits) != definition.n_qubits:
        raise ParseError("%s acts on %d qubit(s), got %d"
                         % (call.gate, definition.n_qubits, len(call.qubits)))


class Parser:
    def __init__(self, source: str, gate_table: dict):
        self.stream = TokenStream(tokenize(source))
        self.gates = gate_table
        self.program = Program()

    # ---- helpers ----------------------------------------------------------

    def _peek(self) -> Optional[Token]:
        return self.stream.peek()

    def _next(self) -> Token:
        try:
            return self.stream.next()
        except LexError as exc:
            raise ParseError(str(exc)) from exc

    def _accept(self, symbol: str) -> bool:
        return self.stream.accept_sym(symbol) is not None

    def _expect(self, symbol: str) -> None:
        try:
            self.stream.expect_sym(symbol)
        except LexError as exc:
            raise ParseError(str(exc)) from exc

    def _keyword(self, *names: str) -> Optional[str]:
        token = self._peek()
        if token is not None and token.kind == "id":
            lowered = token.value.lower()
            if lowered in names:
                self.stream.pos += 1
                return lowered
        return None

    def _identifier(self, *reserved: str) -> str:
        token = self._peek()
        if token is None or token.kind != "id":
            raise _fail("expected an identifier", token)
        name = token.value
        if reserved and name.lower() in reserved:
            raise _fail("%r is a reserved word" % name, token)
        self.stream.pos += 1
        return name

    def _integer_literal(self) -> int:
        token = self._peek()
        if token is None or token.kind != "num":
            raise _fail("expected an integer literal", token)
        value = token.number
        if value != int(value):
            raise _fail("expected an integer literal", token)
        self.stream.pos += 1
        return int(value)

    # ---- expressions ------------------------------------------------------

    def parse_expression(self) -> object:
        return self._additive()

    def _additive(self):
        node = self._multiplicative()
        while True:
            if self._accept("+"):
                node = Binary("+", node, self._multiplicative())
            elif self._accept("-"):
                node = Binary("-", node, self._multiplicative())
            else:
                return node

    def _multiplicative(self):
        node = self._unary()
        while True:
            if self._accept("*"):
                node = Binary("*", node, self._unary())
            elif self._accept("/"):
                node = Binary("/", node, self._unary())
            else:
                return node

    def _unary(self):
        if self._accept("-"):
            return Unary("-", self._unary())
        if self._accept("+"):
            return Unary("+", self._unary())
        return self._atom()

    def _atom(self):
        token = self._peek()
        if token is None:
            raise _fail("expected an expression", None)
        if token.is_sym("("):
            self.stream.pos += 1
            inner = self.parse_expression()
            self._expect(")")
            return inner
        if token.kind == "num":
            self.stream.pos += 1
            return Num(token.number)
        if token.kind == "id":
            lowered = token.value.lower()
            if lowered == "pi":
                self.stream.pos += 1
                return Pi()
            if len(lowered) == 2 and lowered[0] == "r" and lowered[1].isdigit():
                number = int(lowered[1])
                if 1 <= number <= 9:
                    self.stream.pos += 1
                    return RegRef(number)
                raise _fail("register index out of range r1..r9", token)
            if lowered in ("cos", "sin", "tan", "exp", "ln", "sqrt"):
                self.stream.pos += 1
                self._expect("(")
                args = [self.parse_expression()]
                while self._accept(","):
                    args.append(self.parse_expression())
                self._expect(")")
                return Func(lowered, tuple(args))
        raise _fail("unsupported expression near %r" % token.value, token)

    # ---- grammar ----------------------------------------------------------

    def parse_program(self) -> Program:
        while True:
            keyword = self._keyword("openqasm")
            if keyword is None:
                break
            self._parse_version_line()
        while True:
            if self._keyword("include") is not None:
                self._consume_include()
                continue
            if not self._parse_statement():
                break
        trailing = self._peek()
        if trailing is not None:
            raise _fail("unexpected input after program body", trailing)
        if not self.program.qregs:
            raise ParseError("program declares no quantum register")
        return self.program

    def _parse_version_line(self) -> None:
        token = self._peek()
        if token is None or token.kind != "num":
            raise _fail("expected version number after OPENQASM", token)
        self.stream.pos += 1
        self._expect(";")

    def _consume_include(self) -> None:
        token = self._peek()
        if token is None or token.kind != "str":
            raise _fail("expected a quoted filename after include", token)
        self.stream.pos += 1
        self._expect(";")

    def _parse_statement(self) -> bool:
        token = self._peek()
        if token is None:
            return False
        if token.is_sym(";"):
            self.stream.pos += 1
            return True
        keyword = token.value.lower() if token.kind == "id" else None
        if keyword == "qreg" or keyword == "creg":
            self.stream.pos += 1
            self._parse_reg_decl(keyword)
            return True
        if keyword == "measure":
            self.stream.pos += 1
            self._parse_measure()
            return True
        if keyword == "barrier":
            self.stream.pos += 1
            self._skip_to_semicolon()
            return True
        if keyword == "opaque":
            raise ParseError("opaque gates are outside the whitelist subset")
        if keyword == "gate":
            raise ParseError("custom gate definitions are outside the whitelist subset")
        if keyword in ("if",):
            raise ParseError("OpenQASM if-statements belong inside a classical block")
        if keyword == "classical":
            self.stream.pos += 1
            self.program.statements.append(self._parse_classical_block())
            return True
        self._parse_gate_call()
        return True

    def _skip_to_semicolon(self) -> None:
        while self._peek() is not None and not self.stream.peek().is_sym(";"):
            self.stream.pos += 1
        self._expect(";")

    def _parse_reg_decl(self, kind: str) -> None:
        name = self._identifier("qreg", "creg", "measure", "classical")
        self._expect("[")
        size = self._integer_literal()
        self._expect("]")
        self._expect(";")
        if size <= 0:
            raise ParseError("register %r must have positive size" % name)
        table = self.program.qregs if kind == "qreg" else self.program.cregs
        if any(r.name == name for r in table):
            raise ParseError("register %r declared twice" % name)
        table.append(RegDecl(name, size))

    def _parse_qubit_arg(self):
        name = self._identifier("qreg", "creg", "measure", "classical")
        token = self._peek()
        if token is not None and token.is_sym("["):
            self.stream.pos += 1
            index = self._integer_literal()
            self._expect("]")
            decl = self.program.qreg(name)
            if decl is None:
                raise ParseError("undeclared quantum register %r" % name)
            if not 0 <= index < decl.size:
                raise ParseError("q[%s] index %d out of range (size %d)"
                                 % (name, index, decl.size))
            return BitRef(name, index)
        if self.program.qreg(name) is None:
            raise ParseError("undeclared quantum register %r" % name)
        return WholeReg(name)

    def _parse_clbit_arg(self) -> BitRef:
        name = self._identifier("qreg", "creg", "measure", "classical")
        self._expect("[")
        index = self._integer_literal()
        self._expect("]")
        decl = self.program.creg(name)
        if decl is None:
            raise ParseError("undeclared classical register %r" % name)
        if not 0 <= index < decl.size:
            raise ParseError("c[%s] index %d out of range (size %d)"
                             % (name, index, decl.size))
        return BitRef(name, index)

    def _parse_measure(self) -> None:
        source = self._parse_qubit_arg()
        arrow = self._peek()
        if arrow is None or not arrow.is_sym("->"):
            raise _fail("expected '->' in measure statement", arrow)
        self.stream.pos += 1
        if isinstance(source, WholeReg):
            target_name = self._identifier("qreg", "creg", "measure", "classical")
            if self.program.creg(target_name) is None:
                raise ParseError("undeclared classical register %r" % target_name)
            self._expect(";")
            self.program.statements.append(MeasureReg(source.reg, target_name))
            return
        target = self._parse_clbit_arg()
        self._expect(";")
        self.program.statements.append(MeasureBits(source, target))

    def _parse_gate_call(self) -> None:
        start = self._peek()
        name_token = self._next()
        gate = name_token.value.lower()
        params: list = []
        if self._accept("("):
            if not self._accept(")"):
                params.append(self.parse_expression())
                while self._accept(","):
                    params.append(self.parse_expression())
                self._expect(")")
        qubits = [self._parse_qubit_arg()]
        while self._accept(","):
            qubits.append(self._parse_qubit_arg())
        self._expect(";")
        call = GateCall(gate, tuple(params), tuple(qubits))
        _validate_gate_call(call, self.gates)
        self.program.statements.append(call)

    # ---- classical mini-language ------------------------------------------

    def _parse_classical_block(self) -> ClassicalBlock:
        self._expect("{")
        body = []
        while True:
            token = self._peek()
            if token is None:
                raise ParseError("unterminated classical block")
            if token.is_sym("}"):
                self.stream.pos += 1
                return ClassicalBlock(tuple(body))
            body.append(self._parse_classical_statement())

    def _parse_classical_statement(self):
        token = self._peek()
        if token is None:
            raise ParseError("unexpected end inside classical block")
        if token.kind == "id" and token.value.lower() == "if":
            return self._parse_if()
        if token.kind == "id" and len(token.value) == 2 and token.value.lower().startswith("r"):
            return self._parse_assign()
        raise _fail("expected assignment or if-statement", token)

    def _register_number(self, token: Token) -> int:
        name = token.value.lower()
        if name[0] != "r" or not name[1:].isdigit():
            raise _fail("unknown register variable %r (expected r1..r9)" % token.value, token)
        number = int(name[1:])
        if not 1 <= number <= 9:
            raise _fail("register index out of range r1..r9", token)
        return number

    def _parse_assign(self) -> Assign:
        reg_token = self._next()
        rid = self._register_number(reg_token)
        assign_op = self._peek()
        if assign_op is None or not assign_op.is_sym("="):
            raise _fail("expected '=' in assignment", assign_op)
        self.stream.pos += 1
        value = self.parse_expression()
        self._expect(";")
        return Assign(rid, value)

    def _parse_condition(self) -> Condition:
        left = self._peek()
        cbit: Optional[BitRef] = None
        literal: Optional[int] = None
        if left is not None and left.kind == "id" and self.program.creg(left.value) is not None:
            reg_name = self._next().value
            self._expect("[")
            index = self._integer_literal()
            self._expect("]")
            size = self.program.creg(reg_name).size
            if not 0 <= index < size:
                raise ParseError("c[%s] index %d out of range (size %d)"
                                 % (reg_name, index, size))
            cbit = BitRef(reg_name, index)
        else:
            literal = self._integer_literal()
        comparator_token = self._peek()
        if comparator_token is None or not comparator_token.is_sym("==", "!="):
            raise _fail("condition must use '==' or '!='", comparator_token)
        comparator = comparator_token.value
        self.stream.pos += 1
        if literal is None:
            literal_token = self._peek()
            literal = self._integer_literal()
            if literal_token.kind == "id":
                raise _fail("comparison operand must be an integer literal", literal_token)
        else:
            token = self._peek()
            if token is None or token.kind != "id" or self.program.creg(token.value) is None:
                raise _fail("the other comparison operand must be c[k]", token)
            reg_name = self._next().value
            self._expect("[")
            index = self._integer_literal()
            self._expect("]")
            cbit = BitRef(reg_name, index)
        return Condition(cbit, comparator, literal)

    def _parse_if(self) -> IfBlock:
        cond_token = self._next()          # consume 'if'
        assert cond_token.value.lower() == "if"
        self._expect("(")
        condition = self._parse_condition()
        self._expect(")")
        then_body = self._parse_classical_block().body
        else_body: tuple = ()
        token = self._peek()
        if token is not None and token.kind == "id" and token.value.lower() == "else":
            self.stream.pos += 1
            nxt = self._peek()
            if nxt is not None and nxt.kind == "id" and nxt.value.lower() == "if":
                self.stream.pos += 1
                else_body = (self._parse_if(),)
            else:
                else_body = self._parse_classical_block().body
        return IfBlock(condition, then_body, else_body)


def parse_source(source: str, gate_table: dict) -> Program:
    """Tokenize + parse `source` into a validated Program."""
    if not isinstance(source, str) or not source.strip():
        raise ParseError("empty program")
    return Parser(source, gate_table).parse_program()


if __name__ == "__main__":
    import sys
    sample = """OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[2];
    creg c[2];
    h q[0];
    cx q[0], q[1];
    measure q -> c;
    """
    from gates import GATES
    print(parse_source(sample, GATES))
