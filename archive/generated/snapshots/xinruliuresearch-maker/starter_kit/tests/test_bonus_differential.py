"""Differential tests across source mnemonics and encoded machine words."""

from __future__ import annotations

import random
import unittest

from loomq.bonus import QuantumRISCVEmulator, assemble_quantum_line


class BonusDifferentialTests(unittest.TestCase):
    def test_random_circuits_match_after_binary_round_trip(self) -> None:
        rng = random.Random(0x10_0B_2026)
        for case_index in range(200):
            lines = [
                "li x1, 0",
                "li x2, 1",
                "li x3, 2",
                "li x4, 3",
                "li x5, 51472",
            ]
            quantum_lines = ["qinit x4"]
            for _ in range(rng.randint(1, 24)):
                kind = rng.choice(("single", "double", "rotation", "triple"))
                if kind == "single":
                    quantum_lines.append(
                        f"{rng.choice(('qh', 'qx', 'qs', 'qt'))} x{rng.randint(1, 3)}"
                    )
                else:
                    if kind == "rotation":
                        quantum_lines.append(
                            f"{rng.choice(('qry', 'qrz'))} x{rng.randint(1, 3)}, x5"
                        )
                        continue
                    if kind == "triple":
                        operands = rng.sample((1, 2, 3), 3)
                        quantum_lines.append(
                            f"qccx x{operands[0]}, x{operands[1]}, x{operands[2]}"
                        )
                        continue
                    first, second = rng.sample((1, 2, 3), 2)
                    quantum_lines.append(
                        f"{rng.choice(('qcx', 'qswap'))} x{first}, x{second}"
                    )
            mnemonic_program = "\n".join(lines + quantum_lines)
            encoded_program = "\n".join(
                lines
                + [
                    f".word 0x{assemble_quantum_line(line):08x}"
                    for line in quantum_lines
                ]
            )
            source_emulator = QuantumRISCVEmulator(seed=case_index)
            binary_emulator = QuantumRISCVEmulator(seed=case_index)
            source_emulator.load_program(mnemonic_program)
            binary_emulator.load_program(encoded_program)
            source_emulator.execute()
            binary_emulator.execute()
            self.assertEqual(
                source_emulator.quantum_state.probabilities(),
                binary_emulator.quantum_state.probabilities(),
                msg=f"case={case_index}",
            )
            self.assertEqual(source_emulator.quantum_log, binary_emulator.quantum_log)


if __name__ == "__main__":
    unittest.main()
