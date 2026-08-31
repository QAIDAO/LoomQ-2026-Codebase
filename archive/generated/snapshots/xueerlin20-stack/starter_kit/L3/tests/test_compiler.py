from __future__ import annotations

import re
import unittest

from starter_kit.L3 import HybridSyntaxError, compile_hybrid
from starter_kit.riscv_emulator import TinyRISCVEmulator


HEADER = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[{qubits}];
creg c[{cbits}];
"""


def execute(assembly: str, measurements=()):
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    for index, value in enumerate(measurements):
        emulator.set_register("x%d" % (10 + index), value)
    return emulator.execute()


class HybridCompilerTests(unittest.TestCase):
    def test_public_sample_and_quantum_order(self):
        source = HEADER.format(qubits=2, cbits=2) + """
h q[0];
measure q[0] -> c[0];
classical {
  if (c[0] == 1) { r1 = 100; } else { r1 = 10; }
  r1 = r1 + 5;
}
cx q[0], q[1];
"""
        quantum, assembly = compile_hybrid(source)
        self.assertEqual(
            quantum,
            [
                "h q[0];",
                "measure q[0] -> c[0];",
                "cx q[0], q[1];",
            ],
        )
        self.assertEqual(execute(assembly, [0]).get("x1"), 15)
        self.assertEqual(execute(assembly, [1]).get("x1"), 105)

    def test_compact_input_and_comments(self):
        source = (
            'OPENQASM 2.0; include "qelib1.inc"; qreg q[1]; creg c[1]; '
            "x q[0]; // classical { ignored }\n"
            "classical { r1 = 2; if (c[0] != 0) { r1 = r1 + 8; } "
            "else { r1 = r1 - 1; } } measure q[0] -> c[0];"
        )
        quantum, assembly = compile_hybrid(source)
        self.assertEqual(quantum, ["x q[0];", "measure q[0] -> c[0];"])
        self.assertEqual(execute(assembly, [0]).get("x1"), 1)
        self.assertEqual(execute(assembly, [1]).get("x1"), 10)

    def test_nested_branches_and_multiple_measurements(self):
        source = HEADER.format(qubits=3, cbits=3) + """
measure q -> c;
classical {
  r1 = 3;
  if (c[0] != c[1]) {
    r2 = r1 + 7;
    if (c[2] == 1) { r3 = r2 - r1; } else { r3 = r2 + r1; }
  } else {
    r2 = 4;
    r3 = r2 - 9;
  }
  r4 = 20 - r2;
}
"""
        _, assembly = compile_hybrid(source)
        for c0 in (0, 1):
            for c1 in (0, 1):
                for c2 in (0, 1):
                    state = execute(assembly, [c0, c1, c2])
                    if c0 != c1:
                        self.assertEqual(state.get("x2"), 10)
                        self.assertEqual(state.get("x3"), 7 if c2 else 13)
                        self.assertEqual(state.get("x4"), 10)
                    else:
                        self.assertEqual(state.get("x2"), 4)
                        self.assertEqual(state.get("x3"), -5)
                        self.assertEqual(state.get("x4"), 16)

    def test_assignment_preserves_aliased_rhs_values(self):
        source = HEADER.format(qubits=1, cbits=1) + """
measure q[0] -> c[0];
classical {
  r1 = 7;
  r2 = 3;
  r1 = r2 + r1;
  r2 = 20 - r2;
  r3 = -r1 + r2 - 2;
}
"""
        _, assembly = compile_hybrid(source)
        state = execute(assembly, [0])
        self.assertEqual(state.get("x1"), 10)
        self.assertEqual(state.get("x2"), 17)
        self.assertEqual(state.get("x3"), 5)

    def test_register_and_measurement_copy(self):
        source = HEADER.format(qubits=2, cbits=2) + """
measure q -> c;
classical { r1 = c[1]; r2 = r1; }
"""
        _, assembly = compile_hybrid(source)
        state = execute(assembly, [0, 1])
        self.assertEqual(state.get("x1"), 1)
        self.assertEqual(state.get("x2"), 1)

    def test_all_output_registers_map_to_x1_through_x9(self):
        assignments = "\n".join(
            "r%d = %d;" % (index, index * 11) for index in range(1, 10)
        )
        source = HEADER.format(qubits=1, cbits=1) + """
measure q[0] -> c[0];
classical {
%s
}
""" % assignments
        _, assembly = compile_hybrid(source)
        state = execute(assembly, [1])

        for index in range(1, 10):
            self.assertEqual(state.get("x%d" % index), index * 11)

    def test_measurement_registers_map_to_x10_upward_and_are_preserved(self):
        source = HEADER.format(qubits=3, cbits=3) + """
measure q -> c;
classical { r1 = c[0]; r2 = c[1]; r3 = c[2]; }
"""
        _, assembly = compile_hybrid(source)
        state = execute(assembly, [1, 0, 1])

        self.assertEqual(
            [state.get("x%d" % index, 0) for index in (1, 2, 3)],
            [1, 0, 1],
        )
        self.assertEqual(
            [state.get("x%d" % index, 0) for index in (10, 11, 12)],
            [1, 0, 1],
        )

    def test_two_conditions_update_the_same_register_in_sequence(self):
        source = HEADER.format(qubits=2, cbits=2) + """
measure q -> c;
classical {
  if (c[0] == 1) { r1 = 10; } else { r1 = 20; }
  if (c[1] == 1) { r1 = r1 + 5; } else { r1 = r1 + 0; }
}
"""
        _, assembly = compile_hybrid(source)
        expected = {
            (0, 0): 20,
            (0, 1): 25,
            (1, 0): 10,
            (1, 1): 15,
        }

        for measurements, value in expected.items():
            with self.subTest(c0=measurements[0], c1=measurements[1]):
                state = execute(assembly, measurements)
                self.assertEqual(state.get("x1"), value)

    def test_negative_parenthesized_and_self_referential_expressions(self):
        source = HEADER.format(qubits=1, cbits=1) + """
measure q[0] -> c[0];
classical {
  r1 = -10;
  r2 = r1;
  r3 = r2 + 15;
  r4 = 20 - r3;
  r1 = r1 + 5;
  r5 = (r4 + r3) - r1;
}
"""
        _, assembly = compile_hybrid(source)
        state = execute(assembly, [0])

        self.assertEqual(
            [state.get("x%d" % index) for index in range(1, 6)],
            [-5, -10, 5, 15, 25],
        )

    def test_emits_only_supported_instructions(self):
        source = HEADER.format(qubits=1, cbits=1) + """
measure q[0] -> c[0];
classical {
  r1 = 4;
  r2 = 9;
  if (c[0] == 1) { r3 = r1 + r2; } else { r3 = r2 - r1; }
}
"""
        _, assembly = compile_hybrid(source)
        instructions = []
        for line in assembly.splitlines():
            line = line.strip()
            if line and not line.endswith(":"):
                instructions.append(line.split()[0])
        self.assertLessEqual(
            set(instructions), {"li", "add", "sub", "addi", "beq", "bne", "j"}
        )

    def test_rejects_out_of_range_classical_bit(self):
        source = HEADER.format(qubits=1, cbits=1) + """
measure q[0] -> c[0];
classical { r1 = c[1]; }
"""
        with self.assertRaisesRegex(HybridSyntaxError, r"c\[1\].*outside"):
            compile_hybrid(source)

    def test_rejects_invalid_assignment_register(self):
        source = HEADER.format(qubits=1, cbits=1) + """
measure q[0] -> c[0];
classical { r10 = 3; }
"""
        with self.assertRaisesRegex(HybridSyntaxError, "r1..r9"):
            compile_hybrid(source)

    def test_rejects_missing_else(self):
        source = HEADER.format(qubits=1, cbits=1) + """
measure q[0] -> c[0];
classical { if (c[0] == 1) { r1 = 3; } }
"""
        with self.assertRaisesRegex(HybridSyntaxError, "else"):
            compile_hybrid(source)

    def test_labels_are_unique(self):
        source = HEADER.format(qubits=2, cbits=2) + """
measure q -> c;
classical {
  if (c[0] == 0) { r1 = 1; } else { r1 = 2; }
  if (c[1] != 0) { r2 = 3; } else { r2 = 4; }
}
"""
        _, assembly = compile_hybrid(source)
        labels = re.findall(r"^(L3_[A-Za-z0-9_]+):$", assembly, re.MULTILINE)
        self.assertEqual(len(labels), len(set(labels)))


if __name__ == "__main__":
    unittest.main()
