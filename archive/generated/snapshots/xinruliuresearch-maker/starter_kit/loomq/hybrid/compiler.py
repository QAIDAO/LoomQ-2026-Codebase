"""Deterministic Hybrid-QASM to TinyRISCV compiler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set, Union

from .ast import (
    Assignment,
    BinaryExpression,
    ClassicalStatement,
    Condition,
    Expression,
    HybridProgram,
    IfStatement,
    IntegerLiteral,
    MeasurementReference,
    RegisterReference,
    UnaryExpression,
)
from .parser import parse_hybrid_program
from .register_allocator import TemporaryRegisterAllocator


class HybridCompileError(ValueError):
    """Raised when a valid Hybrid AST cannot target TinyRISCV safely."""


@dataclass(frozen=True)
class _Immediate:
    value: int


@dataclass(frozen=True)
class _Location:
    register: int
    owned: bool


_Value = Union[_Immediate, _Location]


class HybridCompiler:
    """Compile a parsed program using only the official emulator instruction set."""

    def __init__(self, program: HybridProgram):
        self._program = program
        measurements = _measurement_indices(program)
        measurements.update(program.declared_measurements)
        reserved = set(range(1, 10))
        reserved.update(10 + index for index in measurements)
        self._allocator = TemporaryRegisterAllocator(reserved)
        self._lines: List[str] = []
        self._label_counter = 0

    def compile(self) -> str:
        for statement in self._program.classical_statements:
            self._compile_statement(statement)
        if self._allocator.active:
            active = ", ".join(f"x{index}" for index in sorted(self._allocator.active))
            raise AssertionError(f"compiler leaked temporary registers: {active}")
        return "\n".join(self._lines)

    def _compile_statement(self, statement: ClassicalStatement) -> None:
        if isinstance(statement, Assignment):
            self._compile_assignment(statement)
            return
        if isinstance(statement, IfStatement):
            self._compile_if(statement)
            return
        raise HybridCompileError(
            f"unsupported classical statement: {type(statement).__name__}"
        )

    def _compile_assignment(self, statement: Assignment) -> None:
        destination = statement.target.index
        if self._compile_simple_assignment(statement.value, destination):
            return
        value = self._compile_expression(statement.value)
        if isinstance(value, _Immediate):
            self._emit("li", destination, value.value)
            return
        if value.register != destination:
            self._emit("addi", destination, value.register, 0)
        self._release_if_owned(value)

    def _compile_simple_assignment(self, expression: Expression, destination: int) -> bool:
        """Emit common assignments directly into their architectural target.

        A destination is not scratch state when the whole instruction computes
        its final value.  Handling atomic arithmetic here means valid programs
        still compile when every x10..x31 register is occupied by measurements.
        """

        if isinstance(expression, IntegerLiteral):
            self._emit("li", destination, expression.value)
            return True
        if isinstance(expression, RegisterReference):
            if destination != expression.index:
                self._emit("addi", destination, expression.index, 0)
            return True
        if isinstance(expression, MeasurementReference):
            self._emit("addi", destination, 10 + expression.index, 0)
            return True
        if isinstance(expression, UnaryExpression):
            simple = self._atomic_value(expression.operand)
            if simple is None:
                return False
            if expression.operator == "+":
                return self._emit_atomic_copy(simple, destination)
            if expression.operator == "-":
                if isinstance(simple, _Immediate):
                    self._emit("li", destination, -simple.value)
                else:
                    self._emit("sub", destination, 0, simple.register)
                return True
            return False
        if not isinstance(expression, BinaryExpression):
            return False
        left = self._atomic_value(expression.left)
        right = self._atomic_value(expression.right)
        if left is None or right is None:
            return False
        if isinstance(left, _Immediate) and isinstance(right, _Immediate):
            value = (
                left.value + right.value
                if expression.operator == "+"
                else left.value - right.value
            )
            self._emit("li", destination, value)
            return True
        if expression.operator == "+":
            if isinstance(left, _Immediate):
                assert isinstance(right, _Location)
                self._emit("addi", destination, right.register, left.value)
            elif isinstance(right, _Immediate):
                self._emit("addi", destination, left.register, right.value)
            else:
                self._emit("add", destination, left.register, right.register)
            return True
        if expression.operator != "-":
            return False
        if isinstance(left, _Location) and isinstance(right, _Immediate):
            self._emit("addi", destination, left.register, -right.value)
            return True
        if isinstance(left, _Immediate) and isinstance(right, _Location):
            if destination == right.register:
                self._emit("sub", destination, 0, destination)
                self._emit("addi", destination, destination, left.value)
            else:
                self._emit("li", destination, left.value)
                self._emit("sub", destination, destination, right.register)
            return True
        assert isinstance(left, _Location) and isinstance(right, _Location)
        self._emit("sub", destination, left.register, right.register)
        return True

    @staticmethod
    def _atomic_value(expression: Expression) -> _Value | None:
        if isinstance(expression, IntegerLiteral):
            return _Immediate(expression.value)
        if isinstance(expression, RegisterReference):
            return _Location(expression.index, False)
        if isinstance(expression, MeasurementReference):
            return _Location(10 + expression.index, False)
        if isinstance(expression, UnaryExpression) and isinstance(
            expression.operand, IntegerLiteral
        ):
            value = expression.operand.value
            if expression.operator == "+":
                return _Immediate(value)
            if expression.operator == "-":
                return _Immediate(-value)
        return None

    def _emit_atomic_copy(self, value: _Value, destination: int) -> bool:
        if isinstance(value, _Immediate):
            self._emit("li", destination, value.value)
        elif value.register != destination:
            self._emit("addi", destination, value.register, 0)
        return True

    def _compile_if(self, statement: IfStatement) -> None:
        left = self._compile_expression(statement.condition.left)
        right = self._compile_expression(statement.condition.right)

        # Constant conditions can be resolved without labels or scratch state.
        if isinstance(left, _Immediate) and isinstance(right, _Immediate):
            condition = _compare_immediates(statement.condition, left.value, right.value)
            body = statement.then_body if condition else statement.else_body
            for child in body:
                self._compile_statement(child)
            return

        left_location = self._materialize(left)
        right_location = self._materialize(right)
        label_id = self._next_label_id()
        end_label = f"L_if_{label_id:04d}_end"
        false_label = (
            f"L_if_{label_id:04d}_else" if statement.has_else else end_label
        )
        if statement.condition.operator == "==":
            inverse_branch = "bne"
        elif statement.condition.operator == "!=":
            inverse_branch = "beq"
        else:
            raise HybridCompileError(
                f"unsupported comparison operator: {statement.condition.operator}"
            )
        self._emit(inverse_branch, left_location.register, right_location.register, false_label)
        self._release_if_owned(left_location)
        self._release_if_owned(right_location)

        for child in statement.then_body:
            self._compile_statement(child)
        if statement.has_else:
            self._emit("j", end_label)
            self._emit_label(false_label)
            for child in statement.else_body:
                self._compile_statement(child)
        self._emit_label(end_label)

    def _compile_expression(self, expression: Expression) -> _Value:
        if isinstance(expression, IntegerLiteral):
            return _Immediate(expression.value)
        if isinstance(expression, RegisterReference):
            return _Location(expression.index, False)
        if isinstance(expression, MeasurementReference):
            return _Location(10 + expression.index, False)
        if isinstance(expression, UnaryExpression):
            return self._compile_unary(expression)
        if isinstance(expression, BinaryExpression):
            left = self._compile_expression(expression.left)
            right = self._compile_expression(expression.right)
            return self._compile_binary(expression.operator, left, right)
        raise HybridCompileError(f"unsupported expression: {type(expression).__name__}")

    def _compile_unary(self, expression: UnaryExpression) -> _Value:
        value = self._compile_expression(expression.operand)
        if expression.operator == "+":
            return value
        if expression.operator != "-":
            raise HybridCompileError(f"unsupported unary operator: {expression.operator}")
        if isinstance(value, _Immediate):
            return _Immediate(-value.value)
        target = value.register if value.owned else self._allocator.allocate()
        # x0 is read as the architectural constant zero; the allocator never
        # selects it and no generated instruction ever writes it.
        self._emit("sub", target, 0, value.register)
        return _Location(target, True)

    def _compile_binary(self, operator: str, left: _Value, right: _Value) -> _Value:
        if isinstance(left, _Immediate) and isinstance(right, _Immediate):
            if operator == "+":
                return _Immediate(left.value + right.value)
            if operator == "-":
                return _Immediate(left.value - right.value)
            raise HybridCompileError(f"unsupported binary operator: {operator}")

        if operator == "+":
            return self._compile_add(left, right)
        if operator == "-":
            return self._compile_subtract(left, right)
        raise HybridCompileError(f"unsupported binary operator: {operator}")

    def _compile_add(self, left: _Value, right: _Value) -> _Location:
        if isinstance(left, _Immediate):
            assert isinstance(right, _Location)
            target = right.register if right.owned else self._allocator.allocate()
            self._emit("addi", target, right.register, left.value)
            return _Location(target, True)
        if isinstance(right, _Immediate):
            target = left.register if left.owned else self._allocator.allocate()
            self._emit("addi", target, left.register, right.value)
            return _Location(target, True)

        target = self._select_binary_target(left, right)
        self._emit("add", target, left.register, right.register)
        self._release_operands_except(target, left, right)
        return _Location(target, True)

    def _compile_subtract(self, left: _Value, right: _Value) -> _Location:
        if isinstance(left, _Location) and isinstance(right, _Immediate):
            target = left.register if left.owned else self._allocator.allocate()
            self._emit("addi", target, left.register, -right.value)
            return _Location(target, True)
        if isinstance(left, _Immediate) and isinstance(right, _Location):
            if right.owned:
                # Negate in place, then add the constant.  This preserves the
                # right operand and requires no second temporary.
                self._emit("sub", right.register, 0, right.register)
                self._emit("addi", right.register, right.register, left.value)
                return right
            target = self._allocator.allocate()
            self._emit("li", target, left.value)
            self._emit("sub", target, target, right.register)
            return _Location(target, True)

        assert isinstance(left, _Location) and isinstance(right, _Location)
        target = self._select_binary_target(left, right)
        self._emit("sub", target, left.register, right.register)
        self._release_operands_except(target, left, right)
        return _Location(target, True)

    def _select_binary_target(self, left: _Location, right: _Location) -> int:
        if left.owned:
            return left.register
        if right.owned:
            return right.register
        return self._allocator.allocate()

    def _release_operands_except(
        self, target: int, left: _Location, right: _Location
    ) -> None:
        released: Set[int] = set()
        for value in (left, right):
            if value.owned and value.register != target and value.register not in released:
                self._allocator.release(value.register)
                released.add(value.register)

    def _materialize(self, value: _Value) -> _Location:
        if isinstance(value, _Location):
            return value
        register = self._allocator.allocate()
        self._emit("li", register, value.value)
        return _Location(register, True)

    def _release_if_owned(self, value: _Location) -> None:
        if value.owned:
            self._allocator.release(value.register)

    def _emit(self, opcode: str, *arguments: object) -> None:
        rendered = [str(argument) for argument in arguments]

        register_positions = {
            "li": (0,),
            "add": (0, 1, 2),
            "sub": (0, 1, 2),
            "addi": (0, 1),
            "beq": (0, 1),
            "bne": (0, 1),
            "j": (),
        }
        if opcode not in register_positions:
            raise AssertionError(f"compiler attempted unsupported opcode {opcode!r}")
        for position in register_positions[opcode]:
            register = int(arguments[position])
            if register < 0 or register > 31:
                raise HybridCompileError(f"register x{register} is outside x0..x31")
            rendered[position] = f"x{register}"
        if opcode in {"li", "add", "sub", "addi"} and int(arguments[0]) == 0:
            raise HybridCompileError("compiler refused to write destination x0")
        self._lines.append(f"{opcode} " + ", ".join(rendered))

    def _emit_label(self, label: str) -> None:
        self._lines.append(f"{label}:")

    def _next_label_id(self) -> int:
        self._label_counter += 1
        return self._label_counter


def _compare_immediates(condition: Condition, left: int, right: int) -> bool:
    if condition.operator == "==":
        return left == right
    if condition.operator == "!=":
        return left != right
    raise HybridCompileError(f"unsupported comparison operator: {condition.operator}")


def _measurement_indices(program: HybridProgram) -> Set[int]:
    indices: Set[int] = set()

    def visit_expression(expression: Expression) -> None:
        if isinstance(expression, MeasurementReference):
            indices.add(expression.index)
        elif isinstance(expression, UnaryExpression):
            visit_expression(expression.operand)
        elif isinstance(expression, BinaryExpression):
            visit_expression(expression.left)
            visit_expression(expression.right)

    def visit_statement(statement: ClassicalStatement) -> None:
        if isinstance(statement, Assignment):
            visit_expression(statement.value)
        elif isinstance(statement, IfStatement):
            visit_expression(statement.condition.left)
            visit_expression(statement.condition.right)
            for child in statement.then_body:
                visit_statement(child)
            for child in statement.else_body:
                visit_statement(child)

    for root in program.classical_statements:
        visit_statement(root)
    return indices


def compile_hybrid_program(source: str) -> tuple[list[str], str]:
    """Compile Hybrid-QASM into stable quantum operations and TinyRISCV text.

    The quantum list contains gate and measurement statements only; OpenQASM
    headers, includes, and register declarations are deliberately excluded.
    """

    program = parse_hybrid_program(source)
    assembly = HybridCompiler(program).compile()
    return list(program.quantum_operations), assembly
