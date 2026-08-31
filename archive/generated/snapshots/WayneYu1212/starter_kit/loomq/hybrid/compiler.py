"""Compile Hybrid-QASM classical AST into the official stock RISC-V subset."""

from __future__ import annotations

from .ast import Assign, BinaryExpr, Expr, IfStmt, IntLiteral, MeasurementRef, RegisterRef, Stmt
from .parser import parse_hybrid


class HybridCompileError(ValueError):
    """Raised when a valid AST cannot fit the published RISC-V register contract."""


class _ScratchRegisters:
    def __init__(self, measurement_indices: frozenset[int]):
        measurement_registers = {10 + index for index in measurement_indices}
        self.available = [index for index in range(31, 9, -1) if index not in measurement_registers]
        self.in_use: set[int] = set()

    def acquire(self) -> int:
        for index in self.available:
            if index not in self.in_use:
                self.in_use.add(index)
                return index
        raise HybridCompileError("classical expression requires more scratch registers")

    def release(self, index: int) -> None:
        if index not in self.in_use:
            raise HybridCompileError("internal scratch-register lifetime error")
        self.in_use.remove(index)


class _Compiler:
    def __init__(self, measurement_indices: frozenset[int]):
        self.lines: list[str] = []
        self.labels = 0
        self.scratch = _ScratchRegisters(measurement_indices)

    def compile(self, statements: tuple[Stmt, ...]) -> str:
        self._statements(statements)
        return "\n".join(self.lines) + "\n"

    def _label(self, stem: str) -> str:
        self.labels += 1
        return f"L3_{stem}_{self.labels:04d}"

    def _register(self, expression: Expr) -> int:
        if isinstance(expression, RegisterRef):
            return expression.index
        if isinstance(expression, MeasurementRef):
            return 10 + expression.index
        raise HybridCompileError("expression is not a direct register reference")

    def _expression(self, expression: Expr) -> int:
        destination = self.scratch.acquire()
        self._expression_into(expression, destination)
        return destination

    def _expression_into(self, expression: Expr, destination: int) -> None:
        if isinstance(expression, IntLiteral):
            self.lines.append(f"li x{destination}, {expression.value}")
            return
        if isinstance(expression, (RegisterRef, MeasurementRef)):
            source = self._register(expression)
            if source != destination:
                self.lines.append(f"addi x{destination}, x{source}, 0")
            return
        if not isinstance(expression, BinaryExpr):
            raise HybridCompileError("unknown expression node")
        self._expression_into(expression.left, destination)
        if isinstance(expression.right, IntLiteral):
            immediate = expression.right.value if expression.operator == "+" else -expression.right.value
            self.lines.append(f"addi x{destination}, x{destination}, {immediate}")
            return
        right = self._expression(expression.right)
        operation = "add" if expression.operator == "+" else "sub"
        self.lines.append(f"{operation} x{destination}, x{destination}, x{right}")
        self.scratch.release(right)

    def _statements(self, statements: tuple[Stmt, ...]) -> None:
        for statement in statements:
            if isinstance(statement, Assign):
                value = self._expression(statement.value)
                self.lines.append(f"addi x{statement.target}, x{value}, 0")
                self.scratch.release(value)
                continue
            if not isinstance(statement, IfStmt):
                raise HybridCompileError("unknown statement node")
            left = self._expression(statement.condition.left)
            right = self._expression(statement.condition.right)
            else_label = self._label("ELSE")
            end_label = self._label("END")
            branch = "bne" if statement.condition.operator == "==" else "beq"
            self.lines.append(f"{branch} x{left}, x{right}, {else_label}")
            self.scratch.release(right)
            self.scratch.release(left)
            self._statements(statement.then_body)
            self.lines.append(f"j {end_label}")
            self.lines.append(f"{else_label}:")
            self._statements(statement.else_body)
            self.lines.append(f"{end_label}:")


def compile_hybrid(source: str) -> tuple[list[str], str]:
    """Return ordered quantum statements and stock-subset RISC-V assembly."""

    program = parse_hybrid(source)
    assembly = _Compiler(program.measurement_indices).compile(program.statements)
    return list(program.quantum_ops), assembly
