"""End-to-end tests for the LQX-1 custom quantum RISC-V extension."""

import unittest

from starter_kit.riscv_emulator import TinyRISCVEmulator, encode_quantum_instruction


class QuantumRISCVExtensionTests(unittest.TestCase):
    def run_words(self, *words):
        emulator = TinyRISCVEmulator()
        emulator.load_program("\n".join(f"qword 0x{word:08x}" for word in words))
        return emulator, emulator.execute()

    def test_x_gate_and_measurement_write_a_classical_register(self):
        x_gate = encode_quantum_instruction("qx", q1=0)
        measure = encode_quantum_instruction("qmeas", q1=0, rd=1)
        emulator, state = self.run_words(x_gate, measure)
        self.assertEqual(state["x1"], 1)
        self.assertEqual(emulator.quantum_trace, ["qx q[0]", "qmeas q[0], x1"])

    def test_h_and_cnot_preserve_bell_measurement_correlation(self):
        h_gate = encode_quantum_instruction("qh", q1=0)
        cnot = encode_quantum_instruction("qcx", q1=0, q2=1)
        measure0 = encode_quantum_instruction("qmeas", q1=0, rd=1)
        measure1 = encode_quantum_instruction("qmeas", q1=1, rd=2)
        emulator, state = self.run_words(h_gate, cnot, measure0, measure1)
        self.assertEqual(state.get("x1", 0), state.get("x2", 0))
        self.assertEqual(emulator.quantum_trace[:2], ["qh q[0]", "qcx q[0], q[1]"])

    def test_rejects_unknown_quantum_gate(self):
        with self.assertRaises(ValueError):
            encode_quantum_instruction("qz", q1=0)


if __name__ == "__main__":
    unittest.main()
