#!/usr/bin/env python3
"""L3 Hybrid-QASM to tiny RISC-V compiler.

This module is deliberately separate from the L1/L2 adapter code. The public
``adapter.compile_hybrid`` entry point only delegates here.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Optional

try:
    from . import adapter
except ImportError:
    import adapter


@dataclass(frozen=True)
class IntLiteral:
    value: int


@dataclass(frozen=True)
class RegisterRef:
    index: int


@dataclass(frozen=True)
class ClassicalBitRef:
    index: int


@dataclass(frozen=True)
class BinaryArithmetic:
    op: str
    left: Any
    right: Any


@dataclass(frozen=True)
class Comparison:
    op: str
    left: Any
    right: Any


@dataclass(frozen=True)
class Assignment:
    target: int
    expr: Any


@dataclass(frozen=True)
class IfElse:
    condition: Comparison
    then_body: list[Any]
    else_body: list[Any]


@dataclass(frozen=True)
class Program:
    statements: list[Any]


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int


def compile_hybrid_impl(hybrid_qasm_str: str) -> tuple[list[str], str]:
    if not isinstance(hybrid_qasm_str, str) or not hybrid_qasm_str.strip():
        raise ValueError("hybrid_qasm_str must be a non-empty string")
    quantum_qasm, classical_source = split_hybrid_qasm(hybrid_qasm_str)
    quantum_ops, creg_size = extract_quantum_ops(quantum_qasm)
    tokens = tokenize_classical(classical_source)
    program = Parser(tokens).parse_program()
    compiler = RISCVCompiler(creg_size=creg_size)
    assembly = compiler.compile(program)
    return quantum_ops, assembly


def split_hybrid_qasm(source: str) -> tuple[str, str]:
    keyword = _find_classical_keyword(source)
    if keyword is None:
        raise ValueError("Hybrid-QASM must contain exactly one classical block")
    start, keyword_end = keyword
    pos = _skip_space_and_line_comments(source, keyword_end)
    if pos >= len(source) or source[pos] != "{":
        raise ValueError("classical block must start with '{'")
    end_brace = _find_matching_brace(source, pos)
    after = source[end_brace + 1 :]
    if _find_classical_keyword(after) is not None:
        raise ValueError("multiple classical blocks are not supported")
    return source[:start] + "\n" + after, source[pos + 1 : end_brace]


def _find_classical_keyword(source: str, start: int = 0) -> Optional[tuple[int, int]]:
    pos = start
    in_string = False
    while pos < len(source):
        if in_string:
            if source[pos] == "\\":
                pos += 2
                continue
            if source[pos] == '"':
                in_string = False
            pos += 1
            continue
        if source.startswith("//", pos):
            newline = source.find("\n", pos)
            if newline == -1:
                return None
            pos = newline + 1
            continue
        if source[pos] == '"':
            in_string = True
            pos += 1
            continue
        if source.startswith("classical", pos):
            before = source[pos - 1] if pos > 0 else ""
            after = source[pos + len("classical")] if pos + len("classical") < len(source) else ""
            if not _is_identifier_char(before) and not _is_identifier_char(after):
                return pos, pos + len("classical")
        pos += 1
    return None


def _is_identifier_char(char: str) -> bool:
    return bool(char) and (char.isalnum() or char == "_")


def _skip_space_and_line_comments(source: str, pos: int) -> int:
    while pos < len(source):
        if source[pos].isspace():
            pos += 1
            continue
        if source.startswith("//", pos):
            newline = source.find("\n", pos)
            if newline == -1:
                return len(source)
            pos = newline + 1
            continue
        break
    return pos


def _find_matching_brace(source: str, open_index: int) -> int:
    depth = 0
    pos = open_index
    while pos < len(source):
        if source.startswith("//", pos):
            newline = source.find("\n", pos)
            if newline == -1:
                break
            pos = newline + 1
            continue
        char = source[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return pos
        pos += 1
    raise ValueError("unmatched brace in classical block")


def extract_quantum_ops(qasm: str) -> tuple[list[str], int]:
    ir = adapter._parse_qasm(qasm)
    ops: list[str] = []
    for op in ir.ops:
        if isinstance(op, adapter.GateOp):
            ops.append(_format_gate_op(op))
        elif isinstance(op, adapter.MeasureOp):
            ops.append(f"measure q[{op.qubit}] -> c[{op.cbit}];")
        else:
            raise ValueError(f"unknown quantum op: {op!r}")
    return ops, ir.num_cbits


def _format_gate_op(op: Any) -> str:
    args = ", ".join(f"q[{qubit}]" for qubit in op.qubits)
    if op.params:
        params = ", ".join(adapter._format_angle(param) for param in op.params)
        return f"{op.name}({params}) {args};"
    return f"{op.name} {args};"


def tokenize_classical(source: str) -> list[Token]:
    clean = "\n".join(line.split("//", 1)[0] for line in source.splitlines())
    tokens: list[Token] = []
    pos = 0
    while pos < len(clean):
        char = clean[pos]
        if char.isspace():
            pos += 1
            continue
        if clean.startswith("==", pos) or clean.startswith("!=", pos):
            tokens.append(Token(clean[pos : pos + 2], clean[pos : pos + 2], pos))
            pos += 2
            continue
        if char in "{}()[]=;+-":
            tokens.append(Token(char, char, pos))
            pos += 1
            continue
        match = re.match(r"\d+", clean[pos:])
        if match:
            value = match.group(0)
            tokens.append(Token("INT", value, pos))
            pos += len(value)
            continue
        match = re.match(r"[A-Za-z_]\w*", clean[pos:])
        if match:
            value = match.group(0)
            kind = value if value in {"if", "else"} else "IDENT"
            tokens.append(Token(kind, value, pos))
            pos += len(value)
            continue
        raise ValueError(f"unsupported classical token at position {pos}: {char!r}")
    tokens.append(Token("EOF", "", len(clean)))
    return tokens


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    def parse_program(self) -> Program:
        statements = self._parse_statements(stop_kind="EOF")
        self._expect("EOF")
        return Program(statements)

    def _parse_statements(self, stop_kind: str) -> list[Any]:
        statements = []
        while self._peek().kind != stop_kind:
            statements.append(self._parse_statement())
        return statements

    def _parse_statement(self) -> Any:
        if self._peek().kind == "if":
            return self._parse_if_else()
        return self._parse_assignment()

    def _parse_assignment(self) -> Assignment:
        target = self._parse_register_ref()
        self._expect("=")
        expr = self._parse_expression()
        self._expect(";")
        return Assignment(target.index, expr)

    def _parse_if_else(self) -> IfElse:
        self._expect("if")
        self._expect("(")
        condition = self._parse_condition()
        self._expect(")")
        then_body = self._parse_block()
        self._expect("else")
        else_body = self._parse_block()
        return IfElse(condition, then_body, else_body)

    def _parse_block(self) -> list[Any]:
        self._expect("{")
        statements = self._parse_statements(stop_kind="}")
        self._expect("}")
        return statements

    def _parse_condition(self) -> Comparison:
        left = self._parse_expression()
        if self._peek().kind not in {"==", "!="}:
            raise ValueError("condition must use == or !=")
        op = self._advance().kind
        right = self._parse_expression()
        return Comparison(op, left, right)

    def _parse_expression(self) -> Any:
        expr = self._parse_atom()
        while self._peek().kind in {"+", "-"}:
            op = self._advance().kind
            rhs = self._parse_atom()
            expr = BinaryArithmetic(op, expr, rhs)
        return expr

    def _parse_atom(self) -> Any:
        token = self._peek()
        if token.kind == "INT":
            self._advance()
            return IntLiteral(int(token.value))
        if token.kind == "IDENT" and re.fullmatch(r"r[1-9]", token.value):
            return self._parse_register_ref()
        if token.kind == "IDENT" and token.value == "c":
            return self._parse_classical_bit_ref()
        raise ValueError(f"expected expression at position {token.position}")

    def _parse_register_ref(self) -> RegisterRef:
        token = self._expect("IDENT")
        if not re.fullmatch(r"r[1-9]", token.value):
            raise ValueError(f"invalid register variable: {token.value}")
        return RegisterRef(int(token.value[1:]))

    def _parse_classical_bit_ref(self) -> ClassicalBitRef:
        self._expect("IDENT", value="c")
        self._expect("[")
        index = self._expect("INT")
        self._expect("]")
        return ClassicalBitRef(int(index.value))

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _advance(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _expect(self, kind: str, value: Optional[str] = None) -> Token:
        token = self._peek()
        if token.kind != kind or (value is not None and token.value != value):
            expected = value if value is not None else kind
            raise ValueError(f"expected {expected!r} at position {token.position}, got {token.value!r}")
        return self._advance()


class RISCVCompiler:
    def __init__(self, creg_size: int):
        self.creg_size = creg_size
        self.lines: list[str] = []
        self.label_counter = 0
        self.scratch_regs = self._choose_scratch_registers(creg_size)

    def compile(self, program: Program) -> str:
        for statement in program.statements:
            self._compile_statement(statement)
        return "\n".join(self.lines) + "\n"

    def _choose_scratch_registers(self, creg_size: int) -> list[str]:
        used = set(range(1, 10)) | set(range(10, 10 + creg_size))
        scratch = []
        for index in range(31, 0, -1):
            if index not in used:
                scratch.append(f"x{index}")
        return scratch

    def _compile_statement(self, statement: Any) -> None:
        if isinstance(statement, Assignment):
            self._compile_assignment(statement)
        elif isinstance(statement, IfElse):
            self._compile_if_else(statement)
        else:
            raise ValueError(f"unsupported statement: {statement!r}")

    def _compile_assignment(self, statement: Assignment) -> None:
        dest = self._r_reg(statement.target)
        self._compile_expr_to(statement.expr, dest)

    def _compile_if_else(self, statement: IfElse) -> None:
        condition_value = self._const_condition(statement.condition)
        if condition_value is not None:
            for item in statement.then_body if condition_value else statement.else_body:
                self._compile_statement(item)
            return

        else_label = self._new_label("ELSE")
        end_label = self._new_label("ENDIF")
        direct_left = self._direct_expr_reg(statement.condition.left)
        direct_right = self._direct_expr_reg(statement.condition.right)
        if direct_left and direct_right:
            left = direct_left
            right = direct_right
        else:
            left = self._compile_condition_delta(statement.condition)
            right = "x0"
        branch = "bne" if statement.condition.op == "==" else "beq"
        self.lines.append(f"{branch} {left}, {right}, {else_label}")
        for item in statement.then_body:
            self._compile_statement(item)
        self.lines.append(f"j {end_label}")
        self.lines.append(f"{else_label}:")
        for item in statement.else_body:
            self._compile_statement(item)
        self.lines.append(f"{end_label}:")

    def _compile_expr_to(self, expr: Any, dest: str, scratch_start: int = 0, reserved: Optional[set[str]] = None) -> None:
        reserved = reserved or set()
        constant = self._const_expr(expr)
        if constant is not None:
            self.lines.append(f"li {dest}, {constant}")
        elif isinstance(expr, IntLiteral):
            self.lines.append(f"li {dest}, {expr.value}")
        elif isinstance(expr, RegisterRef):
            self.lines.append(f"addi {dest}, {self._r_reg(expr.index)}, 0")
        elif isinstance(expr, ClassicalBitRef):
            self._check_c_index(expr.index)
            self.lines.append(f"addi {dest}, {self._c_reg(expr.index)}, 0")
        elif isinstance(expr, BinaryArithmetic):
            self._compile_binary_to(expr, dest, scratch_start, reserved)
        else:
            raise ValueError(f"unsupported expression: {expr!r}")

    def _compile_binary_to(
        self,
        expr: BinaryArithmetic,
        dest: str,
        scratch_start: int = 0,
        reserved: Optional[set[str]] = None,
    ) -> None:
        reserved = reserved or set()
        constant = self._const_expr(expr)
        if constant is not None:
            self.lines.append(f"li {dest}, {constant}")
            return

        first, rest = self._flatten_arithmetic(expr)
        if len(rest) > 1:
            self._compile_arithmetic_chain_to(first, rest, dest, scratch_start, reserved)
            return

        left_reg = self._direct_expr_reg(expr.left)
        right_reg = self._direct_expr_reg(expr.right)
        if left_reg and isinstance(expr.right, IntLiteral) and expr.op == "+":
            self.lines.append(f"addi {dest}, {left_reg}, {expr.right.value}")
            return
        if isinstance(expr.left, IntLiteral) and right_reg and expr.op == "+":
            self.lines.append(f"addi {dest}, {right_reg}, {expr.left.value}")
            return
        if left_reg and isinstance(expr.right, IntLiteral) and expr.op == "-":
            self.lines.append(f"addi {dest}, {left_reg}, {-expr.right.value}")
            return
        if isinstance(expr.left, IntLiteral) and right_reg and expr.op == "-":
            lhs = dest
            if dest == right_reg:
                lhs = self._scratch(scratch_start, reserved)
            self.lines.append(f"li {lhs}, {expr.left.value}")
            self.lines.append(f"sub {dest}, {lhs}, {right_reg}")
            return
        if left_reg and right_reg:
            op = "add" if expr.op == "+" else "sub"
            self.lines.append(f"{op} {dest}, {left_reg}, {right_reg}")
            return
        left, next_scratch = self._compile_expr_operand(expr.left, scratch_start, reserved)
        right, _ = self._compile_expr_operand(expr.right, next_scratch, reserved | {left})
        op = "add" if expr.op == "+" else "sub"
        self.lines.append(f"{op} {dest}, {left}, {right}")

    def _compile_condition_expr(self, expr: Any, scratch_index: int) -> tuple[str, int]:
        return self._compile_expr_operand(expr, scratch_index, set())

    def _compile_expr_operand(self, expr: Any, scratch_start: int, reserved: set[str]) -> tuple[str, int]:
        direct = self._direct_expr_reg(expr)
        if direct:
            return direct, scratch_start
        scratch = self._scratch(scratch_start, reserved)
        self._compile_expr_to(expr, scratch, scratch_start + 1, reserved | {scratch})
        return scratch, scratch_start + 1

    def _compile_arithmetic_chain_to(
        self,
        first: Any,
        rest: list[tuple[str, Any]],
        dest: str,
        scratch_start: int,
        reserved: set[str],
    ) -> None:
        terms = [first] + [rhs for _, rhs in rest]
        dest_index = int(dest[1:]) if re.fullmatch(r"x[1-9]", dest) else None
        late_dest_ref = (
            dest_index is not None
            and any(self._contains_register_ref(term, dest_index) for term in terms[2:])
        )
        accumulator = self._scratch(scratch_start, reserved) if late_dest_ref else dest
        next_scratch = scratch_start + 1 if late_dest_ref else scratch_start
        first_expr = BinaryArithmetic(rest[0][0], first, rest[0][1])
        self._compile_binary_to(first_expr, accumulator, next_scratch, reserved | {accumulator})
        for op, rhs in rest[1:]:
            self._apply_chain_term(accumulator, op, rhs, next_scratch, reserved | {accumulator})
        if accumulator != dest:
            self.lines.append(f"addi {dest}, {accumulator}, 0")

    def _apply_chain_term(
        self,
        accumulator: str,
        op: str,
        term: Any,
        scratch_start: int,
        reserved: set[str],
    ) -> None:
        constant = self._const_expr(term)
        if constant is not None:
            immediate = constant if op == "+" else -constant
            self.lines.append(f"addi {accumulator}, {accumulator}, {immediate}")
            return
        direct = self._direct_expr_reg(term)
        if direct:
            instruction = "add" if op == "+" else "sub"
            self.lines.append(f"{instruction} {accumulator}, {accumulator}, {direct}")
            return
        value, _ = self._compile_expr_operand(term, scratch_start, reserved)
        instruction = "add" if op == "+" else "sub"
        self.lines.append(f"{instruction} {accumulator}, {accumulator}, {value}")

    def _compile_condition_delta(self, condition: Comparison) -> str:
        accumulator = self._scratch(0)
        signed_terms = self._signed_terms(condition.left, 1) + self._signed_terms(condition.right, -1)
        self._materialize_signed_terms(accumulator, signed_terms)
        return accumulator

    def _materialize_signed_terms(self, accumulator: str, signed_terms: list[tuple[int, Any]]) -> None:
        first_sign, first_term = signed_terms[0]
        first_constant = self._const_expr(first_term)
        first_direct = self._direct_expr_reg(first_term)
        if first_constant is not None:
            self.lines.append(f"li {accumulator}, {first_sign * first_constant}")
        elif first_direct:
            if first_sign == 1:
                self.lines.append(f"addi {accumulator}, {first_direct}, 0")
            else:
                self.lines.append(f"sub {accumulator}, x0, {first_direct}")
        else:
            self._compile_expr_to(first_term, accumulator, 1, {accumulator})
            if first_sign == -1:
                self.lines.append(f"sub {accumulator}, x0, {accumulator}")

        for sign, term in signed_terms[1:]:
            constant = self._const_expr(term)
            if constant is not None:
                self.lines.append(f"addi {accumulator}, {accumulator}, {sign * constant}")
                continue
            direct = self._direct_expr_reg(term)
            if direct:
                instruction = "add" if sign == 1 else "sub"
                self.lines.append(f"{instruction} {accumulator}, {accumulator}, {direct}")
                continue
            value, _ = self._compile_expr_operand(term, 1, {accumulator})
            instruction = "add" if sign == 1 else "sub"
            self.lines.append(f"{instruction} {accumulator}, {accumulator}, {value}")

    def _compile_expr_value(self, expr: Any, preferred_scratch: str) -> str:
        constant = self._const_expr(expr)
        if constant is not None:
            self.lines.append(f"li {preferred_scratch}, {constant}")
            return preferred_scratch
        if isinstance(expr, RegisterRef):
            return self._r_reg(expr.index)
        if isinstance(expr, ClassicalBitRef):
            self._check_c_index(expr.index)
            return self._c_reg(expr.index)
        if isinstance(expr, IntLiteral):
            self.lines.append(f"li {preferred_scratch}, {expr.value}")
            return preferred_scratch
        if isinstance(expr, BinaryArithmetic):
            self._compile_expr_to(expr, preferred_scratch)
            return preferred_scratch
        raise ValueError(f"unsupported expression: {expr!r}")

    def _new_label(self, prefix: str) -> str:
        label = f"{prefix}_{self.label_counter}"
        self.label_counter += 1
        return label

    def _scratch(self, index: int, reserved: Optional[set[str]] = None) -> str:
        reserved = reserved or set()
        available = [scratch for scratch in self.scratch_regs if scratch not in reserved]
        if index >= len(available):
            raise ValueError("not enough scratch registers for L3 compilation")
        return available[index]

    def _r_reg(self, index: int) -> str:
        if not 1 <= index <= 9:
            raise ValueError(f"invalid r register: r{index}")
        return f"x{index}"

    def _c_reg(self, index: int) -> str:
        return f"x{10 + index}"

    def _check_c_index(self, index: int) -> None:
        if not 0 <= index < self.creg_size:
            raise ValueError(f"classical bit index out of range: c[{index}]")
        if 10 + index > 31:
            raise ValueError(f"classical bit c[{index}] maps beyond supported RISC-V register x31")

    def _direct_expr_reg(self, expr: Any) -> Optional[str]:
        if isinstance(expr, RegisterRef):
            return self._r_reg(expr.index)
        if isinstance(expr, ClassicalBitRef):
            self._check_c_index(expr.index)
            return self._c_reg(expr.index)
        return None

    def _const_expr(self, expr: Any) -> Optional[int]:
        if isinstance(expr, IntLiteral):
            return expr.value
        if isinstance(expr, BinaryArithmetic):
            left = self._const_expr(expr.left)
            right = self._const_expr(expr.right)
            if left is None or right is None:
                return None
            return left + right if expr.op == "+" else left - right
        return None

    def _const_condition(self, condition: Comparison) -> Optional[bool]:
        left = self._const_expr(condition.left)
        right = self._const_expr(condition.right)
        if left is None or right is None:
            return None
        return left == right if condition.op == "==" else left != right

    def _flatten_arithmetic(self, expr: Any) -> tuple[Any, list[tuple[str, Any]]]:
        if not isinstance(expr, BinaryArithmetic):
            return expr, []
        first, rest = self._flatten_arithmetic(expr.left)
        return first, rest + [(expr.op, expr.right)]

    def _signed_terms(self, expr: Any, sign: int) -> list[tuple[int, Any]]:
        first, rest = self._flatten_arithmetic(expr)
        terms = [(sign, first)]
        for op, rhs in rest:
            rhs_sign = sign if op == "+" else -sign
            terms.append((rhs_sign, rhs))
        return terms

    def _contains_register_ref(self, expr: Any, index: int) -> bool:
        if isinstance(expr, RegisterRef):
            return expr.index == index
        if isinstance(expr, BinaryArithmetic):
            return self._contains_register_ref(expr.left, index) or self._contains_register_ref(expr.right, index)
        return False


def interpret_program(program: Program, measurements: dict[int, int]) -> dict[int, int]:
    registers = {index: 0 for index in range(1, 10)}

    def eval_expr(expr: Any) -> int:
        if isinstance(expr, IntLiteral):
            return expr.value
        if isinstance(expr, RegisterRef):
            return registers[expr.index]
        if isinstance(expr, ClassicalBitRef):
            return int(measurements.get(expr.index, 0))
        if isinstance(expr, BinaryArithmetic):
            left = eval_expr(expr.left)
            right = eval_expr(expr.right)
            return left + right if expr.op == "+" else left - right
        raise ValueError(f"unsupported expression: {expr!r}")

    def eval_condition(condition: Comparison) -> bool:
        left = eval_expr(condition.left)
        right = eval_expr(condition.right)
        return left == right if condition.op == "==" else left != right

    def exec_statements(statements: list[Any]) -> None:
        for statement in statements:
            if isinstance(statement, Assignment):
                registers[statement.target] = eval_expr(statement.expr)
            elif isinstance(statement, IfElse):
                exec_statements(statement.then_body if eval_condition(statement.condition) else statement.else_body)
            else:
                raise ValueError(f"unsupported statement: {statement!r}")

    exec_statements(program.statements)
    return {index: value for index, value in registers.items() if value != 0}


def parse_classical_program(source: str) -> Program:
    return Parser(tokenize_classical(source)).parse_program()
