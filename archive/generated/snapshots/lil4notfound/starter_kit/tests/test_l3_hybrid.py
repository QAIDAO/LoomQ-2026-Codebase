import unittest

try:
    from starter_kit import adapter
    from starter_kit.riscv_emulator import TinyRISCVEmulator
except ModuleNotFoundError:
    import adapter
    from riscv_emulator import TinyRISCVEmulator


HEADER_1 = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
"""


def execute(assembly, measured):
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    for index, value in enumerate(measured):
        emulator.set_register(f"x{10 + index}", value)
    return emulator.execute()


class HybridCompilerTests(unittest.TestCase):
    def test_public_branch_semantics(self):
        source = HEADER_1 + """
classical {
  if (c[0] == 1) { r1 = 7; } else { r1 = 3; }
}
"""
        quantum, assembly = adapter.compile_hybrid(source)
        self.assertEqual(quantum, ["measure q[0] -> c[0];"])
        self.assertEqual(execute(assembly, (0,)).get("x1"), 3)
        self.assertEqual(execute(assembly, (1,)).get("x1"), 7)

    def test_quantum_statement_order_is_preserved(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q[0] -> c[0];
classical { r1 = c[0] + 1; }
cx q[0], q[1];
measure q[1] -> c[1];
"""
        quantum, _ = adapter.compile_hybrid(source)
        self.assertEqual(
            quantum,
            [
                "h q[0];",
                "measure q[0] -> c[0];",
                "cx q[0], q[1];",
                "measure q[1] -> c[1];",
            ],
        )

    def test_assignment_uses_original_target_value(self):
        source = HEADER_1 + """
classical {
  r1 = 5;
  r2 = 2;
  r1 = r2 + r1;
  r3 = -(r1 - 10) + c[0];
}
"""
        _, assembly = adapter.compile_hybrid(source)
        zero = execute(assembly, (0,))
        one = execute(assembly, (1,))
        self.assertEqual((zero.get("x1"), zero.get("x2"), zero.get("x3")), (7, 2, 3))
        self.assertEqual((one.get("x1"), one.get("x2"), one.get("x3")), (7, 2, 4))

    def test_nested_branches_and_not_equal(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
measure q -> c;
classical {
  if (c[0] != c[1]) {
    r1 = 7;
    if (r1 == 7) { r2 = c[0] + 10; } else { r2 = -1; }
  } else {
    r1 = 3;
    r2 = r1 - 1;
  }
  r3 = r1 + r2;
}
"""
        _, assembly = adapter.compile_hybrid(source)
        expected = {
            (0, 0): (3, 2, 5),
            (0, 1): (7, 10, 17),
            (1, 0): (7, 11, 18),
            (1, 1): (3, 2, 5),
        }
        for measured, registers in expected.items():
            with self.subTest(measured=measured):
                state = execute(assembly, measured)
                self.assertEqual(
                    tuple(state.get(f"x{index}", 0) for index in range(1, 4)),
                    registers,
                )

    def test_expression_and_branch_semantics_for_all_measurements(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
measure q -> c;
classical {
  r1 = c[0] + 3;
  r2 = c[1] - (c[2] - 4);
  if ((r1 - r2) != (c[0] + c[1])) {
    r3 = r1 + r2 - c[2];
  } else {
    r3 = -(r1 - r2);
  }
  r4 = r3 + r1 - r2 + 7;
}
"""
        _, assembly = adapter.compile_hybrid(source)
        for c0 in (0, 1):
            for c1 in (0, 1):
                for c2 in (0, 1):
                    measured = (c0, c1, c2)
                    r1 = c0 + 3
                    r2 = c1 - (c2 - 4)
                    if (r1 - r2) != (c0 + c1):
                        r3 = r1 + r2 - c2
                    else:
                        r3 = -(r1 - r2)
                    expected = (r1, r2, r3, r3 + r1 - r2 + 7)
                    with self.subTest(measured=measured):
                        state = execute(assembly, measured)
                        actual = tuple(state.get(f"x{index}", 0) for index in range(1, 5))
                        self.assertEqual(actual, expected)

    def test_multiple_classical_registers_use_global_offsets(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg left[1];
creg right[1];
measure q[0] -> left[0];
measure q[1] -> right[0];
classical {
  if (left[0] == right[0]) { r1 = 1; } else { r1 = 0; }
}
"""
        _, assembly = adapter.compile_hybrid(source)
        for measured in ((0, 0), (0, 1), (1, 0), (1, 1)):
            with self.subTest(measured=measured):
                expected = int(measured[0] == measured[1])
                self.assertEqual(execute(assembly, measured).get("x1", 0), expected)

    def test_full_measurement_register_range_uses_safe_scratch_registers(self):
        terms = " + ".join(f"c[{index}]" for index in range(22))
        source = f"""OPENQASM 2.0;
include "qelib1.inc";
qreg q[22];
creg c[22];
measure q -> c;
classical {{ r1 = {terms}; }}
"""
        _, assembly = adapter.compile_hybrid(source)
        measured = tuple(index % 2 for index in range(22))
        state = execute(assembly, measured)
        self.assertEqual(state.get("x1"), sum(measured))
        self.assertEqual(state.get("x8", 0), 0)
        self.assertEqual(state.get("x9", 0), 0)

    def test_comments_and_multiple_classical_blocks(self):
        source = HEADER_1 + """
// first stage
classical { r1 = 2; /* retained state */ }
classical {
  if (c[0] == 0) { r2 = r1 + 3; } else { r2 = r1 - 1; }
}
"""
        _, assembly = adapter.compile_hybrid(source)
        self.assertEqual(execute(assembly, (0,)).get("x2"), 5)
        self.assertEqual(execute(assembly, (1,)).get("x2"), 1)

    def test_empty_classical_program_emits_valid_noop(self):
        _, assembly = adapter.compile_hybrid(HEADER_1)
        self.assertEqual(execute(assembly, (0,)), {})

    def test_invalid_classical_programs_are_rejected(self):
        invalid_blocks = (
            "r0 = 1;",
            "r10 = 1;",
            "c[0] = 1;",
            "r1 = 2 * 3;",
            "if (c[0] == 1) { r1 = 1; }",
            "r1 = missing + 1;",
            "r1 = other[0] + 1;",
        )
        for block in invalid_blocks:
            with self.subTest(block=block):
                with self.assertRaises(ValueError):
                    adapter.compile_hybrid(HEADER_1 + f"classical {{ {block} }}")


if __name__ == "__main__":
    unittest.main()
