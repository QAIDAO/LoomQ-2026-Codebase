import itertools
import random
from dataclasses import dataclass
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )
from l3 import compile_hybrid_l3
from riscv_emulator import TinyRISCVEmulator


SEED = 20260815
NUM_PROGRAMS = 300
MAX_DEPTH = 2

rng = random.Random(SEED)


# ============================================================
# Small independent reference AST
#
# Important:
# This deliberately does NOT use l3.ast or l3.parser.
# It is our independent semantic oracle.
# ============================================================


@dataclass
class Int:
    value: int


@dataclass
class Reg:
    index: int


@dataclass
class Meas:
    index: int


@dataclass
class Neg:
    value: object


@dataclass
class Bin:
    left: object
    op: str
    right: object


@dataclass
class Assign:
    target: int
    value: object


@dataclass
class If:
    left: object
    op: str
    right: object
    then_body: list
    else_body: list


# ============================================================
# Expression generation
# ============================================================


def random_atom():
    choice = rng.choice([
        "int",
        "reg",
        "meas",
    ])

    if choice == "int":
        return Int(
            rng.randint(-10, 20)
        )

    if choice == "reg":
        return Reg(
            rng.randint(1, 5)
        )

    return Meas(
        rng.randint(0, 2)
    )


def random_expr(depth=0):

    if depth >= 2:
        return random_atom()

    choice = rng.random()

    if choice < 0.50:
        return random_atom()

    if choice < 0.60:
        return Neg(
            random_expr(
                depth + 1
            )
        )

    return Bin(
        random_expr(depth + 1),
        rng.choice(["+", "-"]),
        random_expr(depth + 1),
    )


# ============================================================
# Statement generation
# ============================================================


def random_assignment():

    return Assign(
        target=rng.randint(1, 5),
        value=random_expr(),
    )


def random_statement(
    depth=0,
):

    if (
        depth >= MAX_DEPTH
        or rng.random() < 0.65
    ):
        return random_assignment()

    then_count = rng.randint(
        1,
        3,
    )

    else_count = rng.randint(
        1,
        3,
    )

    return If(
        left=random_expr(),
        op=rng.choice(
            ["==", "!="]
        ),
        right=random_expr(),
        then_body=[
            random_statement(
                depth + 1
            )
            for _ in range(
                then_count
            )
        ],
        else_body=[
            random_statement(
                depth + 1
            )
            for _ in range(
                else_count
            )
        ],
    )


def random_program():

    count = rng.randint(
        2,
        7,
    )

    return [
        random_statement()
        for _ in range(count)
    ]


# ============================================================
# Independent reference interpreter
# ============================================================


def eval_expr(
    expr,
    registers,
    measurements,
):

    if isinstance(expr, Int):
        return expr.value

    if isinstance(expr, Reg):
        return registers[
            expr.index
        ]

    if isinstance(expr, Meas):
        return measurements.get(
            expr.index,
            0,
        )

    if isinstance(expr, Neg):
        return -eval_expr(
            expr.value,
            registers,
            measurements,
        )

    if isinstance(expr, Bin):

        left = eval_expr(
            expr.left,
            registers,
            measurements,
        )

        right = eval_expr(
            expr.right,
            registers,
            measurements,
        )

        if expr.op == "+":
            return left + right

        if expr.op == "-":
            return left - right

        raise RuntimeError(
            f"Unknown operator "
            f"{expr.op}"
        )

    raise RuntimeError(
        f"Unknown expression "
        f"{type(expr).__name__}"
    )


def execute_reference(
    statements,
    measurements,
):

    registers = {
        index: 0
        for index in range(
            1,
            10,
        )
    }

    def execute_block(
        block,
    ):

        for stmt in block:

            if isinstance(
                stmt,
                Assign,
            ):

                value = eval_expr(
                    stmt.value,
                    registers,
                    measurements,
                )

                registers[
                    stmt.target
                ] = value

                continue

            if isinstance(
                stmt,
                If,
            ):

                left = eval_expr(
                    stmt.left,
                    registers,
                    measurements,
                )

                right = eval_expr(
                    stmt.right,
                    registers,
                    measurements,
                )

                if stmt.op == "==":
                    condition = (
                        left == right
                    )

                elif stmt.op == "!=":
                    condition = (
                        left != right
                    )

                else:
                    raise RuntimeError(
                        stmt.op
                    )

                if condition:
                    execute_block(
                        stmt.then_body
                    )
                else:
                    execute_block(
                        stmt.else_body
                    )

                continue

            raise RuntimeError(
                type(stmt).__name__
            )

    execute_block(
        statements
    )

    return registers


# ============================================================
# Source renderer
# ============================================================


def render_expr(expr):

    if isinstance(expr, Int):

        if expr.value < 0:
            return (
                f"({expr.value})"
            )

        return str(
            expr.value
        )

    if isinstance(expr, Reg):
        return (
            f"r{expr.index}"
        )

    if isinstance(expr, Meas):
        return (
            f"c[{expr.index}]"
        )

    if isinstance(expr, Neg):
        return (
            f"-({render_expr(expr.value)})"
        )

    if isinstance(expr, Bin):
        return (
            "("
            + render_expr(
                expr.left
            )
            + f" {expr.op} "
            + render_expr(
                expr.right
            )
            + ")"
        )

    raise RuntimeError(
        type(expr).__name__
    )


def render_block(
    statements,
    indent=4,
):

    lines = []

    prefix = " " * indent

    for stmt in statements:

        if isinstance(
            stmt,
            Assign,
        ):

            lines.append(
                prefix
                + f"r{stmt.target} = "
                + render_expr(
                    stmt.value
                )
                + ";"
            )

            continue

        if isinstance(
            stmt,
            If,
        ):

            lines.append(
                prefix
                + "if ("
                + render_expr(
                    stmt.left
                )
                + f" {stmt.op} "
                + render_expr(
                    stmt.right
                )
                + ") {"
            )

            lines.extend(
                render_block(
                    stmt.then_body,
                    indent + 4,
                )
            )

            lines.append(
                prefix + "} else {"
            )

            lines.extend(
                render_block(
                    stmt.else_body,
                    indent + 4,
                )
            )

            lines.append(
                prefix + "}"
            )

            continue

        raise RuntimeError(
            type(stmt).__name__
        )

    return lines


def build_hybrid_qasm(
    statements,
):

    classical_lines = (
        render_block(
            statements
        )
    )

    return "\n".join(
        [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            "",
            "qreg q[3];",
            "creg c[3];",
            "",
            "h q[0];",
            "measure q[0] -> c[0];",
            "measure q[1] -> c[1];",
            "measure q[2] -> c[2];",
            "",
            "classical {",
            *classical_lines,
            "}",
            "",
            "x q[2];",
            "",
        ]
    )


# ============================================================
# Official RISC-V emulator execution
# ============================================================


def execute_riscv(
    assembly,
    measurements,
):

    emulator = (
        TinyRISCVEmulator()
    )

    emulator.load_program(
        assembly
    )

    for index, value in (
        measurements.items()
    ):

        emulator.set_register(
            f"x{10 + index}",
            value,
        )

    return emulator.execute()


# ============================================================
# Fuzz campaign
# ============================================================


total_runs = 0


for program_index in range(
    NUM_PROGRAMS
):

    statements = (
        random_program()
    )

    source = (
        build_hybrid_qasm(
            statements
        )
    )

    try:

        quantum_ops, assembly = (
            compile_hybrid_l3(
                source
            )
        )

    except Exception:

        print()
        print("=" * 78)
        print(
            "COMPILATION FAILURE"
        )
        print("=" * 78)

        print(
            "program =",
            program_index,
        )

        print()
        print(source)

        raise


    # Three measurement bits:
    #
    # c[0], c[1], c[2]
    #
    # Exhaust all 2^3 = 8 possibilities.

    for bits in itertools.product(
        [0, 1],
        repeat=3,
    ):

        measurements = {
            index: value
            for index, value
            in enumerate(bits)
        }

        expected = (
            execute_reference(
                statements,
                measurements,
            )
        )

        actual_state = (
            execute_riscv(
                assembly,
                measurements,
            )
        )

        for register in range(
            1,
            10,
        ):

            expected_value = (
                expected[
                    register
                ]
            )

            actual_value = (
                actual_state.get(
                    f"x{register}",
                    0,
                )
            )

            if (
                actual_value
                != expected_value
            ):

                print()
                print("=" * 78)
                print(
                    "L3 FUZZ MISMATCH"
                )
                print("=" * 78)

                print(
                    "seed =",
                    SEED,
                )

                print(
                    "program =",
                    program_index,
                )

                print(
                    "measurements =",
                    measurements,
                )

                print(
                    "register =",
                    f"x{register}",
                )

                print(
                    "expected =",
                    expected_value,
                )

                print(
                    "actual =",
                    actual_value,
                )

                print()
                print(
                    "--- Hybrid-QASM ---"
                )

                print(source)

                print()
                print(
                    "--- Generated RISC-V ---"
                )

                print(assembly)

                print()
                print(
                    "--- Expected registers ---"
                )

                print(expected)

                print()
                print(
                    "--- Actual state ---"
                )

                print(actual_state)

                raise AssertionError(
                    "L3 fuzz semantics mismatch"
                )

        total_runs += 1


print()
print("=" * 78)
print("L3 FUZZ TEST PASSED")
print("=" * 78)

print(
    "seed             =",
    SEED,
)

print(
    "random programs  =",
    NUM_PROGRAMS,
)

print(
    "measurement sets =",
    total_runs,
)

print(
    "register checks  =",
    total_runs * 9,
)
