"""Archived end-to-end tests for the optional quantum RISC-V bonus."""

import unittest

try:
    from .riscv_emulator import TinyRISCVEmulator, decode_quantum_instruction, encode_quantum_instruction
except ImportError:
    from riscv_emulator import TinyRISCVEmulator, decode_quantum_instruction, encode_quantum_instruction


class ArchivedQuantumRISCVTests(unittest.TestCase):
    def test_binary_encoding_round_trip(self):
        cases = (
            ("qinit", (2,)),
            ("qh", (0,)),
            ("qx", (1,)),
            ("qcx", (0, 1)),
            ("qmeasure", ("x10", 0)),
        )
        for name, operands in cases:
            word = encode_quantum_instruction(name, *operands)
            decoded_name, decoded_operands = decode_quantum_instruction(word)
            self.assertEqual(encode_quantum_instruction(decoded_name, *decoded_operands), word)

    def test_encoded_bell_circuit_controls_classical_branch(self):
        words = [
            encode_quantum_instruction("qinit", 2),
            encode_quantum_instruction("qh", 0),
            encode_quantum_instruction("qcx", 0, 1),
            encode_quantum_instruction("qmeasure", "x10", 0),
            encode_quantum_instruction("qmeasure", "x11", 1),
        ]
        quantum = "\n".join(f"0x{word:08x}" for word in words)
        classical = """
bne x10, x11, ERROR
li x1, 1
j END
ERROR:
li x1, -1
END:
"""
        outcomes = set()
        for seed in range(24):
            emulator = TinyRISCVEmulator(quantum_seed=seed)
            emulator.load_program(quantum + classical)
            state = emulator.execute()
            self.assertEqual(state.get("x1"), 1)
            self.assertEqual(state.get("x10", 0), state.get("x11", 0))
            outcomes.add(state.get("x10", 0))
        self.assertEqual(outcomes, {0, 1})


if __name__ == "__main__":
    unittest.main()
