from __future__ import annotations

"""Adversarial L3 differential corpus: deeper nesting, three measurement
injections (all 8 combos), five registers with heavy reassignment, negative
intermediate values, and multiple classical blocks — every case compared
against the independent reference interpreter.
"""
import random
import unittest

from starter_kit import adapter
from starter_kit.riscv_emulator import TinyRISCVEmulator
from starter_kit.tests.test_hybrid_compiler import (
    reference_execute,
    render_statements,
)


def build_source(statements, extra_blocks, n_creg: int) -> str:
    header = (
        "OPENQASM 2.0;\n"
        'include "qelib1.inc";\n'
        f"qreg q[{n_creg}]; creg c[{n_creg}];\n"
        "h q[0];\n"
        "classical {\n"
        f"{render_statements(statements)}\n"
        "}\n"
    )
    measured: set[int] = set()
    body_parts: list[str] = []
    for i, block in enumerate(extra_blocks):
        if i not in measured:
            body_parts.append(f"measure q[{i}] -> c[{i}];\n")
            measured.add(i)
        body_parts.append(f"classical {{\n{render_statements(block)}\n}}\n")
    body = "".join(body_parts)
    measures = "".join(
        f"measure q[{i}] -> c[{i}];\n" for i in range(n_creg) if i not in measured
    )
    return header + body + measures


def run(source: str, measurements: tuple[int, ...]) -> dict[str, int]:
    _ops, assembly = adapter.compile_hybrid(source)
    emulator = TinyRISCVEmulator()
    emulator.load_program(assembly)
    for index, value in enumerate(measurements):
        emulator.set_register(f"x{10 + index}", value)
    return emulator.execute()


class HybridAdversarialDifferentialTests(unittest.TestCase):
    def test_deep_nesting_three_measurements_all_injections(self):
        rng = random.Random(8250822)
        for case_index in range(24):
            a = rng.randint(-15, 15)
            b = rng.randint(-15, 15)
            op1, op2, op3 = (rng.choice(("==", "!=")) for _ in range(3))
            # 3-level nested if with 5 registers and reassignments
            statements = (
                ("assign", 1, ("int", a)),
                ("assign", 2, ("add", ("measurement", 0), ("int", b))),
                (
                    "if", ("reg", 2), op1, ("int", 0),
                    (
                        ("assign", 3, ("sub", ("reg", 1), ("reg", 2))),
                        (
                            "if", ("measurement", 1), op2, ("measurement", 2),
                            (("assign", 3, ("add", ("reg", 3), ("int", 7))),),
                            (("assign", 3, ("sub", ("reg", 3), ("int", 7))),),
                        ),
                        ("assign", 3, ("add", ("reg", 3), ("reg", 3))),
                    ),
                    (
                        ("assign", 3, ("int", -3)),
                        (
                            "if", ("measurement", 2), op3, ("int", 1),
                            (("assign", 3, ("add", ("reg", 1), ("reg", 2))),),
                            (("assign", 3, ("sub", ("reg", 1), ("reg", 2))),),
                        ),
                    ),
                ),
                ("assign", 4, ("add", ("reg", 3), ("reg", 1))),
                ("assign", 5, ("sub", ("reg", 4), ("reg", 2))),
            )
            source = build_source(statements, (), 3)
            for c0 in (0, 1):
                for c1 in (0, 1):
                    for c2 in (0, 1):
                        expected = reference_execute(statements, (c0, c1, c2))
                        registers = run(source, (c0, c1, c2))
                        with self.subTest(case=case_index, bits=(c0, c1, c2)):
                            for reg, value in expected.items():
                                self.assertEqual(registers.get(f"x{reg}", 0), value)

    def test_multiple_classical_blocks_with_late_measurement_injection(self):
        # quantum order preserved; later blocks observe earlier measurement results
        rng = random.Random(415043)
        for case_index in range(12):
            k1 = rng.randint(-9, 9)
            k2 = rng.randint(-9, 9)
            op = rng.choice(("==", "!="))
            first = (
                ("assign", 1, ("int", k1)),
                ("assign", 2, ("add", ("reg", 1), ("int", k2))),
            )
            second = (
                ("assign", 3, ("add", ("reg", 2), ("measurement", 0))),
                (
                    "if", ("measurement", 1), op, ("int", 0),
                    (("assign", 4, ("add", ("reg", 3), ("int", 5))),),
                    (("assign", 4, ("sub", ("reg", 3), ("int", 5))),),
                ),
            )
            source = build_source(first, (second,), 2)
            for c0 in (0, 1):
                for c1 in (0, 1):
                    # sequential blocks share register state: run both in order
                    expected = reference_execute(first + second, (c0, c1))
                    registers = run(source, (c0, c1))
                    with self.subTest(case=case_index, bits=(c0, c1)):
                        for reg, value in expected.items():
                            self.assertEqual(registers.get(f"x{reg}", 0), value)


if __name__ == "__main__":
    unittest.main()
