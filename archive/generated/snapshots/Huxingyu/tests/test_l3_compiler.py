import itertools
import random
import unittest

from starter_kit.adapter import compile_hybrid
from starter_kit.riscv_emulator import TinyRISCVEmulator


def hybrid(classical, quantum_before="h q[0];\nmeasure q[0] -> c[0];", quantum_after=""):
    return f'''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
{quantum_before}
classical {{
{classical}
}}
{quantum_after}
'''


def execute(assembly, measured):
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    for index, value in enumerate(measured):
        emulator.set_register(f"x{10 + index}", value)
    return emulator.execute()


class HybridCompilerTests(unittest.TestCase):
    def test_public_branch_and_quantum_operation_order(self):
        source = hybrid(
            "if (c[0] == 1) { r1 = 100; } else { r1 = 10; }\nr1 = r1 + 5;",
            quantum_after="cx q[0], q[1];",
        )
        operations, assembly = compile_hybrid(source)
        self.assertEqual(operations, [
            "h q[0];", "measure q[0] -> c[0];", "cx q[0], q[1];",
        ])
        self.assertEqual(execute(assembly, (0,)).get("x1"), 15)
        self.assertEqual(execute(assembly, (1,)).get("x1"), 105)

    def test_nested_branches_negative_values_and_expression_chains(self):
        source = hybrid("""
r1 = -5;
if (c[0] != c[1]) {
  if (c[2] == 1) { r2 = r1 + 12 - 2; } else { r2 = 30 - r1; }
} else {
  r2 = c[0] + c[1] + 7;
}
r3 = r2 - r1;
""")
        _, assembly = compile_hybrid(source)
        for bits in itertools.product((0, 1), repeat=3):
            if bits[0] != bits[1]:
                expected_r2 = 5 if bits[2] else 35
            else:
                expected_r2 = bits[0] + bits[1] + 7
            state = execute(assembly, bits)
            self.assertEqual(state.get("x1"), -5, bits)
            self.assertEqual(state.get("x2"), expected_r2, bits)
            self.assertEqual(state.get("x3"), expected_r2 + 5, bits)

    def test_all_condition_shapes_are_exhaustive(self):
        source = hybrid("""
r1 = c[0] + 3;
r2 = c[1] - 2;
if (r1 == r2) { r3 = r1 + r2; } else { r3 = r1 - r2; }
if (r3 != 0) { r4 = 9; } else { r4 = -9; }
""")
        _, assembly = compile_hybrid(source)
        for bits in itertools.product((0, 1), repeat=2):
            r1, r2 = bits[0] + 3, bits[1] - 2
            r3 = r1 + r2 if r1 == r2 else r1 - r2
            state = execute(assembly, bits)
            self.assertEqual(state.get("x1"), r1, bits)
            self.assertEqual(state.get("x2"), r2, bits)
            self.assertEqual(state.get("x3", 0), r3, bits)
            self.assertEqual(state.get("x4"), 9 if r3 != 0 else -9, bits)

    def test_measurement_registers_are_not_used_as_temporaries(self):
        source = hybrid("r1 = c[18] + 40; if (c[19] == 1) { r2 = 2; } else { r2 = 3; }")
        _, assembly = compile_hybrid(source)
        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        emulator.set_register("x28", 2)
        emulator.set_register("x29", 1)
        state = emulator.execute()
        self.assertEqual(state.get("x1"), 42)
        self.assertEqual(state.get("x2"), 2)

    def test_invalid_classical_programs_fail_closed(self):
        invalid = (
            hybrid("r10 = 1;"),
            hybrid("c[0] = 1;"),
            hybrid("if (c[0] == 1) { r1 = 1; }"),
            hybrid("r1 = unknown;"),
        )
        for source in invalid:
            with self.assertRaises(ValueError):
                compile_hybrid(source)

    def test_seeded_random_programs_match_reference_semantics(self):
        for seed in range(80):
            rng = random.Random(seed)
            a, b, c, d = (rng.randint(-20, 20) for _ in range(4))
            first_op, second_op, tail_op = (rng.choice(("+", "-")) for _ in range(3))
            comparison = rng.choice(("==", "!="))
            source = hybrid(f"""
r1 = c[0] {first_op} {a};
r2 = c[1] {second_op} {b};
if (r1 {comparison} r2) {{ r3 = r1 + {c}; }} else {{ r3 = r2 - {d}; }}
r4 = r3 {tail_op} r1;
""")
            _, assembly = compile_hybrid(source)
            for bits in itertools.product((0, 1), repeat=2):
                r1 = bits[0] + a if first_op == "+" else bits[0] - a
                r2 = bits[1] + b if second_op == "+" else bits[1] - b
                condition = (r1 == r2) if comparison == "==" else (r1 != r2)
                r3 = r1 + c if condition else r2 - d
                r4 = r3 + r1 if tail_op == "+" else r3 - r1
                state = execute(assembly, bits)
                self.assertEqual(state.get("x1", 0), r1, (seed, bits))
                self.assertEqual(state.get("x2", 0), r2, (seed, bits))
                self.assertEqual(state.get("x3", 0), r3, (seed, bits))
                self.assertEqual(state.get("x4", 0), r4, (seed, bits))


if __name__ == "__main__":
    unittest.main()
