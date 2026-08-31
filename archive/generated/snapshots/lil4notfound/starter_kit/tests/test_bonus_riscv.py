import math
import re
import unittest

try:
    from starter_kit import adapter
    from starter_kit.loomq_bonus import (
        QuantumRISCVEmulator,
        compile_hybrid_bonus,
        compile_quantum_qasm,
        decode_program,
        decode_word,
        encode_assembly,
        encode_instruction,
    )
    from starter_kit.loomq_bonus.isa import ANGLE_STEP, units_to_angle
    from starter_kit.riscv_emulator import TinyRISCVEmulator
except ModuleNotFoundError:
    import adapter
    from loomq_bonus import (
        QuantumRISCVEmulator,
        compile_hybrid_bonus,
        compile_quantum_qasm,
        decode_program,
        decode_word,
        encode_assembly,
        encode_instruction,
    )
    from loomq_bonus.isa import ANGLE_STEP, units_to_angle
    from riscv_emulator import TinyRISCVEmulator


BELL_HYBRID = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
classical {
  if (c[0] == c[1]) { r1 = 1; } else { r1 = 0; }
}
"""

ALL_GATES = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
x q[1];
s q[0];
sdg q[0];
t q[0];
tdg q[0];
ry(pi/2) q[0];
rz(-pi/4) q[1];
cx q[0], q[1];
cu1(pi/8) q[1], q[2];
swap q[0], q[2];
ccx q[0], q[1], q[2];
measure q -> c;
"""


class QuantumInstructionEncodingTests(unittest.TestCase):
    def test_known_layout_and_round_trip(self):
        qinit = encode_instruction("qinit", (2,))
        self.assertEqual(qinit, (1 << 25) | (2 << 7) | 0x0B)
        self.assertEqual(decode_word(qinit).assembly(), "qinit 2")

        source = """qinit 3
qh 0
qparam 512
qry 1
qcx 0, 2
qccx 0, 1, 2
qmeasure 2, x10
"""
        words = encode_assembly(source)
        decoded = decode_program(words)
        self.assertEqual(tuple(item.assembly() for item in decoded), tuple(source.splitlines()))
        self.assertAlmostEqual(units_to_angle(512), math.pi / 2)

    def test_illegal_words_and_sequences_are_rejected(self):
        with self.assertRaises(ValueError):
            decode_word(0)
        with self.assertRaises(ValueError):
            decode_word(0x2B | (1 << 7))
        with self.assertRaises(ValueError):
            encode_instruction("qmeasure", (0, 0))
        with self.assertRaises(ValueError):
            encode_instruction("qcx", (1, 1))
        with self.assertRaises(ValueError):
            decode_program(encode_assembly("qparam 1\nqh 0\n"))
        with self.assertRaises(ValueError):
            decode_program(encode_assembly("qinit 1\nqry 0\n"))

    def test_angle_resolution_is_explicit(self):
        self.assertAlmostEqual(ANGLE_STEP, math.pi / 1024)
        with self.assertRaises(ValueError):
            encode_instruction("qparam", (2048,))


class QuantumBonusCompilerTests(unittest.TestCase):
    def test_all_competition_gates_have_custom_encodings(self):
        program = compile_quantum_qasm(ALL_GATES)
        mnemonics = tuple(item.mnemonic for item in decode_program(program.machine_words))
        for expected in (
            "qinit",
            "qh",
            "qx",
            "qs",
            "qsdg",
            "qt",
            "qtdg",
            "qry",
            "qrz",
            "qcx",
            "qcu1",
            "qswap",
            "qccx",
            "qmeasure",
        ):
            self.assertIn(expected, mnemonics)
        self.assertEqual(len(program.machine_words), len(program.machine_hex))
        self.assertTrue(all(re.fullmatch(r"0x[0-9a-f]{8}", item) for item in program.machine_hex))

    def test_base_l3_contract_is_unchanged_and_bonus_is_separate(self):
        quantum, classical = adapter.compile_hybrid(BELL_HYBRID)
        self.assertEqual(
            quantum,
            ["h q[0];", "cx q[0], q[1];", "measure q -> c;"],
        )
        allowed = {"li", "add", "sub", "addi", "beq", "bne", "j"}
        operations = {
            line.replace(",", " ").split()[0].lower()
            for line in classical.splitlines()
            if line.strip() and not line.rstrip().endswith(":")
        }
        self.assertLessEqual(operations, allowed)
        TinyRISCVEmulator().load_program(classical)

        bonus = compile_hybrid_bonus(BELL_HYBRID)
        self.assertEqual(bonus.quantum_operations, tuple(quantum))
        self.assertEqual(bonus.classical_assembly, classical)
        self.assertIn("qinit 2", bonus.quantum_assembly)
        self.assertNotIn("qh", classical.lower())


class QuantumBonusEndToEndTests(unittest.TestCase):
    def test_encoded_bell_program_drives_classical_branch(self):
        program = compile_hybrid_bonus(BELL_HYBRID)
        outcomes = {"00": 0, "11": 0}
        for seed in range(256):
            emulator = QuantumRISCVEmulator(seed=seed)
            emulator.load_quantum_words(program.machine_words, program.classical_assembly)
            registers = emulator.execute()
            c0 = emulator.get_register("x10")
            c1 = emulator.get_register("x11")
            self.assertEqual(c0, c1)
            self.assertEqual(registers.get("x1"), 1)
            outcomes[f"{c1}{c0}"] += 1
        self.assertGreater(outcomes["00"], 80)
        self.assertGreater(outcomes["11"], 80)

    def test_parameter_word_executes_rotation(self):
        words = encode_assembly("qinit 1\nqparam 1024\nqry 0\nqmeasure 0, x10\n")
        emulator = QuantumRISCVEmulator(seed=7)
        emulator.load_quantum_words(words)
        emulator.execute()
        self.assertEqual(emulator.get_register("x10"), 1)

    def test_runtime_rejects_out_of_range_qubit(self):
        words = encode_assembly("qinit 1\nqh 1\n")
        emulator = QuantumRISCVEmulator()
        emulator.load_quantum_words(words)
        with self.assertRaises(ValueError):
            emulator.execute()


if __name__ == "__main__":
    unittest.main()
