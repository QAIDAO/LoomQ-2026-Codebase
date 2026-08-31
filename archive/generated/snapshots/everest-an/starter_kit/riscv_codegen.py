"""RISC-V assembly generation for the LoomQ L3 classical control block.

Targets the official TinyRISCVEmulator instruction subset:
li, add, sub, addi, beq, bne, j. Registers: r1..r9 -> x1..x9,
measurement bits c[k] -> x10+k. x20/x21 are scratch registers (never
touched by the graded r1..r9 or the injected measurement values).

Strategy: sequential assignment compiles to li/mv plus add/sub chains;
if/else compiles to compare (scratch regs) + inverted branch to the else
label + unconditional jump over it. Nested if/else is handled naturally
by recursion with a monotone label counter.
"""

from typing import Dict, List, Optional, Tuple, Union

try:
    from .hybrid_parser import Assign, Cond, If, Operand
except ImportError:  # standalone-module fallback
    from hybrid_parser import Assign, Cond, If, Operand

_SCRATCH_A = "x20"
_SCRATCH_B = "x21"


class RiscvCodegen:
    def __init__(self) -> None:
        self.lines: List[str] = []
        self.label_counter = 0

    # -- helpers ----------------------------------------------------------

    def new_label(self) -> str:
        label = "L%d" % self.label_counter
        self.label_counter += 1
        return label

    def emit(self, text: str) -> None:
        self.lines.append(text)

    def asm(self) -> str:
        return "\n".join(self.lines) + "\n"

    def load_operand(self, operand: Operand, dest: str) -> None:
        """Materialize an operand into scratch/dest register."""
        kind, value = operand
        if kind == "imm":
            self.emit("li %s, %d" % (dest, value))
        elif kind == "reg":
            self.emit("add %s, x%d, x0" % (dest, value))  # mov via x0
        elif kind == "cbit":
            self.emit("add %s, x%d, x0" % (dest, 10 + value))  # c[k] -> x10+k

    # -- statements ---------------------------------------------------------

    def compile_stmts(self, stmts: List[object]) -> None:
        for stmt in stmts:
            self.compile_stmt(stmt)

    def compile_stmt(self, stmt: object) -> None:
        if isinstance(stmt, Assign):
            self._compile_assign(stmt)
        elif isinstance(stmt, If):
            self._compile_if(stmt)
        else:
            raise ValueError("unknown statement node %r" % (stmt,))

    def _compile_assign(self, stmt: Assign) -> None:
        target = "x%d" % stmt.target
        terms = stmt.expr
        if len(terms) == 1:
            _, operand = terms[0]
            self.load_operand(operand, target)
            return
        # multi-term: first operand goes to scratch, then fold the rest.
        _, first = terms[0]
        self.load_operand(first, _SCRATCH_A)
        for op, operand in terms[1:]:
            self.load_operand(operand, _SCRATCH_B)
            if op == "+":
                self.emit("add %s, %s, %s" % (_SCRATCH_A, _SCRATCH_A, _SCRATCH_B))
            elif op == "-":
                self.emit("sub %s, %s, %s" % (_SCRATCH_A, _SCRATCH_A, _SCRATCH_B))
            else:
                raise ValueError("unsupported assignment operator %r" % op)
        self.emit("add %s, %s, x0" % (target, _SCRATCH_A))

    def _compile_if(self, stmt: If) -> None:
        else_label = self.new_label()
        end_label = self.new_label()
        self._compile_cond_branch(stmt.cond, else_label, jump_if_false=True)
        self.compile_stmts(stmt.then_body)
        self.emit("j %s" % end_label)
        self.emit("%s:" % else_label)
        if stmt.else_body is not None:
            self.compile_stmts(stmt.else_body)
        self.emit("%s:" % end_label)

    def _compile_cond_branch(self, cond: Cond, target: str, jump_if_false: bool) -> None:
        """Branch to ``target`` when the condition is false (or true)."""
        self.load_operand(cond.left, _SCRATCH_A)
        self.load_operand(cond.right, _SCRATCH_B)
        op = "bne" if cond.op == "==" else "beq"  # jump when condition is false
        if not jump_if_false:
            op = "beq" if cond.op == "==" else "bne"
        self.emit("%s %s, %s, %s" % (op, _SCRATCH_A, _SCRATCH_B, target))


def compile_classic_block(stmts: List[object]) -> str:
    """Compile a parsed classical block into TinyRISCVEmulator assembly."""
    codegen = RiscvCodegen()
    codegen.compile_stmts(stmts)
    return codegen.asm()
