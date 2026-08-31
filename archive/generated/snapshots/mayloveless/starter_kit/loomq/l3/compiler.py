"""将 Hybrid-QASM 经典 AST 编译为 Tiny RISC-V 指令子集。"""

from dataclasses import dataclass
from typing import List, Sequence, Set, Tuple, Union

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
from .lexer import HybridQASMError
from .parser import parse_hybrid


@dataclass(frozen=True)
class _Value:
    register: int = -1
    immediate: int = 0
    owned: bool = False

    @property
    def is_immediate(self) -> bool:
        return self.register < 0


class _ScratchAllocator:
    def __init__(self, excluded: Set[int]) -> None:
        # 高寄存器优先使输出稳定，也避免与低位 c[k] 形成不必要耦合。
        self.available = [index for index in range(31, 9, -1) if index not in excluded]
        self.in_use: Set[int] = set()

    def allocate(self) -> int:
        if not self.available:
            raise HybridQASMError(
                "insufficient scratch registers after reserving r1..r9 and referenced c[k]"
            )
        register = self.available.pop(0)
        self.in_use.add(register)
        return register

    def release(self, register: int) -> None:
        if register not in self.in_use:
            return
        self.in_use.remove(register)
        self.available.append(register)
        self.available.sort(reverse=True)


class RISCCompiler:
    def __init__(self, program: Program) -> None:
        self.program = program
        used_classical = _collect_classical_bits(program.statements)
        excluded = set(range(1, 10)) | {10 + index for index in used_classical}
        self.scratch = _ScratchAllocator(excluded)
        self.lines: List[str] = []
        self.label_counter = 0

    def compile(self) -> str:
        self.compile_statements(self.program.statements)
        if not self.lines:
            # 空经典块仍返回可执行且无副作用的非空程序。
            self.emit("addi x0, x0, 0")
        return "\n".join(self.lines) + "\n"

    def emit(self, instruction: str) -> None:
        self.lines.append(instruction)

    def compile_statements(self, statements: Sequence[Statement]) -> None:
        for statement in statements:
            if isinstance(statement, Assignment):
                self.compile_assignment(statement)
            else:
                self.compile_if_else(statement)

    def compile_assignment(self, statement: Assignment) -> None:
        destination = statement.target.index
        # 最外层表达式可直接写 assignment 目标，减少不必要的 scratch。
        value = self.compile_expression(
            statement.expression, preferred_destination=destination
        )
        if value.is_immediate:
            self.emit("li x%d, %d" % (destination, value.immediate))
        elif value.register != destination:
            self.emit("addi x%d, x%d, 0" % (destination, value.register))
        self.release_value(value)

    def compile_if_else(self, statement: IfElse) -> None:
        label_id = self.label_counter
        self.label_counter += 1
        else_label = "L_if_%d_else" % label_id
        end_label = "L_if_%d_end" % label_id

        condition = self.compile_condition(statement.condition)
        if condition is False:
            self.emit("j %s" % else_label)
        elif condition is not True:
            left, right = condition
            false_branch = "bne" if statement.condition.operator == "==" else "beq"
            self.emit(
                "%s x%d, x%d, %s"
                % (false_branch, left.register, right.register, else_label)
            )
            self.release_value(left)
            self.release_value(right)

        self.compile_statements(statement.then_body)
        self.emit("j %s" % end_label)
        self.emit(else_label + ":")
        self.compile_statements(statement.else_body)
        self.emit(end_label + ":")

    def compile_condition(
        self, comparison: Comparison
    ) -> Union[bool, Tuple[_Value, _Value]]:
        left = self.compile_expression(comparison.left)
        right = self.compile_expression(comparison.right)
        if left.is_immediate and right.is_immediate:
            equal = left.immediate == right.immediate
            return equal if comparison.operator == "==" else not equal
        return self.materialize(left), self.materialize(right)

    def compile_expression(
        self, expression: Expression, preferred_destination: int = -1
    ) -> _Value:
        if isinstance(expression, IntegerLiteral):
            return _Value(immediate=expression.value)
        if isinstance(expression, RegisterRef):
            return _Value(register=expression.index)
        if isinstance(expression, ClassicalBitRef):
            return _Value(register=10 + expression.index)

        left = self.compile_expression(expression.left)
        right = self.compile_expression(expression.right)
        if left.is_immediate and right.is_immediate:
            value = (
                left.immediate + right.immediate
                if expression.operator == "+"
                else left.immediate - right.immediate
            )
            return _Value(immediate=value)

        destination = self.choose_destination(
            expression.operator, left, right, preferred_destination
        )
        self.emit_binary(expression.operator, destination, left, right)
        self.release_value(left, except_register=destination)
        self.release_value(right, except_register=destination)
        return _Value(register=destination, owned=True)

    def choose_destination(
        self,
        operator: str,
        left: _Value,
        right: _Value,
        preferred_destination: int,
    ) -> int:
        if preferred_destination >= 0 and not (
            operator == "-"
            and left.is_immediate
            and left.immediate != 0
            and right.register == preferred_destination
        ):
            return preferred_destination
        if left.owned:
            return left.register
        # 非零立即数减临时值需要先装载立即数，不能覆盖仍要读取的右值。
        if right.owned and not (
            operator == "-" and left.is_immediate and left.immediate != 0
        ):
            return right.register
        return self.scratch.allocate()

    def emit_binary(
        self, operator: str, destination: int, left: _Value, right: _Value
    ) -> None:
        if operator == "+":
            if left.is_immediate:
                self.emit(
                    "addi x%d, x%d, %d"
                    % (destination, right.register, left.immediate)
                )
            elif right.is_immediate:
                self.emit(
                    "addi x%d, x%d, %d"
                    % (destination, left.register, right.immediate)
                )
            else:
                self.emit(
                    "add x%d, x%d, x%d"
                    % (destination, left.register, right.register)
                )
            return

        if right.is_immediate:
            self.emit(
                "addi x%d, x%d, %d"
                % (destination, left.register, -right.immediate)
            )
        elif left.is_immediate:
            if left.immediate == 0:
                self.emit("sub x%d, x0, x%d" % (destination, right.register))
            else:
                self.emit("li x%d, %d" % (destination, left.immediate))
                self.emit(
                    "sub x%d, x%d, x%d"
                    % (destination, destination, right.register)
                )
        else:
            self.emit(
                "sub x%d, x%d, x%d"
                % (destination, left.register, right.register)
            )

    def materialize(self, value: _Value) -> _Value:
        if not value.is_immediate:
            return value
        if value.immediate == 0:
            return _Value(register=0)
        register = self.scratch.allocate()
        self.emit("li x%d, %d" % (register, value.immediate))
        return _Value(register=register, owned=True)

    def release_value(self, value: _Value, except_register: int = -1) -> None:
        if value.owned and value.register != except_register:
            self.scratch.release(value.register)


def _collect_classical_bits(statements: Sequence[Statement]) -> Set[int]:
    result: Set[int] = set()

    def visit_expression(expression: Expression) -> None:
        if isinstance(expression, ClassicalBitRef):
            result.add(expression.index)
        elif isinstance(expression, BinaryExpr):
            visit_expression(expression.left)
            visit_expression(expression.right)

    for statement in statements:
        if isinstance(statement, Assignment):
            visit_expression(statement.expression)
        else:
            visit_expression(statement.condition.left)
            visit_expression(statement.condition.right)
            result.update(_collect_classical_bits(statement.then_body))
            result.update(_collect_classical_bits(statement.else_body))
    return result


def compile_program(program: Program) -> Tuple[List[str], str]:
    """编译已解析 AST，返回量子操作和经典汇编。"""
    assembly = RISCCompiler(program).compile()
    return list(program.quantum_operations), assembly


def compile_hybrid_source(source: str) -> Tuple[List[str], str]:
    """完整 Hybrid-QASM 编译入口。"""
    return compile_program(parse_hybrid(source))
