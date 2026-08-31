"""Binary contract tests for the experimental LoomQ quantum RISC-V ISA."""

from __future__ import annotations

import random
import unittest

from loomq.bonus.isa import (
    QuantumDecodingError,
    QuantumEncodingError,
    assemble_quantum_line,
    decode_instruction,
    disassemble_word,
    encode_instruction,
    fixed_to_radians,
    radians_to_fixed,
    word_to_little_endian_bytes,
)


class BonusISATests(unittest.TestCase):
    def test_known_machine_words_are_stable(self) -> None:
        self.assertEqual(encode_instruction("qh", rs1="x1"), 0x0000800B)
        self.assertEqual(encode_instruction("qx", rs1="x1"), 0x0200800B)
        self.assertEqual(
            encode_instruction("qcx", rs1="x1", rs2="x2"), 0x0020900B
        )
        self.assertEqual(
            encode_instruction("qmeasure", rd="x3", rs1="x2"), 0x0001218B
        )
        self.assertEqual(encode_instruction("qinit", rs1="x1"), 0x0000B00B)
        self.assertEqual(
            encode_instruction("qry", rs1="x1", rs2="x2"), 0x0020C00B
        )
        self.assertEqual(
            encode_instruction("qrz", rs1="x1", rs2="x2"), 0x0220C00B
        )
        self.assertEqual(
            encode_instruction("qccx", rs1="x1", rs2="x2", rd="x3"),
            0x0020D18B,
        )
        self.assertEqual(
            word_to_little_endian_bytes(0x0020900B), bytes.fromhex("0b902000")
        )

    def test_all_mnemonics_round_trip(self) -> None:
        lines = (
            "qh x1",
            "qx x2",
            "qs x3",
            "qt x4",
            "qcx x5, x6",
            "qswap x7, x8",
            "qmeasure x9, x10",
            "qinit x11",
            "qry x12, x13",
            "qrz x14, x15",
            "qccx x16, x17, x18",
        )
        for line in lines:
            with self.subTest(line=line):
                word = assemble_quantum_line(line)
                self.assertEqual(disassemble_word(word), line)
                self.assertEqual(decode_instruction(word).word, word)

    def test_register_fields_round_trip_for_many_operands(self) -> None:
        rng = random.Random(20260821)
        for _ in range(1000):
            first, second = rng.sample(range(32), 2)
            word = encode_instruction("qswap", rs1=first, rs2=second)
            decoded = decode_instruction(word)
            self.assertEqual((decoded.rs1, decoded.rs2), (first, second))

    def test_comments_case_and_spacing_are_normalized(self) -> None:
        word = assemble_quantum_line("  QCX X3 ,  x4  # entangle")
        self.assertEqual(disassemble_word(word), "qcx x3, x4")

    def test_q16_16_angle_conversion_is_stable_and_supports_twos_complement(self) -> None:
        encoded = radians_to_fixed(3.141592653589793 / 2)
        self.assertEqual(encoded, 102944)
        self.assertAlmostEqual(fixed_to_radians(encoded), 3.141592653589793 / 2, places=5)
        self.assertEqual(fixed_to_radians(0xFFFF0000), -1.0)
        self.assertEqual(radians_to_fixed(-1.0), -65536)

    def test_encoding_rejects_invalid_or_noncanonical_operands(self) -> None:
        invalid_calls = (
            lambda: encode_instruction("unknown", rs1="x1"),
            lambda: encode_instruction("qh", rs1="q1"),
            lambda: encode_instruction("qh", rs1=32),
            lambda: encode_instruction("qh", rs1=True),
            lambda: encode_instruction("qh", rs1=1, rs2=2),
            lambda: encode_instruction("qcx", rs1=1, rs2=2, rd=3),
            lambda: encode_instruction("qmeasure", rs1=1, rd=0),
            lambda: assemble_quantum_line("qcx x1"),
            lambda: assemble_quantum_line("qccx x1, x2"),
            lambda: radians_to_fixed(float("inf")),
        )
        for call in invalid_calls:
            with self.subTest(call=call), self.assertRaises(QuantumEncodingError):
                call()

        with self.assertRaises(QuantumDecodingError):
            fixed_to_radians(1 << 32)

    def test_decoder_rejects_non_custom_reserved_and_noncanonical_words(self) -> None:
        invalid_words = (
            0x00000013,  # RISC-V addi, not custom-0
            1 << 32,
            -1,
            True,
            0x0FE0000B,  # unassigned funct3/funct7 combination
            encode_instruction("qh", rs1=1) | (1 << 7),  # forbidden rd
            encode_instruction("qmeasure", rd=3, rs1=1) & ~(0x1F << 7),
        )
        for word in invalid_words:
            with self.subTest(word=word), self.assertRaises(QuantumDecodingError):
                decode_instruction(word)


if __name__ == "__main__":
    unittest.main()
