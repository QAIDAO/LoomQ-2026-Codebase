"""Lower the classical Hybrid-QASM AST to the official RISC-V subset."""

from __future__ import annotations

from typing import List, Set, Tuple

from .errors import HybridCompileError
from .nodes import (
    Assignment,
    BinaryExpression,
    Comparison,
    Expression,
    IfStatement,
    IntegerLiteral,
    MeasurementRef,
    RegisterRef,
    Statement,
)


class RISCVCompiler:
    def __init__(self, classical_bit_count: int) -> None:
        if classical_bit_count > 22:
            raise HybridCompileError(
                "creg c[%d] cannot map to x10..x31" % classical_bit_count
            )
        reserved = set(range(1, 10)) | set(
            range(10, 10 + classical_bit_count)
        )
        self._available_scratch = [
            index for index in range(31, 9, -1) if index not in reserved
        ]
        self._used_scratch: Set[int] = set()
        self._lines: List[str] = []
        self._label_counter = 0

    def compile(self, statements: Tuple[Statement, ...]) -> str:
        for statement in statements:
            self._compile_statement(statement)
        if not self._lines:
            self._lines.append("addi x0, x0, 0")
        for register in sorted(self._used_scratch):
            self._lines.append("li x%d, 0" % register)
        return "\n".join(self._lines) + "\n"

    def _compile_statement(self, statement: Statement) -> None:
        if isinstance(statement, Assignment):
            self._compile_assignment(statement)
            return
        if isinstance(statement, IfStatement):
            self._compile_if(statement)
            return
        raise HybridCompileError("unsupported classical statement: %r" % statement)

    def _compile_assignment(self, statement: Assignment) -> None:
        destination = statement.target
        expression = statement.expression
        if isinstance(expression, IntegerLiteral):
            self._emit("li x%d, %d" % (destination, expression.value))
            return
        if isinstance(expression, (RegisterRef, MeasurementRef)):
            source = self._reference_register(expression)
            if source != destination:
                self._emit("addi x%d, x%d, 0" % (destination, source))
            return

        result, owned = self._materialize(expression)
        self._emit("addi x%d, x%d, 0" % (destination, result))
        if owned:
            self._release(result)

    def _compile_if(self, statement: IfStatement) -> None:
        else_label = self._new_label("else")
        end_label = self._new_label("end")
        left, left_owned = self._materialize(statement.condition.left)
        right, right_owned = self._materialize(statement.condition.right)
        branch = "bne" if statement.condition.operator == "==" else "beq"
        self._emit("%s x%d, x%d, %s" % (branch, left, right, else_label))
        if left_owned:
            self._release(left)
        if right_owned:
            self._release(right)

        for child in statement.then_body:
            self._compile_statement(child)
        self._emit("j %s" % end_label)
        self._lines.append(else_label + ":")
        for child in statement.else_body:
            self._compile_statement(child)
        self._lines.append(end_label + ":")

    def _materialize(self, expression: Expression) -> Tuple[int, bool]:
        if isinstance(expression, RegisterRef):
            return expression.index, False
        if isinstance(expression, MeasurementRef):
            return 10 + expression.index, False
        if isinstance(expression, IntegerLiteral):
            if expression.value == 0:
                return 0, False
            register = self._acquire()
            self._emit("li x%d, %d" % (register, expression.value))
            return register, True
        if isinstance(expression, BinaryExpression):
            left, left_owned = self._materialize(expression.left)
            right, right_owned = self._materialize(expression.right)
            result = self._acquire()
            instruction = "add" if expression.operator == "+" else "sub"
            self._emit(
                "%s x%d, x%d, x%d" % (instruction, result, left, right)
            )
            if left_owned:
                self._release(left)
            if right_owned:
                self._release(right)
            return result, True
        raise HybridCompileError("unsupported expression: %r" % expression)

    @staticmethod
    def _reference_register(expression: Expression) -> int:
        if isinstance(expression, RegisterRef):
            return expression.index
        if isinstance(expression, MeasurementRef):
            return 10 + expression.index
        raise HybridCompileError("expression is not a register reference")

    def _acquire(self) -> int:
        if not self._available_scratch:
            raise HybridCompileError("not enough RISC-V scratch registers")
        register = self._available_scratch.pop(0)
        self._used_scratch.add(register)
        return register

    def _release(self, register: int) -> None:
        if register not in self._available_scratch:
            self._available_scratch.append(register)
            self._available_scratch.sort(reverse=True)

    def _new_label(self, role: str) -> str:
        label = "L3_%s_%d" % (role, self._label_counter)
        self._label_counter += 1
        return label

    def _emit(self, line: str) -> None:
        self._lines.append(line)


def compile_riscv(
    statements: Tuple[Statement, ...], classical_bit_count: int
) -> str:
    return RISCVCompiler(classical_bit_count).compile(statements)

