"""L3 hybrid compiler: spec-conformant cases + randomized cross-validation.

Spec conventions (problem_statement.md):
  * classical registers are r1..r9, mapped onto RISC-V x1..x9;
  * measured bits c[k] are injected into registers x10+k by the grader;
  * grammar: integer literals, r1..r9, operators + - == !=, if/else.

Every program is executed two ways over all measurement injections and
must agree:
  1. our reference interpreter (interpret_classical),
  2. the official TinyRISCVEmulator from the starter kit.
"""

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starter_kit.gates import GATES
from starter_kit.hybrid_compiler import (compile_hybrid, interpret_classical,
                                         verify_hybrid)
from starter_kit.parser import parse_source
from starter_kit.riscv_emulator import TinyRISCVEmulator


def official_registers(assembly, injections):
    emu = TinyRISCVEmulator()
    emu.load_program(assembly)          # official order: load, then inject
    for reg, value in injections.items():
        emu.set_register(reg, value)
    result = emu.execute()
    return {reg: int(result.get(reg, 0)) for reg in
            ("x%d" % i for i in range(1, 10))}


def classical_stmts(source):
    program = parse_source(source, GATES)
    return tuple(stmt for block in program.classical_blocks()
                 for stmt in block.body)


def wrap(block_body):
    """Minimal quantum shell around a classical block body."""
    return ("OPENQASM 2.0;\ninclude \"qelib1.inc\";\n"
            "qreg q[2]; creg c[2];\n"
            "h q[0]; cx q[0], q[1];\n"
            "measure q -> c;\n"
            "classical {\n%s\n}" % block_body)


class TestProblemStatementCase(unittest.TestCase):
    SOURCE = ('OPENQASM 2.0;\ninclude "qelib1.inc";\n'
              "qreg q[2];\ncreg c[2];\n"
              "h q[0];\n"
              "measure q[0] -> c[0];\n"
              "classical {\n"
              "  if (c[0] == 1) {\n"
              "    r1 = 100;\n"
              "  } else {\n"
              "    r1 = 10;\n"
              "  }\n"
              "  r1 = r1 + 5;\n"
              "}\n"
              "cx q[0], q[1];\n")

    def test_compile_shape(self):
        quantum_ops, assembly = compile_hybrid(self.SOURCE)
        self.assertEqual(quantum_ops[0].upper().split()[0], "H")
        self.assertTrue(any(op.upper().startswith("MEASURE")
                            for op in quantum_ops))
        self.assertIn("li", assembly.lower())
        self.assertIn("bne", assembly.lower())

    def test_branch_semantics_match_spec(self):
        _, assembly = compile_hybrid(self.SOURCE)
        self.assertEqual(official_registers(assembly, {"x10": 1})["x1"], 105)
        self.assertEqual(official_registers(assembly, {"x10": 0})["x1"], 15)

    def test_verify_report_ok(self):
        report = verify_hybrid(self.SOURCE)
        self.assertTrue(report["ok"])
        self.assertEqual(report["cases"], 2)       # one referenced cbit


class TestAddressingForms(unittest.TestCase):
    def assert_evaluates_to(self, statement, injections, expected):
        _, assembly = compile_hybrid(wrap(statement))
        regs = official_registers(assembly, injections)
        self.assertEqual(regs["x1"], expected,
                         "%r with %r -> %r" % (statement, injections, regs))

    def test_negative_immediate_load(self):
        self.assert_evaluates_to("r1 = -7;", {}, -7)

    def test_register_copy(self):
        self.assert_evaluates_to("r1 = r3;", {"x3": 41}, 41)

    def test_add_immediate(self):
        self.assert_evaluates_to("r1 = r3 + 9;", {"x3": 33}, 42)

    def test_sub_immediate_both_sides(self):
        self.assert_evaluates_to("r1 = r3 - 8;", {"x3": 50}, 42)
        self.assert_evaluates_to("r1 = 50 - r3;", {"x3": 8}, 42)

    def test_reg_plus_reg_and_minus(self):
        self.assert_evaluates_to("r1 = r2 + r3;", {"x2": 40, "x3": 2}, 42)
        self.assert_evaluates_to("r1 = r2 - r3;", {"x2": 44, "x3": 2}, 42)

    def test_constant_folding_with_parentheses(self):
        self.assert_evaluates_to("r1 = (10 - 4) + (5 - 3);", {}, 8)

    def test_sequential_statements_keep_order(self):
        _, assembly = compile_hybrid(wrap("r2 = 40;\nr1 = r2 + r2;"))
        self.assertEqual(official_registers(assembly, {})["x1"], 80)


class TestBranching(unittest.TestCase):
    def test_equality_branch_inversion(self):
        source = wrap("if (c[0] == 1) { r1 = 10; } else { r1 = 20; }")
        _, assembly = compile_hybrid(source)
        self.assertEqual(official_registers(assembly, {"x10": 1})["x1"], 10)
        self.assertEqual(official_registers(assembly, {"x10": 0})["x1"], 20)

    def test_inequality_branch(self):
        source = wrap("if (c[1] != 0) { r1 = 5; } else { r1 = 6; }")
        _, assembly = compile_hybrid(source)
        self.assertEqual(official_registers(assembly, {"x11": 1})["x1"], 5)
        self.assertEqual(official_registers(assembly, {"x11": 0})["x1"], 6)

    def test_reversed_operand_order(self):
        source = wrap("if (1 == c[0]) { r1 = 8; } else { r1 = 9; }")
        _, assembly = compile_hybrid(source)
        self.assertEqual(official_registers(assembly, {"x10": 1})["x1"], 8)
        self.assertEqual(official_registers(assembly, {"x10": 0})["x1"], 9)

    def test_nested_ifs_else_if_chain(self):
        body = ("if (c[0] == 1) {\n"
                "    if (c[1] == 1) { r1 = 3; } else { r1 = 2; }\n"
                "} else {\n"
                "    r1 = 5;\n"
                "}")
        source = wrap(body)
        report = verify_hybrid(source)
        self.assertTrue(report["ok"])
        self.assertEqual(report["cases"], 4)
        stmts = classical_stmts(source)
        for bits in ((0, 0), (0, 1), (1, 0), (1, 1)):
            expected = interpret_classical(
                stmts, dict(enumerate(bits)))
            injections = {"x%d" % (10 + i): b for i, b in enumerate(bits)}
            _, assembly = compile_hybrid(source)
            got = official_registers(assembly, injections)["x1"]
            self.assertEqual(got, expected[1], "bits=%r" % (bits,))


class TestRandomizedCrossValidation(unittest.TestCase):
    """Fuzz: random spec-grammar programs agree everywhere."""

    def test_sixty_random_programs(self):
        rng = random.Random(20260823)
        for case_index in range(60):
            source = _random_program(rng)
            try:
                report = verify_hybrid(source)
            except Exception as exc:
                self.fail("verify crashed on case %d: %r\n%s"
                          % (case_index, exc, source))
            if not report["ok"]:
                self.fail("mismatch on case %d: %s\n%s"
                          % (case_index, report["mismatches"][:3], source))
            quantum_ops, assembly = compile_hybrid(source)
            stmts = classical_stmts(source)
            n_bits = max(_referenced_bits(stmts)) + 1 \
                if _referenced_bits(stmts) else 1
            for mask in range(1 << min(n_bits, 4)):
                bits = [(mask >> i) & 1 for i in range(min(n_bits, 4))]
                expected = interpret_classical(stmts, dict(enumerate(bits)))
                injections = {"x%d" % (10 + i): b
                              for i, b in enumerate(bits)}
                got = official_registers(assembly, injections)
                for rid in range(1, 10):
                    self.assertEqual(
                        got["x%d" % rid], expected[rid],
                        "case %d bits=%r register r%d\n%s"
                        % (case_index, bits, rid, source))


def _referenced_bits(stmts):
    found = set()
    for stmt in stmts:
        if hasattr(stmt, "cond"):
            found.add(stmt.cond.cbit.index)
        if hasattr(stmt, "then_body"):
            found |= _referenced_bits(stmt.then_body)
            found |= _referenced_bits(stmt.else_body)
    return found


def _random_program(rng: random.Random) -> str:
    lines = []
    depth = 0
    else_used = []                       # one flag per open if-statement
    for _step in range(rng.randint(3, 8)):
        indent = "    " * (depth + 1)
        roll = rng.random()
        if roll < 0.28 and depth < 2:
            comparator = "==" if rng.random() < 0.65 else "!="
            bit_index = rng.randint(0, 1)
            literal = rng.randint(0, 1)
            operands = ["c[%d]" % bit_index, str(literal)]
            if rng.random() < 0.3:
                operands.reverse()
            lines.append("%sif (%s %s %s) {"
                         % (indent, operands[0], comparator, operands[1]))
            depth += 1
            else_used.append(False)
            continue
        if roll < 0.38 and depth > 0 and not else_used[-1]:
            # close then-branch, open its sibling; net depth unchanged
            lines.append("%s} else {" % ("    " * (depth + 1)))
            else_used[-1] = True
            continue
        target = "r%d" % rng.randint(1, 4)
        kind = rng.choice(["imm", "neg_imm", "copy", "add_imm",
                           "sub_imm", "sub_rev", "reg_reg"])
        if kind == "imm":
            expr = str(rng.randint(-30, 30))
        elif kind == "neg_imm":
            expr = "-%d" % rng.randint(1, 30)
        elif kind == "copy":
            expr = "r%d" % rng.randint(1, 4)
        elif kind == "add_imm":
            expr = "r%d + %d" % (rng.randint(1, 4), rng.randint(-20, 20))
        elif kind == "sub_imm":
            expr = "r%d - %d" % (rng.randint(1, 4), rng.randint(-20, 20))
        elif kind == "sub_rev":
            expr = "%d - r%d" % (rng.randint(0, 20), rng.randint(1, 4))
        else:
            expr = "r%d + r%d" % (rng.randint(1, 4), rng.randint(1, 4))
        lines.append("%s%s = %s;" % (indent, target, expr))
    while depth > 0:
        depth -= 1
        else_used.pop()
        lines.append("%s}" % ("    " * (depth + 1)))
    return wrap("\n".join(lines))


if __name__ == "__main__":
    unittest.main()
