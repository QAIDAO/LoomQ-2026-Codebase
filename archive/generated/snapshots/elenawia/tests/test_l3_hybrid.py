import unittest

from starter_kit.adapter import compile_hybrid
from starter_kit.riscv_emulator import TinyRISCVEmulator


def execute(assembly, measured_bits):
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    for index, value in enumerate(measured_bits):
        emulator.set_register(f"x{10 + index}", value)
    return emulator.execute()


class L3HybridCompileTests(unittest.TestCase):
    def test_public_branch_case(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
classical { if (c[0] == 1) { r1 = 7; } else { r1 = 3; } }
"""

        quantum_ops, assembly = compile_hybrid(source)

        self.assertEqual(quantum_ops, ["measure q[0] -> c[0];"])
        self.assertEqual(execute(assembly, [0]).get("x1"), 3)
        self.assertEqual(execute(assembly, [1]).get("x1"), 7)

    def test_arithmetic_after_branch(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
measure q[0] -> c[0];
classical {
  if (c[0] != 0) {
    r1 = 100;
  } else {
    r1 = 10;
  }
  r2 = r1 + 5;
  r3 = r2 - 2;
}
"""

        quantum_ops, assembly = compile_hybrid(source)

        self.assertEqual(quantum_ops, ["h q[0];", "measure q[0] -> c[0];"])
        self.assertEqual(execute(assembly, [0]).get("x3"), 13)
        self.assertEqual(execute(assembly, [1]).get("x3"), 103)

    def test_multiple_measurement_bits(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
classical {
  if (c[1] == 1) {
    r1 = c[0] + 20;
  } else {
    r1 = c[0] + 5;
  }
}
"""

        _, assembly = compile_hybrid(source)

        self.assertEqual(execute(assembly, [0, 0]).get("x1"), 5)
        self.assertEqual(execute(assembly, [1, 0]).get("x1"), 6)
        self.assertEqual(execute(assembly, [0, 1]).get("x1"), 20)
        self.assertEqual(execute(assembly, [1, 1]).get("x1"), 21)

    def test_nested_branches_and_compact_spacing(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
classical{if(c[0]==1){if(c[1]!=0){r1=30;}else{r1=20;}}else{r1=10;}r2=r1+c[1]-3;}
"""

        _, assembly = compile_hybrid(source)

        self.assertEqual(execute(assembly, [0, 0]).get("x2"), 7)
        self.assertEqual(execute(assembly, [0, 1]).get("x2"), 8)
        self.assertEqual(execute(assembly, [1, 0]).get("x2"), 17)
        self.assertEqual(execute(assembly, [1, 1]).get("x2"), 28)

    def test_quantum_ops_after_classical_block_are_preserved(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q[0] -> c[0];
classical { r1 = c[0] + 4; }
cx q[0], q[1];
measure q[1] -> c[1];
"""

        quantum_ops, assembly = compile_hybrid(source)

        self.assertEqual(
            quantum_ops,
            ["h q[0];", "measure q[0] -> c[0];", "cx q[0], q[1];", "measure q[1] -> c[1];"],
        )
        self.assertEqual(execute(assembly, [0]).get("x1"), 4)
        self.assertEqual(execute(assembly, [1]).get("x1"), 5)

    def test_if_without_else_leaves_previous_value(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
classical {
  r1 = 4;
  if (c[0] == 1) {
    r1 = r1 + 6;
  }
}
"""

        _, assembly = compile_hybrid(source)

        self.assertEqual(execute(assembly, [0]).get("x1"), 4)
        self.assertEqual(execute(assembly, [1]).get("x1"), 10)

    def test_condition_can_compare_expressions(self):
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
classical {
  if (c[0] + c[1] == 2) {
    r1 = 99;
  } else {
    r1 = c[0] + c[1] + 1;
  }
}
"""

        _, assembly = compile_hybrid(source)

        self.assertEqual(execute(assembly, [0, 0]).get("x1"), 1)
        self.assertEqual(execute(assembly, [1, 0]).get("x1"), 2)
        self.assertEqual(execute(assembly, [0, 1]).get("x1"), 2)
        self.assertEqual(execute(assembly, [1, 1]).get("x1"), 99)


if __name__ == "__main__":
    unittest.main()
