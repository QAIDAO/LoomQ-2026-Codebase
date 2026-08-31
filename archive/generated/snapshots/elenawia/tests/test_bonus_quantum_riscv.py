import unittest

from starter_kit.riscv_emulator import (
    QUANTUM_CUSTOM_OPCODE,
    TinyRISCVEmulator,
    decode_quantum_instruction,
    encode_quantum_instruction,
    run_quantum_riscv_shots,
)


BELL_PROGRAM = """
qinit 2
qh q0
qcx q0, q1
qmeasure q0, x1
qmeasure q1, x2
"""


class BonusQuantumRISCVTests(unittest.TestCase):
    def test_custom_opcode_encoding_round_trips_quantum_fields(self):
        encoded_qinit = encode_quantum_instruction("qinit", size=2)
        encoded_qh = encode_quantum_instruction("qh", qubit=0)
        encoded_qcx = encode_quantum_instruction("qcx", qubit=0, target=1)
        encoded_qmeasure = encode_quantum_instruction("qmeasure", qubit=1, rd=2)

        self.assertEqual(encoded_qinit & 0x7F, QUANTUM_CUSTOM_OPCODE)
        self.assertEqual(decode_quantum_instruction(encoded_qinit), {"op": "qinit", "opcode": QUANTUM_CUSTOM_OPCODE, "funct3": 0, "funct7": 0, "size": 2})
        self.assertEqual(decode_quantum_instruction(encoded_qh)["op"], "qh")
        self.assertEqual(decode_quantum_instruction(encoded_qh)["qubit"], 0)
        self.assertEqual(decode_quantum_instruction(encoded_qcx)["op"], "qcx")
        self.assertEqual(decode_quantum_instruction(encoded_qcx)["target"], 1)
        self.assertEqual(decode_quantum_instruction(encoded_qmeasure)["op"], "qmeasure")
        self.assertEqual(decode_quantum_instruction(encoded_qmeasure)["rd"], 2)

    def test_bell_program_produces_correlated_counts(self):
        counts = run_quantum_riscv_shots(BELL_PROGRAM, shots=512, readout_registers=["x1", "x2"])

        self.assertEqual(set(counts), {"00", "11"})
        self.assertGreater(counts["00"], 180)
        self.assertGreater(counts["11"], 180)

    def test_quantum_measurement_writes_classical_registers(self):
        emulator = TinyRISCVEmulator()
        emulator.set_quantum_seed(1)
        emulator.load_program(BELL_PROGRAM)
        state = emulator.execute()

        self.assertIn(state.get("x1"), (0, 1))
        self.assertEqual(state.get("x1"), state.get("x2"))

    def test_classical_riscv_still_works_after_quantum_extension(self):
        program = """
        li x1, 5
        li x2, 10
        add x3, x1, x2
        addi x3, x3, 1
        """
        emulator = TinyRISCVEmulator()
        emulator.load_program(program)
        state = emulator.execute()

        self.assertEqual(state.get("x3"), 16)


if __name__ == "__main__":
    unittest.main()
