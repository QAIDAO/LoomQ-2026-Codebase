from __future__ import annotations

"""Adversarial RISC-V quantum-extension corpus: exhaustive encode/decode
round-trips over every instruction with randomized valid operands, plus
machine-word end-to-end equivalence against the mnemonic program.
"""
import random
import unittest

from starter_kit.riscv_emulator import (
    TinyRISCVEmulator,
    decode_quantum_word,
    encode_quantum_instruction,
)


def random_instruction(rng: random.Random) -> tuple[str, tuple[int, ...]]:
    name = rng.choice(("qinit", "qh", "qx", "qrz", "qcx", "qmeasure"))
    if name in ("qinit", "qh", "qx"):
        return name, (rng.randint(0, 31),)
    if name == "qrz":
        return name, (rng.randint(0, 31), rng.randint(-2048, 2047))
    if name == "qcx":
        a, b = rng.sample(range(32), 2)  # control must differ from target
        return name, (a, b)
    return name, (rng.randint(0, 31), rng.randint(0, 31))


class QuantumEncodingRoundTripTests(unittest.TestCase):
    def test_encode_decode_round_trip_for_all_instructions(self):
        rng = random.Random(20260822)
        for case in range(600):
            name, operands = random_instruction(rng)
            with self.subTest(case=case, name=name, operands=operands):
                word = encode_quantum_instruction(name, *operands)
                self.assertIsInstance(word, int)
                self.assertGreaterEqual(word, 0)
                self.assertLess(word, 1 << 32)
                decoded_name, decoded_operands = decode_quantum_word(word)
                self.assertEqual(decoded_name, name)
                self.assertEqual(tuple(decoded_operands), operands)

    def test_machine_word_program_matches_mnemonic_trace(self):
        rng = random.Random(505)
        for case in range(40):
            instructions = [random_instruction(rng) for _ in range(rng.randint(3, 10))]
            mnemonic_program = "\n".join(
                f"{name} " + ", ".join(str(o) for o in operands)
                for name, operands in instructions
            )
            words_program = "\n".join(
                f".word 0x{encode_quantum_instruction(name, *operands):08x}"
                for name, operands in instructions
            )
            mnemonic = TinyRISCVEmulator()
            mnemonic.load_program(mnemonic_program)
            worded = TinyRISCVEmulator()
            worded.load_program(words_program)
            with self.subTest(case=case):
                self.assertEqual(mnemonic.execute(), worded.execute())
                self.assertEqual(mnemonic.quantum_trace, worded.quantum_trace)


if __name__ == "__main__":
    unittest.main()
