"""L3 Hybrid-QASM parser、compiler 与隐藏风格随机差分测试。"""

import itertools
import random
import unittest
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple, Union

from adapter import compile_hybrid
from loomq.expressions import parse_angle_expression
from loomq.l3 import HybridQASMError, parse_hybrid
from loomq.l3.ast import Assignment, BinaryExpr, IfElse, IntegerLiteral
from riscv_emulator import TinyRISCVEmulator


def hybrid_source(body: str, *, bits: int = 3, before: str = "", after: str = "") -> str:
    return (
        "OPENQASM 2.0;\n"
        'include "qelib1.inc";\n'
        "qreg q[3];\n"
        "creg c[%d];\n" % bits
        + before
        + "classical {\n"
        + body
        + "\n}\n"
        + after
    )


def execute(source: str, measurements: Sequence[int] = ()) -> Dict[str, int]:
    _, assembly = compile_hybrid(source)
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    for index, value in enumerate(measurements):
        emulator.set_register("x%d" % (10 + index), value)
    return emulator.execute()


class HybridParserCompilerTests(unittest.TestCase):
    def test_parser_builds_explicit_ast(self) -> None:
        program = parse_hybrid(
            hybrid_source(
                "r1 = -7; r2 = (r1 + c[0]) - (3 - r1);\n"
                "if (r2 != 0) { r3 = 1; } else { r3 = 2; }"
            )
        )

        self.assertEqual(3, len(program.statements))
        self.assertIsInstance(program.statements[0], Assignment)
        self.assertEqual(IntegerLiteral(-7), program.statements[0].expression)
        self.assertIsInstance(program.statements[1].expression, BinaryExpr)
        self.assertIsInstance(program.statements[2], IfElse)

    def test_assignments_operand_combinations_and_sequential_values(self) -> None:
        state = execute(
            hybrid_source(
                """
                r1 = 7;
                r2 = r1;
                r3 = r1 + r2;
                r4 = r3 - r1;
                r5 = r4 + 5;
                r6 = r5 - 3;
                r7 = 2 + r6;
                r8 = 20 - r7;
                r9 = -4 + c[1];
                r9 = 5 - (c[0] + r9);
                r1 = r1 + 5;
                """
            ),
            (0, 1, 0),
        )

        self.assertEqual(
            [12, 7, 14, 7, 12, 9, 11, 9, 8],
            [state.get("x%d" % index, 0) for index in range(1, 10)],
        )

    def test_adversarial_precedence_associativity_and_unary_minus(self) -> None:
        source = hybrid_source(
            """
            r2 = 10;
            r3 = 3;
            r1 = 10 - 3 - 2;
            r4 = 10 - (3 - 2);
            r5 = -3 + 5;
            r6 = r2 - (r3 - 4);
            r7 = -(r2 - r3);
            r8 = +5 - -2;
            r9 = r9 - (r9 - 4);
            if ((r1 - 1) != (c[0] + 2)) { r2 = 21; } else { r2 = 22; }
            """,
            bits=1,
        )
        state = execute(source, (0,))

        self.assertEqual(
            [5, 21, 3, 9, 2, 11, -7, 7, 4],
            [state.get("x%d" % index, 0) for index in range(1, 10)],
        )

    def test_adversarial_comparison_directions_and_label_lifetimes(self) -> None:
        source = hybrid_source(
            """
            if (c[0] == 0) { r1 = 10; } else { r1 = 20; }
            if (c[0] != 0) { r2 = r1 - 1; } else { r2 = r1 + 1; }
            if ((r2 - r1) == -1) { r3 = 30; } else { r3 = 40; }
            if ((r2 - r1) != 1) { r4 = 50; } else { r4 = 60; }
            """,
            bits=1,
        )
        zero_state = execute(source, (0,))
        one_state = execute(source, (1,))

        self.assertEqual(
            [10, 11, 40, 60],
            [zero_state.get("x%d" % index, 0) for index in range(1, 5)],
        )
        self.assertEqual(
            [20, 19, 30, 50],
            [one_state.get("x%d" % index, 0) for index in range(1, 5)],
        )

    def test_equal_not_equal_nested_and_sequential_if(self) -> None:
        source = hybrid_source(
            """
            r1 = 2;
            if (c[0] == 1) {
              if (r1 != c[1]) { r2 = 10; } else { r2 = 20; }
            } else {
              r2 = 30;
            }
            if ((r2 - 10) == (5 - 5)) { r3 = r2 + 1; } else { r3 = r2 - 1; }
            """
        )

        self.assertEqual(29, execute(source, (0, 0, 0)).get("x3"))
        self.assertEqual(11, execute(source, (1, 0, 0)).get("x3"))
        self.assertEqual(19, execute(source, (1, 2, 0)).get("x3"))

    def test_constant_conditions_and_empty_branches(self) -> None:
        source = hybrid_source(
            "if (-2 == 1 - 3) { } else { r1 = 8; }\n"
            "if (4 != 4) { r2 = 9; } else { }"
        )
        _, assembly = compile_hybrid(source)

        self.assertEqual(0, execute(source).get("x1", 0))
        self.assertEqual(0, execute(source).get("x2", 0))
        self.assertIn("L_if_0_else:", assembly)
        self.assertIn("L_if_1_else:", assembly)

    def test_quantum_operations_are_canonical_and_keep_source_order(self) -> None:
        source = (
            "// braces in comments do not matter: { }\n"
            "OPENQASM 2.0; include \"qelib1.inc\"; qreg q[3]; creg c[2];\n"
            "ry( pi/2 ) q[0]; measure q[0] -> c[0];\n"
            "classical /* split */ { r1=c[0]+1; }\n"
            "cx q[0],q[1]; cu1(3*pi/8) q[1], q[2];\n"
        )
        quantum_ops, _ = compile_hybrid(source)

        self.assertEqual(
            [
                "ry(pi / 2) q[0];",
                "measure q[0] -> c[0];",
                "cx q[0], q[1];",
                "cu1(3 * pi / 8) q[1], q[2];",
            ],
            quantum_ops,
        )

    def test_quantum_numeric_literals_keep_parameter_semantics(self) -> None:
        parameters = ("1e-3", "1.5e+2", ".5", "5.", "-pi/2", "-3*pi/8")
        for parameter in parameters:
            with self.subTest(parameter=parameter):
                quantum_ops, _ = compile_hybrid(
                    hybrid_source("", bits=1, before="rz(%s) q[0];\n" % parameter)
                )
                emitted = quantum_ops[0]
                emitted_parameter = emitted[emitted.index("(") + 1 : emitted.rindex(")")]
                self.assertEqual(
                    parse_angle_expression(parameter),
                    parse_angle_expression(emitted_parameter),
                )

    def test_adversarial_quantum_tokens_comments_and_include_string(self) -> None:
        source = (
            'OPENQASM 2.0; include "classical;{still-a-string}.inc"; '
            "qreg q[22]; creg c[22];\n"
            "sdg q[10]; tdg q[11]; swap q[10],q[11]; ccx q[0],q[10],q[21];\n"
            "rz((pi/2)-(-.25e+1)) q[21]; // classical { ; }\n"
            "measure/* keep mapping */q[21]->c[21];\n"
            "classical /* { fake } */ { r1 = c[21]; }\n"
            "cu1(-3.0E-2) q[10],q[21];\n"
        )
        quantum_ops, _ = compile_hybrid(source)

        self.assertEqual(
            [
                "sdg q[10];",
                "tdg q[11];",
                "swap q[10], q[11];",
                "ccx q[0], q[10], q[21];",
            ],
            quantum_ops[:4],
        )
        self.assertEqual("measure q[21] -> c[21];", quantum_ops[5])
        self.assertTrue(quantum_ops[6].endswith(" q[10], q[21];"))
        for source_parameter, operation in (
            ("(pi/2)-(-.25e+1)", quantum_ops[4]),
            ("-3.0E-2", quantum_ops[6]),
        ):
            emitted_parameter = operation[operation.index("(") + 1 : operation.rindex(")")]
            self.assertEqual(
                parse_angle_expression(source_parameter),
                parse_angle_expression(emitted_parameter),
            )

    def test_adversarial_high_classical_bit_and_scratch_preservation(self) -> None:
        references = " ".join("r9 = c[%d];" % index for index in range(22))
        source = hybrid_source(
            references
            + " r1 = c[0] + c[21];"
            + " if (c[21] != c[0]) { r2 = 7; } else { r2 = 8; }",
            bits=22,
        )
        measurements = (0,) * 21 + (1,)
        _, assembly = compile_hybrid(source)
        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        for index, value in enumerate(measurements):
            emulator.set_register("x%d" % (10 + index), value)
        state = emulator.execute()

        self.assertEqual(1, state.get("x1"))
        self.assertEqual(7, state.get("x2"))
        self.assertEqual(1, emulator.get_register("x31"))

    def test_deep_balanced_expression_keeps_temp_lifetimes_bounded(self) -> None:
        measurements = (2, 3, 5, 7)

        def build_expression(depth: int, leaf: int) -> Tuple[str, int, int]:
            if depth == 0:
                index = leaf % len(measurements)
                return "c[%d]" % index, measurements[index], leaf + 1
            left, left_value, next_leaf = build_expression(depth - 1, leaf)
            right, right_value, next_leaf = build_expression(depth - 1, next_leaf)
            return "(%s - %s)" % (left, right), left_value - right_value, next_leaf

        expression, expected, _ = build_expression(8, 0)
        source = hybrid_source("r1 = %s;" % expression, bits=4)
        _, assembly = compile_hybrid(source)
        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        for index, value in enumerate(measurements):
            emulator.set_register("x%d" % (10 + index), value)
        state = emulator.execute()

        self.assertEqual(expected, state.get("x1", 0))
        self.assertEqual(
            list(measurements),
            [emulator.get_register("x%d" % (10 + index)) for index in range(4)],
        )

    def test_creg_beyond_emulator_mapping_is_rejected(self) -> None:
        source = hybrid_source("r1 = c[0];", bits=23)
        with self.assertRaisesRegex(HybridQASMError, "mapping x10..x31"):
            compile_hybrid(source)

    def test_single_line_whitespace_and_block_comments(self) -> None:
        source = (
            'OPENQASM 2.0;include "qelib1.inc";qreg q[1];creg c[1];'
            "/* comment\nwith lines */ classical{if(c[0]!=0){r1=1;}else{r1=-1;}}"
        )
        self.assertEqual(-1, execute(source, (0,)).get("x1"))
        self.assertEqual(1, execute(source, (1,)).get("x1"))

    def test_only_supported_instructions_and_unique_labels_are_emitted(self) -> None:
        _, assembly = compile_hybrid(
            hybrid_source(
                "if (c[0] == 0) { r1 = 1; } else { r1 = 2; }\n"
                "if (c[1] != r1) { r2 = 3; } else { r2 = 4; }"
            )
        )
        instructions = []
        labels = []
        for line in assembly.splitlines():
            if line.endswith(":"):
                labels.append(line)
            elif line:
                instructions.append(line.split()[0])

        self.assertLessEqual(set(instructions), {"li", "add", "sub", "addi", "beq", "bne", "j"})
        self.assertEqual(len(labels), len(set(labels)))
        self.assertIn("bne", instructions)
        self.assertIn("beq", instructions)

    def test_scratch_does_not_overwrite_referenced_classical_bits(self) -> None:
        source = hybrid_source(
            "r1 = ((c[0] + c[1]) - (c[2] + 5)) + (c[0] - c[2]);",
            bits=3,
        )
        _, assembly = compile_hybrid(source)
        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        for index, value in enumerate((7, 11, 13)):
            emulator.set_register("x%d" % (10 + index), value)
        state = emulator.execute()

        self.assertEqual(-6, state.get("x1"))
        self.assertEqual([7, 11, 13], [emulator.get_register("x%d" % i) for i in (10, 11, 12)])

    def test_exhausted_scratch_has_clear_error(self) -> None:
        references = " ".join("r1 = c[%d];" % index for index in range(22))
        direct_source = hybrid_source(references + " r2 = c[0] + c[1];", bits=22)
        self.assertEqual(1, execute(direct_source, (1, 0) + (0,) * 20).get("x2"))

        source = hybrid_source(
            references + " r2 = (c[0] + c[1]) + (c[2] + c[3]);", bits=22
        )
        with self.assertRaisesRegex(HybridQASMError, "insufficient scratch registers"):
            compile_hybrid(source)

    def test_zero_condition_uses_x0_when_all_measurement_registers_are_reserved(self) -> None:
        references = " ".join("r1 = c[%d];" % index for index in range(22))
        source = hybrid_source(
            references + " if (c[0] == 0) { r2 = 4; } else { r2 = 5; }",
            bits=22,
        )
        _, assembly = compile_hybrid(source)

        self.assertIn("bne x10, x0", assembly)
        self.assertEqual(4, execute(source, (0,) * 22).get("x2"))

    def test_empty_classical_block_returns_no_op_program(self) -> None:
        quantum_ops, assembly = compile_hybrid(hybrid_source("", bits=1))
        self.assertEqual([], quantum_ops)
        self.assertEqual("addi x0, x0, 0\n", assembly)
        self.assertEqual({}, execute(hybrid_source("", bits=1)))

    def test_malformed_programs_are_rejected_deterministically(self) -> None:
        cases = {
            "missing header": "creg c[1]; classical { r1 = 1; }",
            "header not first": "creg c[1]; OPENQASM 2.0; classical { }",
            "missing classical": "OPENQASM 2.0; creg c[1];",
            "malformed include": "OPENQASM 2.0; include qelib; creg c[1]; classical { }",
            "malformed qreg": "OPENQASM 2.0; qreg q; creg c[1]; classical { }",
            "bad register zero": hybrid_source("r0 = 1;", bits=1),
            "bad register ten": hybrid_source("r10 = 1;", bits=1),
            "unknown identifier": hybrid_source("r1 = value;", bits=1),
            "out of range bit": hybrid_source("r1 = c[1];", bits=1),
            "missing else": hybrid_source("if (c[0] == 0) { r1 = 1; }", bits=1),
            "bad comparison": hybrid_source("if (c[0] = 0) { } else { }", bits=1),
            "unterminated block": "OPENQASM 2.0; creg c[1]; classical { r1 = 1;",
            "duplicate block": (
                "OPENQASM 2.0; creg c[1]; classical { } classical { }"
            ),
            "unterminated string": (
                'OPENQASM 2.0; include "qelib1.inc;\ncreg c[1]; classical { }'
            ),
        }
        for name, source in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(HybridQASMError) as first:
                    compile_hybrid(source)
                with self.assertRaises(HybridQASMError) as second:
                    compile_hybrid(source)
                self.assertEqual(str(first.exception), str(second.exception))


# 下列测试 AST 刻意独立于生产 AST，避免 parser 与参考解释器共享同一个错误。
@dataclass(frozen=True)
class TLiteral:
    value: int


@dataclass(frozen=True)
class TRegister:
    index: int


@dataclass(frozen=True)
class TBit:
    index: int


@dataclass(frozen=True)
class TBinary:
    operator: str
    left: "TExpression"
    right: "TExpression"


TExpression = Union[TLiteral, TRegister, TBit, TBinary]


@dataclass(frozen=True)
class TAssignment:
    target: int
    expression: TExpression


@dataclass(frozen=True)
class TIfElse:
    operator: str
    left: TExpression
    right: TExpression
    then_body: Tuple["TStatement", ...]
    else_body: Tuple["TStatement", ...]


TStatement = Union[TAssignment, TIfElse]


def render_expression(expression: TExpression, compact: bool = False) -> str:
    if isinstance(expression, TLiteral):
        return str(expression.value)
    if isinstance(expression, TRegister):
        return "r%d" % expression.index
    if isinstance(expression, TBit):
        return "c[%d]" % expression.index
    left = render_expression(expression.left, compact=compact)
    right = render_expression(expression.right, compact=compact)
    # 紧凑形式省略左结合链的冗余括号，但保留右子树以维持原 AST 语义。
    if compact and isinstance(expression.right, TBinary):
        right = "(%s)" % right
    rendered = "%s %s %s" % (
        left,
        expression.operator,
        right,
    )
    return rendered if compact else "(%s)" % rendered


def render_statements(
    statements: Sequence[TStatement], indent: str = "  ", compact: bool = False
) -> str:
    lines: List[str] = []
    for statement in statements:
        if isinstance(statement, TAssignment):
            lines.append(
                "%sr%d = %s;"
                % (
                    indent,
                    statement.target,
                    render_expression(statement.expression, compact=compact),
                )
            )
        else:
            lines.append(
                "%sif (%s %s %s) {"
                % (
                    indent,
                    render_expression(statement.left, compact=compact),
                    statement.operator,
                    render_expression(statement.right, compact=compact),
                )
            )
            lines.append(
                render_statements(statement.then_body, indent + "  ", compact=compact)
            )
            lines.append("%s} else {" % indent)
            lines.append(
                render_statements(statement.else_body, indent + "  ", compact=compact)
            )
            lines.append("%s}" % indent)
    return "\n".join(line for line in lines if line)


def evaluate_expression(expression: TExpression, registers: List[int], bits: Sequence[int]) -> int:
    if isinstance(expression, TLiteral):
        return expression.value
    if isinstance(expression, TRegister):
        return registers[expression.index]
    if isinstance(expression, TBit):
        return bits[expression.index]
    left = evaluate_expression(expression.left, registers, bits)
    right = evaluate_expression(expression.right, registers, bits)
    return left + right if expression.operator == "+" else left - right


def interpret(statements: Sequence[TStatement], bits: Sequence[int]) -> List[int]:
    registers = [0] * 10

    def run(items: Sequence[TStatement]) -> None:
        for statement in items:
            if isinstance(statement, TAssignment):
                registers[statement.target] = evaluate_expression(
                    statement.expression, registers, bits
                )
            else:
                left = evaluate_expression(statement.left, registers, bits)
                right = evaluate_expression(statement.right, registers, bits)
                condition = left == right
                if statement.operator == "!=":
                    condition = not condition
                run(statement.then_body if condition else statement.else_body)

    run(statements)
    return registers


def generate_expression(rng: random.Random, bit_count: int, depth: int) -> TExpression:
    if depth <= 0 or rng.random() < 0.52:
        choice = rng.randrange(3)
        if choice == 0:
            return TLiteral(rng.randint(-12, 12))
        if choice == 1:
            return TRegister(rng.randint(1, 9))
        return TBit(rng.randrange(bit_count))
    return TBinary(
        rng.choice(("+", "-")),
        generate_expression(rng, bit_count, depth - 1),
        generate_expression(rng, bit_count, depth - 1),
    )


def generate_statement(rng: random.Random, bit_count: int, depth: int) -> TStatement:
    if depth > 0 and rng.random() < 0.30:
        return TIfElse(
            rng.choice(("==", "!=")),
            generate_expression(rng, bit_count, 2),
            generate_expression(rng, bit_count, 2),
            tuple(generate_statement(rng, bit_count, depth - 1) for _ in range(rng.randint(1, 2))),
            tuple(generate_statement(rng, bit_count, depth - 1) for _ in range(rng.randint(1, 2))),
        )
    return TAssignment(
        rng.randint(1, 9), generate_expression(rng, bit_count, rng.randint(0, 3))
    )


class HiddenLikeDifferentialTests(unittest.TestCase):
    def test_fixed_seed_random_programs_match_reference_interpreter(self) -> None:
        program_count = 0
        input_count = 0
        metamorphic_program_count = 0
        metamorphic_input_count = 0
        for seed in (14, 1401, 1402, 2026, 8675309):
            rng = random.Random(seed)
            for program_index in range(200):
                bit_count = rng.randint(1, 4)
                statements = tuple(
                    generate_statement(rng, bit_count, 2)
                    for _ in range(rng.randint(3, 7))
                )
                body = render_statements(statements, compact=program_index % 2 == 1)
                source = hybrid_source(
                    body,
                    bits=bit_count,
                    before="h q[0];\nmeasure q[0] -> c[0];\n",
                    after="cx q[0], q[1];\n",
                )
                quantum_ops, assembly = compile_hybrid(source)
                self.assertEqual((quantum_ops, assembly), compile_hybrid(source))
                instructions = []
                labels = []
                for line in assembly.splitlines():
                    if line.endswith(":"):
                        labels.append(line)
                    elif line:
                        instructions.append(line.split()[0])
                self.assertLessEqual(
                    set(instructions), {"li", "add", "sub", "addi", "beq", "bne", "j"}
                )
                self.assertEqual(len(labels), len(set(labels)))
                self.assertEqual(
                    ["h q[0];", "measure q[0] -> c[0];", "cx q[0], q[1];"],
                    quantum_ops,
                )
                program_count += 1

                for bits in itertools.product((0, 1), repeat=bit_count):
                    expected = interpret(statements, bits)
                    emulator = TinyRISCVEmulator()
                    emulator.load_program(assembly)
                    for index, value in enumerate(bits):
                        emulator.set_register("x%d" % (10 + index), value)
                    actual = emulator.execute()
                    with self.subTest(
                        seed=seed,
                        program=program_index,
                        bits=bits,
                        source=source,
                    ):
                        self.assertEqual(
                            expected[1:],
                            [actual.get("x%d" % index, 0) for index in range(1, 10)],
                        )
                    input_count += 1

                if program_index < 20:
                    mutated_body = render_statements(statements, compact=True)
                    for spaced, compacted in (
                        (" = ", "="),
                        (" + ", "+"),
                        (" - ", "-"),
                        (" == ", "=="),
                        (" != ", "!="),
                    ):
                        mutated_body = mutated_body.replace(spaced, compacted)
                    mutated_source = hybrid_source(
                        mutated_body,
                        bits=bit_count,
                        before=(
                            "/* { ; classical } 不应改变顶层扫描 */\n"
                            "h/* gate comment */ q[0]; // 行注释\n"
                            "measure q[0]/* mapping */->c[0];\n"
                        ),
                        after="cx q[0]/* comma */ ,q[1];\n",
                    )
                    mutated_quantum_ops, mutated_assembly = compile_hybrid(mutated_source)
                    self.assertEqual(quantum_ops, mutated_quantum_ops)
                    metamorphic_program_count += 1
                    for bits in itertools.product((0, 1), repeat=bit_count):
                        emulator = TinyRISCVEmulator()
                        emulator.load_program(mutated_assembly)
                        for index, value in enumerate(bits):
                            emulator.set_register("x%d" % (10 + index), value)
                        actual = emulator.execute()
                        self.assertEqual(
                            interpret(statements, bits)[1:],
                            [
                                actual.get("x%d" % index, 0)
                                for index in range(1, 10)
                            ],
                        )
                        metamorphic_input_count += 1

        self.assertEqual(1000, program_count)
        self.assertEqual(7698, input_count)
        self.assertEqual(100, metamorphic_program_count)
        self.assertEqual(748, metamorphic_input_count)


if __name__ == "__main__":
    unittest.main()
