from __future__ import annotations

import random
import re
import unittest

from starter_kit import adapter
from starter_kit.riscv_emulator import TinyRISCVEmulator


PUBLIC_BRANCH = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q[0] -> c[0];
classical {
  if (c[0] == 1) {
    r1 = 100;
  } else {
    r1 = 10;
  }
  r1 = r1 + 5;
}
cx q[0], q[1];
"""


def execute(source: str, measurements: tuple[int, ...]) -> tuple[list[str], dict[str, int], str]:
    quantum_ops, assembly = adapter.compile_hybrid(source)
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    for index, value in enumerate(measurements):
        emulator.set_register(f"x{10 + index}", value)
    return quantum_ops, emulator.execute(), assembly


def reference_expr(expression, registers: dict[int, int], measurements: tuple[int, ...]) -> int:
    kind = expression[0]
    if kind == "int":
        return expression[1]
    if kind == "reg":
        return registers.get(expression[1], 0)
    if kind == "measurement":
        return measurements[expression[1]]
    left = reference_expr(expression[1], registers, measurements)
    right = reference_expr(expression[2], registers, measurements)
    return left + right if kind == "add" else left - right


def reference_execute(statements, measurements: tuple[int, ...]) -> dict[int, int]:
    registers: dict[int, int] = {}

    def run(block) -> None:
        for statement in block:
            if statement[0] == "assign":
                registers[statement[1]] = reference_expr(statement[2], registers, measurements)
                continue
            left = reference_expr(statement[1], registers, measurements)
            right = reference_expr(statement[3], registers, measurements)
            condition = left == right if statement[2] == "==" else left != right
            run(statement[4] if condition else statement[5])

    run(statements)
    return registers


def render_expr(expression) -> str:
    kind = expression[0]
    if kind == "int":
        return str(expression[1])
    if kind == "reg":
        return f"r{expression[1]}"
    if kind == "measurement":
        return f"c[{expression[1]}]"
    operator = "+" if kind == "add" else "-"
    return f"({render_expr(expression[1])} {operator} {render_expr(expression[2])})"


def render_statements(statements, indent: str = "  ") -> str:
    lines: list[str] = []
    for statement in statements:
        if statement[0] == "assign":
            lines.append(f"{indent}r{statement[1]} = {render_expr(statement[2])};")
            continue
        lines.append(
            f"{indent}if ({render_expr(statement[1])} {statement[2]} {render_expr(statement[3])}) {{"
        )
        lines.append(render_statements(statement[4], indent + "  "))
        lines.append(f"{indent}}} else {{")
        lines.append(render_statements(statement[5], indent + "  "))
        lines.append(f"{indent}}}")
    return "\n".join(lines)


class HybridCompilerContractTests(unittest.TestCase):
    def test_public_branch_preserves_quantum_order_and_classical_semantics(self):
        expected_ops = ["h q[0];", "measure q[0] -> c[0];", "cx q[0], q[1];"]

        zero_ops, zero, zero_asm = execute(PUBLIC_BRANCH, (0,))
        one_ops, one, one_asm = execute(PUBLIC_BRANCH, (1,))

        self.assertEqual(zero_ops, expected_ops)
        self.assertEqual(one_ops, expected_ops)
        self.assertEqual(zero.get("x1"), 15)
        self.assertEqual(one.get("x1"), 105)
        self.assertEqual(zero_asm, one_asm)

    def test_arithmetic_measurements_nested_branches_and_repeated_writes(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[1];
classical {
  r1 = c[0];
  r2 = -3;
  r3 = r1 + 5 - r2;
  if (r3 != 8) {
    if (c[1] == 1) { r4 = r3 + c[1]; } else { r4 = r3 - 2; }
  } else {
    r4 = 99;
  }
  r1 = r4 - r2;
}
measure q[1] -> c[1];
"""
        expected = {
            (0, 0): 102,
            (0, 1): 102,
            (1, 0): 10,
            (1, 1): 13,
        }

        for bits, r1 in expected.items():
            with self.subTest(bits=bits):
                ops, registers, _assembly = execute(source, bits)
                self.assertEqual(ops, ["x q[1];", "measure q[1] -> c[1];"])
                self.assertEqual(registers.get("x1"), r1)
                self.assertEqual(registers.get("x2"), -3)

    def test_multiple_classical_blocks_execute_sequentially(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
classical { r1 = 4; }
measure q[0] -> c[0];
classical { r1 = r1 + c[0]; r2 = r1 - 1; }
"""

        for measured, expected in ((0, (4, 3)), (1, (5, 4))):
            with self.subTest(measured=measured):
                _ops, registers, _assembly = execute(source, (measured,))
                self.assertEqual((registers.get("x1"), registers.get("x2")), expected)

    def test_comments_whitespace_and_left_associative_subtraction(self):
        source = """// heading
OPENQASM 2.0; include "qelib1.inc";
qreg q[1]; creg c[1];
h q[0]; /* keep quantum order */
classical {
  r1 = 20 - 5 - 3; // (20 - 5) - 3
  if ((r1 + 1) == 13) { r2 = +7; } else { r2 = 0; }
}
measure q[0] -> c[0];
"""
        _ops, registers, _assembly = execute(source, (0,))
        self.assertEqual(registers.get("x1"), 12)
        self.assertEqual(registers.get("x2"), 7)

    def test_deterministic_randomized_programs_match_reference_interpreter(self):
        generator = random.Random(26082026)
        for case_index in range(80):
            a = generator.randint(-20, 20)
            b = generator.randint(-20, 20)
            delta = generator.randint(-9, 9)
            branch_delta = generator.randint(-7, 7)
            op = generator.choice(("==", "!="))
            statements = (
                ("assign", 1, ("int", a)),
                ("assign", 2, ("add", ("measurement", 0), ("int", b))),
                (
                    "assign",
                    3,
                    ("sub", ("add", ("reg", 1), ("reg", 2)), ("int", delta)),
                ),
                (
                    "if",
                    ("measurement", 1),
                    op,
                    ("measurement", 0),
                    (("assign", 3, ("add", ("reg", 3), ("int", branch_delta))),),
                    (("assign", 3, ("sub", ("reg", 3), ("int", branch_delta))),),
                ),
                ("assign", 4, ("add", ("reg", 3), ("reg", 1))),
            )
            source = f"""OPENQASM 2.0;
include "qelib1.inc";
qreg q[2]; creg c[2];
h q[0];
classical {{
{render_statements(statements)}
}}
measure q[0] -> c[0]; measure q[1] -> c[1];
"""
            for c0 in (0, 1):
                for c1 in (0, 1):
                    expected = reference_execute(statements, (c0, c1))
                    with self.subTest(case=case_index, c0=c0, c1=c1):
                        _ops, registers, _assembly = execute(source, (c0, c1))
                        for register, value in expected.items():
                            self.assertEqual(registers.get(f"x{register}", 0), value)

    def test_rejects_malformed_or_unsafe_hybrid_source(self):
        cases = {
            "no classical block": PUBLIC_BRANCH.replace("classical {", "not_classical {"),
            "unbalanced brace": PUBLIC_BRANCH.replace("  r1 = r1 + 5;\n}", "  r1 = r1 + 5;"),
            "missing assignment semicolon": PUBLIC_BRANCH.replace("r1 = 100;", "r1 = 100"),
            "measurement write": PUBLIC_BRANCH.replace("r1 = 100;", "c[0] = 100;"),
            "invalid user register": PUBLIC_BRANCH.replace("r1 = 100;", "r10 = 100;"),
            "unsupported multiplication": PUBLIC_BRANCH.replace("r1 = 100;", "r1 = 2 * 50;"),
            "missing else": PUBLIC_BRANCH.replace("} else {\n    r1 = 10;", "}\n    r1 = 10;"),
            "unterminated comment": PUBLIC_BRANCH + "/*",
        }
        for label, source in cases.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                adapter.compile_hybrid(source)

    def test_output_is_deterministic_labels_are_unique_and_high_measurement_bits_work(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1]; creg c[22];
h q[0];
classical {
  if (c[21] != 0) { r1 = c[21] + 9; } else { r1 = -9; }
  if (r1 == 10) { r2 = r1 - 3; } else { r2 = r1 + 3; }
}
measure q[0] -> c[21];
"""
        first_ops, first_assembly = adapter.compile_hybrid(source)
        second_ops, second_assembly = adapter.compile_hybrid(source)
        self.assertEqual((first_ops, first_assembly), (second_ops, second_assembly))
        labels = re.findall(r"^(L3_[A-Z]+_\d+):", first_assembly, flags=re.MULTILINE)
        self.assertEqual(len(labels), len(set(labels)))
        for measured, expected in ((0, (-9, -6)), (1, (10, 7))):
            emulator = TinyRISCVEmulator()
            emulator.load_program(first_assembly)
            emulator.set_register("x31", measured)
            registers = emulator.execute()
            self.assertEqual((registers.get("x1"), registers.get("x2")), expected)


if __name__ == "__main__":
    unittest.main()
