"""Contract and edge-case tests for deterministic Hybrid compilation."""

from __future__ import annotations

import itertools
import unittest

from loomq.hybrid import (
    RegisterExhaustionError,
    compile_hybrid_program,
    interpret_hybrid_program,
)
from riscv_emulator import TinyRISCVEmulator


def _emulate(assembly: str, measurements: tuple[int, ...]) -> dict[int, int]:
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    for index, value in enumerate(measurements):
        emulator.set_register(f"x{10 + index}", value)
    emulator.execute()
    return {index: emulator.get_register(f"x{index}") for index in range(1, 10)}


def _assert_differential(
    case: unittest.TestCase, source: str, measurement_count: int
) -> None:
    _, assembly = compile_hybrid_program(source)
    for bits in itertools.product((0, 1), repeat=measurement_count):
        actual = _emulate(assembly, bits)
        expected_named = interpret_hybrid_program(
            source, {index: value for index, value in enumerate(bits)}
        )
        expected = {index: expected_named[f"r{index}"] for index in range(1, 10)}
        case.assertEqual(actual, expected, msg=f"measurements={bits}\n{assembly}")


class HybridCompilerTests(unittest.TestCase):
    def test_public_branch_contract(self) -> None:
        source = """OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[1];
        creg c[1];
        h q[0];
        measure q[0] -> c[0];
        classical { if (c[0] == 1) { r1 = 7; } else { r1 = 3; } }
        """
        quantum, assembly = compile_hybrid_program(source)
        self.assertEqual(quantum, ["h q[0];", "measure q[0] -> c[0];"])
        self.assertEqual(_emulate(assembly, (0,))[1], 3)
        self.assertEqual(_emulate(assembly, (1,))[1], 7)

    def test_nested_not_equal_negative_and_associativity(self) -> None:
        source = """OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[3]; creg c[3];
        h q[0]; measure q[0] -> c[0];
        classical {
          r1 = 20 - 5 - 3;
          if (c[0] != c[1]) {
            r2 = -5;
            if (r1 == 12) { r2 = r2 + c[2]; }
          } else {
            r2 = c[0] + 9;
          }
          if (r2 != r1) { r3 = r2 - r1; }
        }
        cx q[0], q[1]; x q[2]; measure q[2] -> c[2];
        """
        quantum, assembly = compile_hybrid_program(source)
        self.assertEqual(
            quantum,
            [
                "h q[0];",
                "measure q[0] -> c[0];",
                "cx q[0], q[1];",
                "x q[2];",
                "measure q[2] -> c[2];",
            ],
        )
        labels = [line[:-1] for line in assembly.splitlines() if line.endswith(":" )]
        self.assertEqual(len(labels), len(set(labels)))
        _assert_differential(self, source, 3)

    def test_register_measurement_comparisons_and_sequential_blocks(self) -> None:
        source = """OPENQASM 2.0;
        qreg q[2]; creg c[2];
        classical { r1 = c[0] + 2; }
        h q[0];
        classical {
          if (r1 != c[1]) { r2 = r1 - c[1]; }
          r3 = 5 - r2;
          r4 = -(r3 + c[0]);
        }
        x q[1];
        """
        _assert_differential(self, source, 2)

    def test_output_is_deterministic_and_instruction_subset_is_strict(self) -> None:
        source = """OPENQASM 2.0; qreg q[1]; creg c[1];
        x q[0];
        classical {
          r1 = c[0] + 4;
          if (r1 == 5) { r2 = r1 + c[0]; } else { r2 = r1 - 2; }
        }
        """
        first = compile_hybrid_program(source)
        second = compile_hybrid_program(source)
        self.assertEqual(first, second)
        allowed = {"li", "add", "addi", "sub", "beq", "bne", "j"}
        writing = {"li", "add", "addi", "sub"}
        for line in first[1].splitlines():
            if line.endswith(":"):
                continue
            opcode, arguments = line.split(maxsplit=1)
            self.assertIn(opcode, allowed)
            if opcode in writing:
                self.assertNotEqual(arguments.split(",", 1)[0], "x0")

    def test_declared_measurement_registers_are_not_temporary_storage(self) -> None:
        source = """OPENQASM 2.0; qreg q[2]; creg c[2];
        classical { r1 = (c[0] + 5) + 1; }
        """
        _, assembly = compile_hybrid_program(source)
        # x10 and x11 are both architectural measurement inputs; x12 is the
        # first legal temporary even though c[1] is not read by the source.
        self.assertIn("addi x12, x10, 5", assembly)
        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        emulator.set_register("x10", 1)
        emulator.set_register("x11", 99)
        emulator.execute()
        self.assertEqual(emulator.get_register("x1"), 7)
        self.assertEqual(emulator.get_register("x11"), 99)

    def test_allocator_reports_true_exhaustion(self) -> None:
        source = """OPENQASM 2.0; qreg q[1]; creg c[22];
        classical { r1 = (c[0] + c[1]) + (c[2] + c[3]); }
        """
        with self.assertRaisesRegex(RegisterExhaustionError, "no temporary"):
            compile_hybrid_program(source)


if __name__ == "__main__":
    unittest.main()
