import unittest

from starter_kit import adapter
from starter_kit.riscv_emulator import TinyRISCVEmulator


BASE = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
measure q -> c;
classical {
%s
}
'''


def run(assembly, x10=0, x11=0):
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    emulator.set_register("x10", x10)
    emulator.set_register("x11", x11)
    return emulator.execute()


class RiscVCodegenTests(unittest.TestCase):
    def test_assignments_support_measurements_arithmetic_and_old_register_values(self):
        _operations, assembly = adapter.compile_hybrid(
            BASE % "r1 = c[1] + 3; r2 = r1 - 2; r1 = r2 + r1;"
        )

        state = run(assembly, x11=1)
        self.assertEqual(state.get("x1", 0), 6)
        self.assertEqual(state.get("x2", 0), 2)
        self.assertNotIn("mul", assembly)
        self.assertNotIn("mv", assembly)

    def test_nested_if_and_not_equal_cover_all_measurement_combinations(self):
        _operations, assembly = adapter.compile_hybrid(
            BASE
            % '''if (c[0] != 0) {
  r1 = 4;
  if (c[1] == 1) { r2 = r1 + 5; } else { r2 = r1 - 1; }
} else { r1 = 9; r2 = r1 - 2; }'''
        )

        expected = {(0, 0): (9, 7), (0, 1): (9, 7), (1, 0): (4, 3), (1, 1): (4, 9)}
        for (x10, x11), (r1, r2) in expected.items():
            state = run(assembly, x10=x10, x11=x11)
            self.assertEqual((state.get("x1", 0), state.get("x2", 0)), (r1, r2))

    def test_out_of_range_measurement_and_register_are_rejected(self):
        with self.assertRaises(ValueError):
            adapter.compile_hybrid(BASE % "r10 = 1;")
        with self.assertRaises(ValueError):
            adapter.compile_hybrid(BASE % "r1 = c[2];")


if __name__ == "__main__":
    unittest.main()
