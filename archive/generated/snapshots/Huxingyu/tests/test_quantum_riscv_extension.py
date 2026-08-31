import unittest

from starter_kit.riscv_emulator import (
    QUANTUM_OPCODE,
    TinyRISCVEmulator,
    decode_quantum_instruction,
    encode_quantum_instruction,
)


TEXT_BELL = """
qinit 2
qh 0
qcx 0, 1
qmeasure x10, 0
qmeasure x11, 1
bne x10, x11, ERROR
li x1, 1
j END
ERROR:
li x1, -1
END:
"""


class QuantumRISCVExtensionTests(unittest.TestCase):
    def test_all_instruction_encodings_round_trip(self):
        cases = (
            ("qinit", (3,)),
            ("qh", (2,)),
            ("qx", (1,)),
            ("qcx", (1, 2)),
            ("qmeasure", ("x7", 2)),
        )
        for name, operands in cases:
            word = encode_quantum_instruction(name, *operands)
            self.assertEqual(word & 0x7F, QUANTUM_OPCODE)
            decoded_name, _ = decode_quantum_instruction(word)
            self.assertEqual(decoded_name, name)
            self.assertEqual(
                encode_quantum_instruction(decoded_name, *decode_quantum_instruction(word)[1]),
                word,
            )

    def test_textual_bell_program_reaches_classical_success_branch(self):
        outcomes = set()
        for seed in range(32):
            emulator = TinyRISCVEmulator(quantum_seed=seed)
            emulator.load_program(TEXT_BELL)
            state = emulator.execute()
            self.assertEqual(state.get("x1"), 1, seed)
            self.assertEqual(state.get("x10", 0), state.get("x11", 0), seed)
            outcomes.add(state.get("x10", 0))
        self.assertEqual(outcomes, {0, 1})

    def test_raw_encoded_bell_program_executes_end_to_end(self):
        words = [
            encode_quantum_instruction("qinit", 2),
            encode_quantum_instruction("qh", 0),
            encode_quantum_instruction("qcx", 0, 1),
            encode_quantum_instruction("qmeasure", "x10", 0),
            encode_quantum_instruction("qmeasure", "x11", 1),
        ]
        program = "\n".join(f"0x{word:08x}" for word in words) + "\nbne x10, x11, ERROR\nli x1, 1\nj END\nERROR:\nli x1, -1\nEND:\n"
        emulator = TinyRISCVEmulator(quantum_seed=7)
        emulator.load_program(program)
        state = emulator.execute()
        self.assertEqual(state.get("x1"), 1)
        self.assertEqual(state.get("x10", 0), state.get("x11", 0))

    def test_invalid_or_noncanonical_words_are_rejected(self):
        with self.assertRaises(ValueError):
            decode_quantum_instruction(0xFFFFFFFF)
        with self.assertRaises(ValueError):
            encode_quantum_instruction("qcx", 0, 32)
        with self.assertRaises(ValueError):
            encode_quantum_instruction("qinit", 0)


if __name__ == "__main__":
    unittest.main()
