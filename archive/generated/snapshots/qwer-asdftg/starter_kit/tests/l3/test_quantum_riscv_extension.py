import unittest

from starter_kit.riscv_emulator import (
    TinyRISCVEmulator,
    decode_custom0_instruction,
    encode_qcx,
    encode_qh,
    encode_qmeas,
)


class QuantumRiscVExtensionTests(unittest.TestCase):
    def test_custom0_encoder_decoder_round_trips_all_instruction_fields(self):
        self.assertEqual(decode_custom0_instruction(encode_qh(7)), ("qh", (7,)))
        self.assertEqual(decode_custom0_instruction(encode_qcx(2, 6)), ("qcx", (2, 6)))
        self.assertEqual(decode_custom0_instruction(encode_qmeas(31, 5)), ("qmeas", (31, 5)))

        with self.assertRaises(ValueError):
            encode_qh(8)
        with self.assertRaises(ValueError):
            decode_custom0_instruction(0x0200000B)  # funct7 must be zero in v1

    def test_raw_bell_program_measures_correlated_bits_into_classical_registers(self):
        bell_words = [
            encode_qh(0),
            encode_qcx(0, 1),
            encode_qmeas(10, 0),
            encode_qmeas(11, 1),
        ]

        emulator = TinyRISCVEmulator(random_seed=20260824)
        emulator.load_program(bell_words)
        state = emulator.execute()

        self.assertIn("x10", state)
        self.assertIn("x11", state)
        self.assertEqual(state["x10"], state["x11"])

    def test_mnemonics_seed_and_load_reset_are_deterministic(self):
        program = """
        qh q0
        qmeas x5, q0
        """

        first = TinyRISCVEmulator(random_seed=17)
        first.load_program(program)
        first_state = first.execute()

        second = TinyRISCVEmulator(random_seed=17)
        second.load_program(program)
        second_state = second.execute()
        self.assertEqual(first_state.get("x5", 0), second_state.get("x5", 0))

        first.load_program("qmeas x6, q0")
        self.assertEqual(first.execute().get("x6", 0), 0)

    def test_classical_assembly_regression_is_unchanged(self):
        emulator = TinyRISCVEmulator()
        emulator.load_program(
            """
            li x1, 5
            addi x2, x1, 3
            sub x3, x2, x1
            """
        )
        self.assertEqual(emulator.execute(), {"x1": 5, "x2": 8, "x3": 3})


if __name__ == "__main__":
    unittest.main()
