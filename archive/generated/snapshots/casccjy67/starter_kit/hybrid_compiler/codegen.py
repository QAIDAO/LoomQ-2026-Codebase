"""RISC-V code generator for Hybrid-QASM classical blocks."""
from .parser import (
    NumberExpr, RegisterExpr, ClbitExpr, BinaryOp,
    Assignment, IfStatement,
)


class RiscVCodeGen:
    def __init__(self):
        self.lines = []
        self.label_counter = 0
        self.temp_counter = 5  # x5+ used for temps, avoid x0

    def generate(self, statements: list) -> str:
        for stmt in statements:
            self._gen_statement(stmt)
        return "\n".join(self.lines) if self.lines else "nop"

    def _gen_statement(self, stmt):
        if isinstance(stmt, Assignment):
            self._gen_assignment(stmt)
        elif isinstance(stmt, IfStatement):
            self._gen_if(stmt)

    def _gen_assignment(self, stmt: Assignment):
        result_reg = self._eval_expr(stmt.value, stmt.target.index)
        if result_reg != stmt.target.index:
            self._emit(f"mv x{stmt.target.index}, x{result_reg}")

    def _gen_if(self, stmt: IfStatement):
        left_reg = self._eval_operand(stmt.condition_left)
        right_reg = self._eval_operand(stmt.condition_right)

        if stmt.else_body:
            else_label = self._new_label()
            end_label = self._new_label()
            cmp_instr = "beq" if stmt.cmp_op == "!=" else "bne"
            self._emit(f"{cmp_instr} x{left_reg}, x{right_reg}, {else_label}")
            for s in stmt.then_body:
                self._gen_statement(s)
            self._emit(f"j {end_label}")
            self._emit(f"{else_label}:")
            for s in stmt.else_body:
                self._gen_statement(s)
            self._emit(f"{end_label}:")
        else:
            end_label = self._new_label()
            cmp_instr = "bne" if stmt.cmp_op == "==" else "beq"
            self._emit(f"{cmp_instr} x{left_reg}, x{right_reg}, {end_label}")
            for s in stmt.then_body:
                self._gen_statement(s)
            self._emit(f"{end_label}:")

    def _eval_expr(self, expr, target_reg: int) -> int:
        if isinstance(expr, NumberExpr):
            self._emit(f"li x{target_reg}, {expr.value}")
            return target_reg

        if isinstance(expr, RegisterExpr):
            if expr.index == target_reg:
                return target_reg
            self._emit(f"mv x{target_reg}, x{expr.index}")
            return target_reg

        if isinstance(expr, ClbitExpr):
            mapped = 10 + expr.index
            self._emit(f"mv x{target_reg}, x{mapped}")
            return target_reg

        if isinstance(expr, BinaryOp):
            if isinstance(expr.left, NumberExpr) and isinstance(expr.right, NumberExpr):
                val = expr.left.value + expr.right.value if expr.op == "+" else expr.left.value - expr.right.value
                self._emit(f"li x{target_reg}, {val}")
                return target_reg

            left_reg = self._eval_operand(expr.left)
            right_reg = self._eval_operand(expr.right)

            if expr.op == "+":
                self._emit(f"add x{target_reg}, x{left_reg}, x{right_reg}")
            else:
                self._emit(f"sub x{target_reg}, x{left_reg}, x{right_reg}")
            return target_reg

        raise ValueError(f"Unknown expression type: {type(expr)}")

    def _eval_operand(self, operand) -> int:
        if isinstance(operand, NumberExpr):
            temp = self._new_temp()
            self._emit(f"li x{temp}, {operand.value}")
            return temp

        if isinstance(operand, RegisterExpr):
            return operand.index

        if isinstance(operand, ClbitExpr):
            return 10 + operand.index

        if isinstance(operand, BinaryOp):
            temp = self._new_temp()
            return self._eval_expr(operand, temp)

        raise ValueError(f"Unknown operand type: {type(operand)}")

    def _new_label(self) -> str:
        self.label_counter += 1
        return f"L{self.label_counter}"

    def _new_temp(self) -> int:
        self.temp_counter += 1
        return self.temp_counter

    def _emit(self, line: str):
        self.lines.append(f"    {line}")
