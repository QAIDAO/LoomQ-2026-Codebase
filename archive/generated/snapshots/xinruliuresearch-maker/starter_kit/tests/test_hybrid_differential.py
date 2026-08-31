"""Deterministic randomized differential coverage against TinyRISCVEmulator."""

from __future__ import annotations

import itertools
import random
import unittest

from loomq.hybrid import compile_hybrid_program, interpret_hybrid_program
from riscv_emulator import TinyRISCVEmulator


class HybridDifferentialTests(unittest.TestCase):
    def test_five_hundred_generated_programs_all_measurements(self) -> None:
        randomizer = random.Random(0x10_0C_2026)
        atoms = ("-9", "-1", "0", "3", "11", "r1", "r2", "c[0]", "c[1]", "c[2]")

        def expression(max_terms: int = 4) -> str:
            count = randomizer.randint(1, max_terms)
            result = randomizer.choice(atoms)
            for _ in range(count - 1):
                result += f" {randomizer.choice(('+', '-'))} {randomizer.choice(atoms)}"
            if randomizer.random() < 0.2:
                result = f"-({result})"
            return result

        for program_index in range(500):
            comparator_1 = randomizer.choice(("==", "!="))
            comparator_2 = randomizer.choice(("==", "!="))
            source = f"""OPENQASM 2.0;
            include "qelib1.inc";
            qreg q[3]; creg c[3];
            h q[0]; measure q[0] -> c[0];
            classical {{
              r1 = {expression()};
              r2 = {expression()};
              if ({expression(2)} {comparator_1} {expression(2)}) {{
                r3 = {expression()};
                if (r1 {comparator_2} c[2]) {{ r4 = {expression()}; }}
                else {{ r4 = {expression()}; }}
              }} else {{
                r3 = {expression()};
              }}
              r5 = {expression()};
            }}
            cx q[0], q[1]; measure q[2] -> c[2];
            """
            quantum, assembly = compile_hybrid_program(source)
            self.assertEqual(
                quantum,
                [
                    "h q[0];",
                    "measure q[0] -> c[0];",
                    "cx q[0], q[1];",
                    "measure q[2] -> c[2];",
                ],
            )
            for bits in itertools.product((0, 1), repeat=3):
                expected = interpret_hybrid_program(
                    source, {index: bit for index, bit in enumerate(bits)}
                )
                emulator = TinyRISCVEmulator()
                emulator.load_program(assembly)
                for index, bit in enumerate(bits):
                    emulator.set_register(f"x{10 + index}", bit)
                emulator.execute()
                actual = {
                    f"r{index}": emulator.get_register(f"x{index}")
                    for index in range(1, 10)
                }
                self.assertEqual(
                    actual,
                    expected,
                    msg=f"program={program_index}, measurements={bits}\n{source}\n{assembly}",
                )


if __name__ == "__main__":
    unittest.main()
