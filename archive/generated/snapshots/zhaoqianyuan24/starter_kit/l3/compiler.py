import re
from typing import List, Set, Tuple

from .ast import (
    Assign,
    BinaryOp,
    ClassicalBlock,
    Expr,
    IfStmt,
    IntLiteral,
    MeasurementRef,
    RegisterRef,
    Stmt,
    UnaryOp,
)

from .parser import (
    ParserError,
    parse_classical_block,
)


class CompileError(ValueError):
    pass


# ============================================================
# Hybrid-QASM splitting
# ============================================================


def _find_classical_span(
    source: str,
) -> Tuple[int, int]:

    match = re.search(
        r"\bclassical\s*\{",
        source,
    )

    if match is None:
        raise CompileError(
            "Hybrid-QASM contains no classical block."
        )

    start = match.start()

    brace_start = source.find(
        "{",
        match.start(),
        match.end(),
    )

    depth = 0
    i = brace_start
    in_string = False

    while i < len(source):

        ch = source[i]

        # --------------------------------------------
        # String
        # --------------------------------------------

        if ch == '"':
            in_string = not in_string
            i += 1
            continue

        if in_string:
            i += 1
            continue

        # --------------------------------------------
        # // comment
        # --------------------------------------------

        if (
            ch == "/"
            and i + 1 < len(source)
            and source[i + 1] == "/"
        ):
            newline = source.find(
                "\n",
                i + 2,
            )

            if newline == -1:
                i = len(source)
            else:
                i = newline + 1

            continue

        # --------------------------------------------
        # Brace nesting
        # --------------------------------------------

        if ch == "{":
            depth += 1

        elif ch == "}":
            depth -= 1

            if depth == 0:
                return start, i + 1

        i += 1

    raise CompileError(
        "Unterminated classical block."
    )


def remove_classical_block(
    source: str,
) -> str:

    start, end = _find_classical_span(
        source
    )

    return (
        source[:start]
        + "\n"
        + source[end:]
    )


# ============================================================
# Quantum operation extraction
# ============================================================


def _remove_line_comments(
    text: str,
) -> str:

    lines = []

    for line in text.splitlines():

        if "//" in line:
            line = line.split(
                "//",
                1,
            )[0]

        lines.append(line)

    return "\n".join(lines)


def extract_quantum_ops(
    hybrid_qasm: str,
) -> List[str]:

    quantum_source = (
        remove_classical_block(
            hybrid_qasm
        )
    )

    quantum_source = (
        _remove_line_comments(
            quantum_source
        )
    )

    operations = []

    for part in quantum_source.split(";"):

        statement = (
            re.sub(
                r"\s+",
                " ",
                part,
            )
            .strip()
        )

        if not statement:
            continue

        lower = statement.lower()

        # Headers/declarations are not quantum operations.
        if lower.startswith(
            (
                "openqasm ",
                "include ",
                "qreg ",
                "creg ",
            )
        ):
            continue

        operations.append(
            statement + ";"
        )

    return operations


# ============================================================
# AST inspection
# ============================================================


def _collect_expr_measurements(
    expr: Expr,
    output: Set[int],
):

    if isinstance(
        expr,
        MeasurementRef,
    ):
        output.add(
            expr.index
        )
        return

    if isinstance(
        expr,
        UnaryOp,
    ):
        _collect_expr_measurements(
            expr.operand,
            output,
        )
        return

    if isinstance(
        expr,
        BinaryOp,
    ):
        _collect_expr_measurements(
            expr.left,
            output,
        )

        _collect_expr_measurements(
            expr.right,
            output,
        )


def _collect_stmt_measurements(
    stmt: Stmt,
    output: Set[int],
):

    if isinstance(
        stmt,
        Assign,
    ):
        _collect_expr_measurements(
            stmt.value,
            output,
        )
        return

    if isinstance(
        stmt,
        IfStmt,
    ):
        _collect_expr_measurements(
            stmt.condition,
            output,
        )

        for child in stmt.then_body:
            _collect_stmt_measurements(
                child,
                output,
            )

        if stmt.else_body is not None:

            for child in stmt.else_body:
                _collect_stmt_measurements(
                    child,
                    output,
                )


def collect_measurements(
    block: ClassicalBlock,
) -> Set[int]:

    result = set()

    for stmt in block.statements:
        _collect_stmt_measurements(
            stmt,
            result,
        )

    return result


# ============================================================
# Scratch-register allocator
# ============================================================


class ScratchPool:

    def __init__(
        self,
        measurement_indices: Set[int],
    ):

        measurement_registers = {
            10 + index
            for index in measurement_indices
        }

        for index in measurement_indices:

            if index < 0 or index > 21:
                raise CompileError(
                    f"c[{index}] maps outside "
                    "RISC-V register range x0-x31."
                )

        # x1..x9 belong to r1..r9.
        #
        # x10... are measurement / available temporary
        # registers. Never use a measurement register that
        # appears in this classical program as scratch.

        self.available = [
            f"x{index}"
            for index in range(
                10,
                32,
            )
            if index not in measurement_registers
        ]

    def acquire(self) -> str:

        if not self.available:
            raise CompileError(
                "Not enough temporary RISC-V registers."
            )

        return self.available.pop()

    def release(
        self,
        register: str,
    ):
        self.available.append(
            register
        )


# ============================================================
# RISC-V code generator
# ============================================================


class RISCVCompiler:

    def __init__(
        self,
        block: ClassicalBlock,
    ):

        self.block = block
        self.lines: List[str] = []
        self.label_counter = 0

        measurements = (
            collect_measurements(
                block
            )
        )

        self.scratch = ScratchPool(
            measurements
        )

    def emit(
        self,
        line: str,
    ):
        self.lines.append(
            line
        )

    def new_label(
        self,
        prefix: str,
    ) -> str:

        label = (
            f"LOOMQ_{prefix}_"
            f"{self.label_counter}"
        )

        self.label_counter += 1

        return label

    # ========================================================
    # Expression compilation
    # ========================================================

    def compile_expr(
        self,
        expr: Expr,
        dest: str,
    ):

        # ----------------------------------------------------
        # Integer
        # ----------------------------------------------------

        if isinstance(
            expr,
            IntLiteral,
        ):
            self.emit(
                f"li {dest}, {expr.value}"
            )
            return

        # ----------------------------------------------------
        # r1..r9
        # ----------------------------------------------------

        if isinstance(
            expr,
            RegisterRef,
        ):

            source = f"x{expr.index}"

            self.emit(
                f"addi {dest}, {source}, 0"
            )
            return

        # ----------------------------------------------------
        # c[k] -> x10+k
        # ----------------------------------------------------

        if isinstance(
            expr,
            MeasurementRef,
        ):

            reg_index = (
                10 + expr.index
            )

            if reg_index > 31:
                raise CompileError(
                    f"c[{expr.index}] maps "
                    "outside x0-x31."
                )

            source = (
                f"x{reg_index}"
            )

            self.emit(
                f"addi {dest}, {source}, 0"
            )
            return

        # ----------------------------------------------------
        # Unary minus
        # ----------------------------------------------------

        if isinstance(
            expr,
            UnaryOp,
        ):

            if expr.op != "-":
                raise CompileError(
                    f"Unsupported unary operator: "
                    f"{expr.op}"
                )

            self.compile_expr(
                expr.operand,
                dest,
            )

            self.emit(
                f"sub {dest}, x0, {dest}"
            )
            return

        # ----------------------------------------------------
        # Binary + / -
        # ----------------------------------------------------

        if isinstance(
            expr,
            BinaryOp,
        ):

            if expr.op not in {
                "+",
                "-",
            }:
                raise CompileError(
                    f"Unsupported arithmetic operator: "
                    f"{expr.op}"
                )

            self.compile_expr(
                expr.left,
                dest,
            )

            temp = (
                self.scratch.acquire()
            )

            try:
                self.compile_expr(
                    expr.right,
                    temp,
                )

                instruction = (
                    "add"
                    if expr.op == "+"
                    else "sub"
                )

                self.emit(
                    f"{instruction} "
                    f"{dest}, {dest}, {temp}"
                )

            finally:
                self.scratch.release(
                    temp
                )

            return

        raise CompileError(
            f"Unsupported expression node: "
            f"{type(expr).__name__}"
        )

    # ========================================================
    # Statement compilation
    # ========================================================

    def compile_assign(
        self,
        stmt: Assign,
    ):

        if not 1 <= stmt.target <= 9:
            raise CompileError(
                "Classical registers must "
                "be r1..r9."
            )

        destination = (
            f"x{stmt.target}"
        )

        # Always compute the RHS into a temporary first.
        #
        # This preserves old register values for cases such as:
        #
        #   r1 = r2 - r1;
        #
        # If we wrote directly into x1 while evaluating the
        # RHS, the old value of r1 could be destroyed.

        temp = (
            self.scratch.acquire()
        )

        try:

            self.compile_expr(
                stmt.value,
                temp,
            )

            self.emit(
                f"addi {destination}, "
                f"{temp}, 0"
            )

        finally:
            self.scratch.release(
                temp
            )

    def compile_if(
        self,
        stmt: IfStmt,
    ):

        condition = (
            stmt.condition
        )

        if condition.op not in {
            "==",
            "!=",
        }:
            raise CompileError(
                "if condition must use "
                "'==' or '!='."
            )

        left_reg = (
            self.scratch.acquire()
        )

        right_reg = (
            self.scratch.acquire()
        )

        try:

            self.compile_expr(
                condition.left,
                left_reg,
            )

            self.compile_expr(
                condition.right,
                right_reg,
            )

            false_label = (
                self.new_label(
                    "FALSE"
                )
            )

            end_label = (
                self.new_label(
                    "END"
                )
            )

            # Jump when the condition is FALSE.
            #
            #   a == b  -> false when a != b
            #   a != b  -> false when a == b

            if condition.op == "==":

                self.emit(
                    f"bne {left_reg}, "
                    f"{right_reg}, "
                    f"{false_label}"
                )

            else:

                self.emit(
                    f"beq {left_reg}, "
                    f"{right_reg}, "
                    f"{false_label}"
                )

        finally:

            self.scratch.release(
                right_reg
            )

            self.scratch.release(
                left_reg
            )

        # ----------------------------------------------------
        # THEN
        # ----------------------------------------------------

        for child in stmt.then_body:
            self.compile_stmt(
                child
            )

        if stmt.else_body is not None:

            self.emit(
                f"j {end_label}"
            )

        # ----------------------------------------------------
        # FALSE / ELSE
        # ----------------------------------------------------

        self.emit(
            f"{false_label}:"
        )

        if stmt.else_body is not None:

            for child in stmt.else_body:
                self.compile_stmt(
                    child
                )

            self.emit(
                f"{end_label}:"
            )

    def compile_stmt(
        self,
        stmt: Stmt,
    ):

        if isinstance(
            stmt,
            Assign,
        ):
            self.compile_assign(
                stmt
            )
            return

        if isinstance(
            stmt,
            IfStmt,
        ):
            self.compile_if(
                stmt
            )
            return

        raise CompileError(
            f"Unsupported statement node: "
            f"{type(stmt).__name__}"
        )

    # ========================================================
    # Full block
    # ========================================================

    def compile(self) -> str:

        for stmt in self.block.statements:

            self.compile_stmt(
                stmt
            )

        return "\n".join(
            self.lines
        )


# ============================================================
# Public compiler helpers
# ============================================================


def compile_classical_block(
    block: ClassicalBlock,
) -> str:

    return RISCVCompiler(
        block
    ).compile()


def compile_hybrid_source(
    hybrid_qasm: str,
) -> Tuple[List[str], str]:

    try:
        block = (
            parse_classical_block(
                hybrid_qasm
            )
        )

    except ParserError as exc:
        raise CompileError(
            str(exc)
        ) from exc

    quantum_ops = (
        extract_quantum_ops(
            hybrid_qasm
        )
    )

    assembly = (
        compile_classical_block(
            block
        )
    )

    return (
        quantum_ops,
        assembly,
    )
