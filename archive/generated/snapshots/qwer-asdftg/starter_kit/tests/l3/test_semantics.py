import random
import re
import unittest

from starter_kit import adapter
from starter_kit.riscv_emulator import TinyRISCVEmulator


def source(a, b, pivot, delta):
    return '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
measure q -> c;
classical {
  if (c[0] == 1) { r1 = %d; } else { r1 = %d; }
  r2 = r1 + c[1];
  if (r2 != %d) { r3 = r2 - %d; } else { r3 = r2 + %d; }
}
x q[0];
''' % (a, b, pivot, delta, delta)


class SemanticRegressionTests(unittest.TestCase):
    def test_seeded_programs_match_reference_for_all_measurement_inputs(self):
        rng = random.Random(20260824)
        allowed = {"li", "add", "sub", "addi", "beq", "bne", "j"}
        for _case in range(12):
            a, b, pivot, delta = (rng.randrange(-8, 9) for _ in range(4))
            operations, assembly = adapter.compile_hybrid(source(a, b, pivot, delta))
            self.assertEqual(operations[-2:], ["measure q -> c;", "x q[0];"])
            mnemonics = {
                line.split()[0]
                for line in assembly.splitlines()
                if line.strip() and not line.rstrip().endswith(":")
            }
            self.assertTrue(mnemonics <= allowed)
            for c0 in (0, 1):
                for c1 in (0, 1):
                    r1 = a if c0 == 1 else b
                    r2 = r1 + c1
                    r3 = r2 - delta if r2 != pivot else r2 + delta
                    emulator = TinyRISCVEmulator()
                    emulator.load_program(assembly)
                    emulator.set_register("x10", c0)
                    emulator.set_register("x11", c1)
                    actual = emulator.execute()
                    self.assertEqual(
                        (actual.get("x1", 0), actual.get("x2", 0), actual.get("x3", 0)),
                        (r1, r2, r3),
                        msg="case=%r c=(%d,%d)" % ((a, b, pivot, delta), c0, c1),
                    )

    def test_mixed_expression_conditions_and_three_measurement_bits(self):
        program = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
measure q -> c;
classical {
  r1 = c[0] - c[1] + 2;
  if (c[0] + r1 == c[2] + 3) {
    r2 = r1 + c[2];
    if (r2 != c[1] + 2) { r3 = r2 - c[0]; } else { r3 = r2 + c[0]; }
  } else {
    r2 = r1 - c[2];
    r3 = r2 + c[1];
  }
}
cx q[0], q[1];
'''
        operations, assembly = adapter.compile_hybrid(program)
        self.assertEqual(operations[-2:], ["measure q -> c;", "cx q[0], q[1];"])
        for c0 in (0, 1):
            for c1 in (0, 1):
                for c2 in (0, 1):
                    r1 = c0 - c1 + 2
                    if c0 + r1 == c2 + 3:
                        r2 = r1 + c2
                        r3 = r2 - c0 if r2 != c1 + 2 else r2 + c0
                    else:
                        r2 = r1 - c2
                        r3 = r2 + c1
                    emulator = TinyRISCVEmulator()
                    emulator.load_program(assembly)
                    emulator.set_register("x10", c0)
                    emulator.set_register("x11", c1)
                    emulator.set_register("x12", c2)
                    actual = emulator.execute()
                    self.assertEqual(
                        (actual.get("x1", 0), actual.get("x2", 0), actual.get("x3", 0)),
                        (r1, r2, r3),
                        msg="c=(%d,%d,%d)" % (c0, c1, c2),
                    )


if __name__ == "__main__":
    unittest.main()
