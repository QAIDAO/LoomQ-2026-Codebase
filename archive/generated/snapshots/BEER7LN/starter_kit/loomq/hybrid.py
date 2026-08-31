"""Hybrid-QASM parser and deterministic RISC-V compiler for LoomQ L3."""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Sequence
from .gate_policy import PUBLIC_GATE_ARITY, assert_gate_names
from .qasm import GateOperation, MeasureOperation, QasmParseError, _parse_operation

class HybridQasmError(ValueError):
    pass

@dataclass(frozen=True)
class Integer: value: int
@dataclass(frozen=True)
class RegisterValue: index: int
@dataclass(frozen=True)
class MeasurementValue: index: int
@dataclass(frozen=True)
class Binary: operator: str; left: object; right: object
@dataclass(frozen=True)
class Assign: target: int; expression: object
@dataclass(frozen=True)
class If: operator: str; left: object; right: object; then_body: tuple[object, ...]; else_body: tuple[object, ...]

_TOKEN = re.compile(r"\s*(?:(//[^\n]*)|([A-Za-z_]\w*)|(\d+)|(==|!=|[{}()\[\];=+\-]))")
_QREG = re.compile(r"^qreg\s+([A-Za-z_]\w*)\[(\d+)\]$", re.I)
_CREG = re.compile(r"^creg\s+([A-Za-z_]\w*)\[(\d+)\]$", re.I)
_INDEXED = re.compile(r"^([A-Za-z_]\w*)\[(\d+)\]$")
_EXPECTED = PUBLIC_GATE_ARITY

def compile_hybrid(source: str) -> tuple[list[str], str]:
    operations, creg_size, statements = parse_hybrid(source)
    return operations, _Codegen(creg_size).compile(statements)


def parse_hybrid(source: str) -> tuple[list[str], int, tuple[object, ...]]:
    """Parse Hybrid-QASM once for the compiler and independent test oracle."""

    quantum, classical = _split(source)
    operations, creg_size = _quantum_operations(quantum)
    statements = _Parser(_tokens(classical), creg_size).program()
    return operations, creg_size, statements

def _split(source: str) -> tuple[str, str]:
    if not isinstance(source, str) or not source.strip():
        raise HybridQasmError("Hybrid-QASM source must be non-empty")
    marker = re.search(r"\bclassical\s*\{", source, re.I)
    if marker is None:
        raise HybridQasmError("Hybrid-QASM requires one classical { ... } block")
    depth, pos = 1, marker.end()
    while pos < len(source) and depth:
        # Braces inside line comments are not structural delimiters. The
        # classical lexer already accepts these comments, so splitting must
        # observe the same boundary.
        if source.startswith("//", pos):
            newline = source.find("\n", pos + 2)
            pos = len(source) if newline < 0 else newline + 1
            continue
        if source[pos] == "{": depth += 1
        elif source[pos] == "}": depth -= 1
        pos += 1
    if depth:
        raise HybridQasmError("classical block is missing a closing brace")
    if re.search(r"\bclassical\s*\{", source[pos:], re.I):
        raise HybridQasmError("Hybrid-QASM supports exactly one classical block")
    return source[:marker.start()] + source[pos:], source[marker.end():pos-1]

def _quantum_operations(source: str) -> tuple[list[str], int]:
    text = re.sub(r"//[^\n]*", "", source)
    statements = [piece.strip() for piece in text.split(";")]
    if statements and not statements[-1]: statements.pop()
    if len(statements) < 5 or statements[0].upper() != "OPENQASM 2.0" or statements[1] != 'include "qelib1.inc"':
        raise HybridQasmError("quantum portion must begin with valid OpenQASM 2.0 declarations")
    qmatch, cmatch = _QREG.fullmatch(statements[2]), _CREG.fullmatch(statements[3])
    if qmatch is None or cmatch is None:
        raise HybridQasmError("quantum portion requires qreg then creg declarations")
    qname, qsize = qmatch.group(1), int(qmatch.group(2)); cname, csize = cmatch.group(1), int(cmatch.group(2))
    if qsize < 1 or csize < 1: raise HybridQasmError("register sizes must be positive")
    rendered=[]
    gate_names: list[str] = []
    for statement in statements[4:]:
        try: operation = _parse_operation(statement)
        except QasmParseError as exc: raise HybridQasmError(str(exc)) from exc
        _validate_operation(operation, qname, qsize, cname, csize)
        if isinstance(operation, GateOperation):
            gate_names.append(operation.name)
        rendered.append(_render(operation))
    assert_gate_names(gate_names)
    return rendered, csize

def _validate_operation(operation: GateOperation | MeasureOperation, qname: str, qsize: int, cname: str, csize: int) -> None:
    if isinstance(operation, GateOperation):
        if len(operation.operands) != _EXPECTED[operation.name] or len(set(operation.operands)) != len(operation.operands): raise HybridQasmError("invalid quantum gate operands")
        for operand in operation.operands:
            match=_INDEXED.fullmatch(operand)
            if match is None or match.group(1)!=qname or int(match.group(2))>=qsize: raise HybridQasmError(f"invalid quantum operand: {operand}")
    elif operation.source == qname and operation.destination == cname:
        if qsize != csize: raise HybridQasmError("whole-register measurement requires equal sizes")
    else:
        src,dst=_INDEXED.fullmatch(operation.source),_INDEXED.fullmatch(operation.destination)
        if src is None or dst is None or src.group(1)!=qname or dst.group(1)!=cname or int(src.group(2))>=qsize or int(dst.group(2))>=csize: raise HybridQasmError("invalid measurement operands")

def _render(operation: GateOperation | MeasureOperation) -> str:
    if isinstance(operation, MeasureOperation): return f"measure {operation.source} -> {operation.destination};"
    parameter=f"({operation.parameter})" if operation.parameter is not None else ""
    return f"{operation.name}{parameter} {', '.join(operation.operands)};"

def _tokens(source: str) -> list[str]:
    output=[]; pos=0
    while pos < len(source):
        match=_TOKEN.match(source,pos)
        if match is None:
            if source[pos:].strip(): raise HybridQasmError(f"unexpected classical token near {source[pos:pos+16]!r}")
            break
        pos=match.end()
        if not match.group(1): output.append(match.group(2) or match.group(3) or match.group(4))
    return output

class _Parser:
    def __init__(self,tokens: Sequence[str],creg_size:int): self.tokens=list(tokens); self.creg_size=creg_size; self.pos=0
    def program(self) -> tuple[object,...]:
        body=self.block(None)
        if not body: raise HybridQasmError("classical block must contain a statement")
        return tuple(body)
    def block(self,end:str|None) -> list[object]:
        body=[]
        while self.peek() is not None and self.peek()!=end: body.append(self.statement())
        if end is not None: self.take(end)
        return body
    def statement(self) -> object:
        if self.peek()=="if": return self.if_statement()
        target=self.reg(self.identifier()); self.take("="); expression=self.expression(); self.take(";"); return Assign(target,expression)
    def if_statement(self) -> If:
        self.take("if"); self.take("("); left=self.expression(); operator=self.one("==","!="); right=self.expression(); self.take(")"); self.take("{"); then_body=tuple(self.block("}")); else_body=()
        if self.peek()=="else": self.take("else"); self.take("{"); else_body=tuple(self.block("}"))
        return If(operator,left,right,then_body,else_body)
    def expression(self) -> object:
        value=self.value()
        while self.peek() in {"+","-"}: value=Binary(self.one("+","-"),value,self.value())
        return value
    def value(self) -> object:
        if self.peek()=="(":
            self.take("("); value=self.expression(); self.take(")"); return value
        negative=False
        if self.peek()=="-": self.take("-"); negative=True
        token=self.peek()
        if token is None: raise HybridQasmError("expected expression value")
        if token.isdigit(): self.pos+=1; return Integer(-int(token) if negative else int(token))
        if negative: raise HybridQasmError("unary minus is allowed only on an integer literal")
        name=self.identifier()
        if name=="c":
            self.take("["); index=int(self.number()); self.take("]")
            if index>=self.creg_size: raise HybridQasmError(f"measurement c[{index}] is outside creg")
            return MeasurementValue(index)
        return RegisterValue(self.reg(name))
    def reg(self,name:str)->int:
        match=re.fullmatch(r"r([1-9])",name)
        if match is None: raise HybridQasmError("classical variables must be r1 through r9")
        return int(match.group(1))
    def peek(self): return self.tokens[self.pos] if self.pos<len(self.tokens) else None
    def take(self,expected):
        if self.peek()!=expected: raise HybridQasmError(f"expected {expected!r}, found {self.peek()!r}")
        self.pos+=1
    def one(self,*values):
        token=self.peek()
        if token not in values: raise HybridQasmError(f"expected one of {values!r}, found {token!r}")
        self.pos+=1; return token
    def identifier(self):
        token=self.peek()
        if token is None or re.fullmatch(r"[A-Za-z_]\w*",token) is None: raise HybridQasmError(f"expected identifier, found {token!r}")
        self.pos+=1; return token
    def number(self):
        token=self.peek()
        if token is None or not token.isdigit(): raise HybridQasmError(f"expected integer, found {token!r}")
        self.pos+=1; return token

class _Codegen:
    """Lower additive L3 expressions without reserving measurement inputs."""

    def __init__(self, creg_size: int):
        if creg_size > 22:
            raise HybridQasmError("c[k] maps only through c[21] / x31")
        self.lines: list[str] = []
        self.counter = 0

    def compile(self, statements: Sequence[object]) -> str:
        self._emit_path(tuple(statements), {index: (0, {}) for index in range(1, 10)})
        return "\n".join(self.lines) + "\n"

    def _emit_path(self, statements: tuple[object, ...], environment: dict[int, tuple[int, dict[int, int]]]) -> None:
        environment = self._copy_environment(environment)
        for offset, statement in enumerate(statements):
            if isinstance(statement, Assign):
                environment[statement.target] = self._linear(statement.expression, environment)
                continue

            remainder = statements[offset + 1 :]
            difference = self._combine(
                self._linear(statement.left, environment),
                self._linear(statement.right, environment),
                -1,
            )
            constant, terms = difference
            if not terms:
                equal = constant == 0
                selected = statement.then_body if equal == (statement.operator == "==") else statement.else_body
                self._emit_path(tuple(selected) + remainder, environment)
                return

            label = self.counter
            self.counter += 1
            self._materialize(1, difference)
            branch = "bne" if statement.operator == "==" else "beq"
            self.lines.append(f"{branch} x1, x0, L3_ELSE_{label}")
            self._emit_path(tuple(statement.then_body) + remainder, environment)
            self.lines.append(f"j L3_END_{label}")
            self.lines.append(f"L3_ELSE_{label}:")
            self._emit_path(tuple(statement.else_body) + remainder, environment)
            self.lines.append(f"L3_END_{label}:")
            return

        # The official oracle observes all r1..r9. Rebuilding every register
        # restores x1 after it served as a path-local comparison scratch.
        for register in range(1, 10):
            self._materialize(register, environment[register])

    @staticmethod
    def _copy_environment(environment: dict[int, tuple[int, dict[int, int]]]) -> dict[int, tuple[int, dict[int, int]]]:
        return {register: (constant, dict(terms)) for register, (constant, terms) in environment.items()}

    def _linear(self, value: object, environment: dict[int, tuple[int, dict[int, int]]]) -> tuple[int, dict[int, int]]:
        if isinstance(value, Integer):
            return value.value, {}
        if isinstance(value, RegisterValue):
            constant, terms = environment[value.index]
            return constant, dict(terms)
        if isinstance(value, MeasurementValue):
            return 0, {10 + value.index: 1}
        if isinstance(value, Binary):
            return self._combine(
                self._linear(value.left, environment),
                self._linear(value.right, environment),
                1 if value.operator == "+" else -1,
            )
        raise HybridQasmError("invalid expression node")

    @staticmethod
    def _combine(left: tuple[int, dict[int, int]], right: tuple[int, dict[int, int]], sign: int) -> tuple[int, dict[int, int]]:
        constant, terms = left[0] + sign * right[0], dict(left[1])
        for register, coefficient in right[1].items():
            terms[register] = terms.get(register, 0) + sign * coefficient
            if terms[register] == 0:
                del terms[register]
        return constant, terms

    def _materialize(self, destination: int, value: tuple[int, dict[int, int]]) -> None:
        constant, terms = value
        width = max([abs(constant).bit_length()] + [abs(coefficient).bit_length() for coefficient in terms.values()])
        if width == 0:
            self.lines.append(f"li x{destination}, 0")
            return
        self.lines.append(f"li x{destination}, 0")
        for bit in range(width - 1, -1, -1):
            if bit != width - 1:
                self.lines.append(f"add x{destination}, x{destination}, x{destination}")
            if (abs(constant) >> bit) & 1:
                self.lines.append(f"addi x{destination}, x{destination}, {1 if constant > 0 else -1}")
            for register, coefficient in sorted(terms.items()):
                if (abs(coefficient) >> bit) & 1:
                    operation = "add" if coefficient > 0 else "sub"
                    self.lines.append(f"{operation} x{destination}, x{destination}, x{register}")
