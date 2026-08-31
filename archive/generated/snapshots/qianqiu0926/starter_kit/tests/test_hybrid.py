import random
import unittest

from loomq.hybrid import HybridSyntaxError, compile_hybrid_program
from riscv_emulator import TinyRISCVEmulator


def program(classical):
    return f'''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q[0] -> c[0];
classical {{ {classical} }}
cx q[0], q[1];
measure q[1] -> c[1];
'''


class HybridCompilerTests(unittest.TestCase):
    def run_assembly(self, assembly, c0, c1):
        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        emulator.set_register("x10", c0)
        emulator.set_register("x11", c1)
        return emulator.execute()

    def test_quantum_operation_order_survives_classical_extraction(self):
        operations, _ = compile_hybrid_program(program("r1 = 1;"))
        self.assertEqual(operations, [
            "h q[0];",
            "measure q[0] -> c[0];",
            "cx q[0], q[1];",
            "measure q[1] -> c[1];",
        ])

    def test_nested_random_branches_match_reference(self):
        for seed in range(80):
            rng = random.Random(seed)
            a, b, k, m = (rng.randint(-30, 30) for _ in range(4))
            bit0, bit1 = rng.randint(0, 1), rng.randint(0, 1)
            source = program(f'''
                r1 = {a};
                r2 = {b};
                if (c[0] == {bit0}) {{
                    r1 = r1 + r2;
                    if (c[1] != {bit1}) {{ r2 = r1 - {k}; }}
                    else {{ r2 = r1 + {m}; }}
                }} else {{
                    r1 = r1 - r2;
                    r2 = r1 + {k};
                }}
                r3 = r1 - r2;
            ''')
            _, assembly = compile_hybrid_program(source)
            for c0 in (0, 1):
                for c1 in (0, 1):
                    expected_r1, expected_r2 = a, b
                    if c0 == bit0:
                        expected_r1 = expected_r1 + expected_r2
                        expected_r2 = expected_r1 - k if c1 != bit1 else expected_r1 + m
                    else:
                        expected_r1 = expected_r1 - expected_r2
                        expected_r2 = expected_r1 + k
                    expected = {1: expected_r1, 2: expected_r2, 3: expected_r1 - expected_r2}
                    state = self.run_assembly(assembly, c0, c1)
                    for register, value in expected.items():
                        with self.subTest(seed=seed, c0=c0, c1=c1, register=register):
                            self.assertEqual(state.get(f"x{register}", 0), value)
                    self.assertFalse(any(name in state for name in ("x30", "x31")))

    def test_invalid_classical_inputs_fail_closed(self):
        invalid = [
            program("r10 = 1;"),
            program("r1 = c[2];"),
            program("if (c[0] == 1) { r1 = 2;"),
            program("while (c[0] == 1) { r1 = 2; }"),
        ]
        for source in invalid:
            with self.subTest(source=source), self.assertRaises(HybridSyntaxError):
                compile_hybrid_program(source)

    def test_expression_reuses_two_remaining_scratch_registers(self):
        source = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[20];
creg c[20];
measure q -> c;
classical { r1 = 1 + 2 + 3 - 4; r2 = -r1; }
'''
        _, assembly = compile_hybrid_program(source)
        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        state = emulator.execute()
        self.assertEqual(state.get("x1"), 2)
        self.assertEqual(state.get("x2"), -2)
        self.assertFalse(any(name in state for name in ("x30", "x31")))


if __name__ == "__main__":
    unittest.main()
