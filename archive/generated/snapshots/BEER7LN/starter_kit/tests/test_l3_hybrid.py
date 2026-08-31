"""Differential tests for the public L3 Hybrid-QASM compiler contract."""

from __future__ import annotations

from itertools import product
from pathlib import Path
import sys
import unittest


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

import adapter  # noqa: E402
from riscv_emulator import TinyRISCVEmulator  # noqa: E402


def run_assembly(assembly: str, measurements: tuple[int, ...]) -> dict[str, int]:
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    for index, value in enumerate(measurements):
        emulator.set_register(f"x{10 + index}", value)
    return emulator.execute()


def source(classical: str, quantum_tail: str = "") -> str:
    return f'''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
classical {{
{classical}
}}
{quantum_tail}
'''


class HybridParserTests(unittest.TestCase):
    def test_rejects_missing_classical_block(self) -> None:
        plain = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
'''
        with self.assertRaises(ValueError):
            adapter.compile_hybrid(plain)

    def test_rejects_malformed_classical_syntax(self) -> None:
        with self.assertRaises(ValueError):
            adapter.compile_hybrid(source("if (c[0] == 1) { r1 = 2;"))

    def test_rejects_register_outside_declared_classical_subset(self) -> None:
        with self.assertRaises(ValueError):
            adapter.compile_hybrid(source("r10 = 2;"))

    def test_rejects_measurement_index_outside_creg(self) -> None:
        with self.assertRaises(ValueError):
            adapter.compile_hybrid(source("r1 = c[3];"))


class QuantumExtractionTests(unittest.TestCase):
    def test_preserves_all_quantum_gate_and_measurement_statements_in_order(self) -> None:
        operations, _assembly = adapter.compile_hybrid(
            source("r1 = 1;", "cx q[0], q[1];\nmeasure q[1] -> c[1];")
        )
        self.assertEqual(
            operations,
            [
                "h q[0];",
                "measure q[0] -> c[0];",
                "measure q[1] -> c[1];",
                "measure q[2] -> c[2];",
                "cx q[0], q[1];",
                "measure q[1] -> c[1];",
            ],
        )

    def test_returns_only_quantum_operations_not_headers_or_classical_text(self) -> None:
        operations, _assembly = adapter.compile_hybrid(source("r1 = 42;"))
        self.assertTrue(operations)
        self.assertTrue(all(item.endswith(";") for item in operations))
        self.assertTrue(all("OPENQASM" not in item and "classical" not in item for item in operations))


class DifferentialCompilerTests(unittest.TestCase):
    def test_public_if_else_semantics_for_all_measurement_values(self) -> None:
        _ops, assembly = adapter.compile_hybrid(
            source("if (c[0] == 1) { r1 = 7; } else { r1 = 3; }")
        )
        self.assertEqual(run_assembly(assembly, (0,)).get("x1", 0), 3)
        self.assertEqual(run_assembly(assembly, (1,)).get("x1", 0), 7)

    def test_measurements_map_to_x10_plus_index(self) -> None:
        _ops, assembly = adapter.compile_hybrid(source("r1 = c[2] + c[1] + c[0];"))
        for measured in product((0, 1), repeat=3):
            self.assertEqual(run_assembly(assembly, measured).get("x1", 0), sum(measured))

    def test_chained_expression_and_sequential_assignment(self) -> None:
        _ops, assembly = adapter.compile_hybrid(
            source("r1 = 9; r2 = r1 - c[0] + 4 - c[1]; r1 = r2 + 1;")
        )
        for c0, c1 in product((0, 1), repeat=2):
            expected = 14 - c0 - c1
            state = run_assembly(assembly, (c0, c1))
            self.assertEqual(state.get("x2", 0), expected - 1)
            self.assertEqual(state.get("x1", 0), expected)

    def test_nested_conditions_and_inequality_are_exhaustive(self) -> None:
        classical = '''
if (c[0] != 1) {
  r1 = 10;
} else {
  if (c[1] == 0) { r1 = 20; } else { r1 = 30; }
}
r2 = r1 + c[2] - 1;
'''
        _ops, assembly = adapter.compile_hybrid(source(classical))
        for c0, c1, c2 in product((0, 1), repeat=3):
            base = 10 if c0 != 1 else (20 if c1 == 0 else 30)
            state = run_assembly(assembly, (c0, c1, c2))
            self.assertEqual(state.get("x1", 0), base)
            self.assertEqual(state.get("x2", 0), base + c2 - 1)

    def test_generated_programs_cover_all_injected_inputs(self) -> None:
        """A deterministic corpus with an independent arithmetic oracle."""
        for constant in (-13, -2, 0, 5, 17):
            for outer_op in ("==", "!="):
                for inner_op in ("==", "!="):
                    classical = f"""
if (c[0] {outer_op} 1) {{
  r1 = {constant};
}} else {{
  if (c[1] {inner_op} 0) {{ r1 = {constant + 9}; }} else {{ r1 = {constant - 4}; }}
}}
r2 = r1 + c[0] - c[1] + c[2];
r3 = r2 - {constant};
"""
                    _ops, assembly = adapter.compile_hybrid(source(classical))
                    for c0, c1, c2 in product((0, 1), repeat=3):
                        outer = (c0 == 1) if outer_op == "==" else (c0 != 1)
                        if outer:
                            r1 = constant
                        else:
                            inner = (c1 == 0) if inner_op == "==" else (c1 != 0)
                            r1 = constant + 9 if inner else constant - 4
                        state = run_assembly(assembly, (c0, c1, c2))
                        self.assertEqual(state.get("x1", 0), r1)
                        self.assertEqual(state.get("x2", 0), r1 + c0 - c1 + c2)
                        self.assertEqual(state.get("x3", 0), r1 + c0 - c1 + c2 - constant)
    def test_seeded_family_of_branch_and_constant_variants(self) -> None:
        for offset in (-7, -1, 0, 2, 19):
            for compare in ("==", "!="):
                classical = (
                    f"if (c[1] {compare} 1) {{ r3 = {offset}; }} "
                    f"else {{ r3 = {offset + 11}; }} r4 = r3 + c[0] - c[2];"
                )
                _ops, assembly = adapter.compile_hybrid(source(classical))
                for c0, c1, c2 in product((0, 1), repeat=3):
                    condition = (c1 == 1) if compare == "==" else (c1 != 1)
                    base = offset if condition else offset + 11
                    state = run_assembly(assembly, (c0, c1, c2))
                    self.assertEqual(state.get("x3", 0), base)
                    self.assertEqual(state.get("x4", 0), base + c0 - c2)

    def test_highest_representable_measurement_and_all_user_registers(self) -> None:
        """c[21] occupies x31, so codegen must not reserve an input as scratch."""
        source = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[22];
creg c[22];
measure q -> c;
classical {
  // This brace is a comment, not the end of the classical block: }
  r9 = 4;
  r1 = (c[21] + c[20]) - 2;
  r2 = r1 + r1 + c[0];
  if ((r2 - c[21]) != (c[20] + c[0] - 4)) { r3 = r2 + 7; } else { r3 = r2 - 7; }
  r4 = r3 - r2;
  r5 = r4 + r9;
  r6 = r5 - c[0];
  r7 = r6 + r1;
  r8 = r7 - r2;
  r9 = r8 - c[20];
}
'''
        _operations, assembly = adapter.compile_hybrid(source)
        samples = (
            (0,) * 22,
            (1,) * 22,
            (0,) * 20 + (1, 0),
            (1,) + (0,) * 20 + (1,),
        )
        for measured in samples:
            c0, c20, c21 = measured[0], measured[20], measured[21]
            r1 = c21 + c20 - 2
            r2 = r1 + r1 + c0
            r3 = r2 + 7 if c21 + c20 != 0 else r2 - 7
            expected = {
                1: r1,
                2: r2,
                3: r3,
                4: r3 - r2,
            }
            expected[5] = expected[4] + 4
            expected[6] = expected[5] - c0
            expected[7] = expected[6] + r1
            expected[8] = expected[7] - r2
            expected[9] = expected[8] - c20
            state = run_assembly(assembly, measured)
            self.assertEqual(
                {index: state.get(f"x{index}", 0) for index in range(1, 10)},
                expected,
            )
            self.assertEqual(state.get("x31", 0), c21)


if __name__ == "__main__":
    unittest.main()