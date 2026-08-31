from __future__ import annotations

import math
import unittest

from starter_kit.bonus_quantum_riscv import (
    CUSTOM_0_OPCODE,
    CUSTOM_1_OPCODE,
    GateCode,
    QuantumEncodingError,
    QuantumRISCVEmulator,
    compile_quantum_riscv,
    decode_word,
    encode_gate,
    encode_parameter,
)


HEADER = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[{qubits}];
creg c[{cbits}];
"""


class QuantumRISCVEncodingTests(unittest.TestCase):
    def test_custom_words_round_trip(self):
        words = (
            encode_gate(GateCode.QINIT, q0=2),
            encode_gate(GateCode.H, q0=0),
            encode_gate(GateCode.CX, q0=0, q1=1),
            encode_gate(GateCode.MEASURE, q0=0, rd=10),
        )

        self.assertEqual(words[0], 0x0001000B)
        self.assertEqual(words[1], 0x0400000B)
        self.assertEqual(words[2], 0x1210000B)
        self.assertEqual(words[3], 0x1A00050B)
        self.assertTrue(all((word & 0x7F) == CUSTOM_0_OPCODE for word in words))

        decoded = [decode_word(word) for word in words]
        self.assertEqual(decoded[0].gate, GateCode.QINIT)
        self.assertEqual(decoded[1].gate, GateCode.H)
        self.assertEqual(decoded[2].gate, GateCode.CX)
        self.assertEqual(decoded[3].gate, GateCode.MEASURE)

    def test_parameter_word_uses_signed_fixed_point(self):
        word = encode_parameter(-math.pi / 3.0)
        decoded = decode_word(word)

        self.assertEqual(word & 0x7F, CUSTOM_1_OPCODE)
        self.assertEqual(decoded.kind, "parameter")
        self.assertAlmostEqual(decoded.angle, -math.pi / 3.0, places=6)

    def test_invalid_opcode_is_rejected(self):
        with self.assertRaisesRegex(QuantumEncodingError, "unsupported custom opcode"):
            decode_word(0xFFFFFFFF)


class QuantumRISCVEndToEndTests(unittest.TestCase):
    def test_compiler_covers_all_l1_gates_and_measurement(self):
        source = HEADER.format(qubits=3, cbits=3) + """
h q[0];
x q[1];
s q[0];
sdg q[0];
t q[0];
tdg q[0];
rz(pi/3) q[0];
ry(-pi/4) q[1];
cx q[0],q[1];
cu1(pi/8) q[0],q[1];
swap q[0],q[1];
ccx q[0],q[1],q[2];
measure q -> c;
classical { r1 = c[0]; }
"""
        program = compile_quantum_riscv(source)
        decoded = [decode_word(word) for word in program.quantum_words]
        gates = {item.gate for item in decoded if item.kind == "gate"}

        self.assertEqual(
            gates,
            {
                GateCode.QINIT,
                GateCode.X,
                GateCode.H,
                GateCode.S,
                GateCode.SDG,
                GateCode.T,
                GateCode.TDG,
                GateCode.RZ,
                GateCode.RY,
                GateCode.CX,
                GateCode.CU1,
                GateCode.SWAP,
                GateCode.CCX,
                GateCode.MEASURE,
            },
        )
        self.assertEqual(
            sum(item.kind == "parameter" for item in decoded), 3
        )
        self.assertIn("qmeasure q2, x12", program.quantum_assembly)

    def test_measurement_drives_existing_classical_branch(self):
        source = HEADER.format(qubits=1, cbits=1) + """
x q[0];
measure q[0] -> c[0];
classical {
  if (c[0] == 1) { r1 = 100; } else { r1 = 10; }
  r1 = r1 + 5;
}
"""
        program = compile_quantum_riscv(source)
        emulator = QuantumRISCVEmulator(seed=7)
        emulator.load_words(program.quantum_words, program.classical_assembly)
        state = emulator.execute()

        self.assertEqual(state.get("x10"), 1)
        self.assertEqual(state.get("x1"), 105)
        self.assertEqual(emulator.measurement_log, ((0, 10, 1),))

    def test_bell_program_produces_only_correlated_results(self):
        source = HEADER.format(qubits=2, cbits=2) + """
h q[0];
cx q[0],q[1];
measure q -> c;
classical { r1 = 1; }
"""
        program = compile_quantum_riscv(source)
        emulator = QuantumRISCVEmulator(seed=19)
        emulator.load_words(program.quantum_words, program.classical_assembly)
        counts = emulator.run_shots(1000, program.classical_bit_count)

        self.assertEqual(sum(counts.values()), 1000)
        self.assertLessEqual(set(counts), {"00", "11"})
        self.assertGreater(counts.get("00", 0), 400)
        self.assertGreater(counts.get("11", 0), 400)

    def test_parameter_gate_measurement(self):
        source = HEADER.format(qubits=1, cbits=1) + """
ry(pi) q[0];
measure q[0] -> c[0];
classical { r1 = c[0]; }
"""
        program = compile_quantum_riscv(source)
        emulator = QuantumRISCVEmulator(seed=3)
        emulator.load_words(program.quantum_words, program.classical_assembly)
        state = emulator.execute()

        self.assertEqual(state.get("x10"), 1)
        self.assertEqual(state.get("x1"), 1)

    def test_ccx_and_swap_execute_on_quantum_state(self):
        source = HEADER.format(qubits=3, cbits=3) + """
x q[0];
x q[1];
ccx q[0],q[1],q[2];
swap q[0],q[2];
measure q -> c;
classical { r1 = c[0] + c[1] + c[2]; }
"""
        program = compile_quantum_riscv(source)
        emulator = QuantumRISCVEmulator(seed=5)
        emulator.load_words(program.quantum_words, program.classical_assembly)
        state = emulator.execute()

        self.assertEqual([state.get("x%d" % index) for index in (10, 11, 12)], [1, 1, 1])
        self.assertEqual(state.get("x1"), 3)

    def test_original_classical_subset_remains_compatible(self):
        emulator = QuantumRISCVEmulator()
        emulator.load_program(
            """
li x1, 5
li x2, 10
add x3, x1, x2
addi x3, x3, 1
"""
        )
        self.assertEqual(emulator.execute().get("x3"), 16)

    def test_emulator_limit_is_reported(self):
        emulator = QuantumRISCVEmulator(max_qubits=4)
        emulator.load_program("qinit 5")
        with self.assertRaisesRegex(ValueError, "qinit supports 1..4"):
            emulator.execute()


if __name__ == "__main__":
    unittest.main()
