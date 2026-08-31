import math
import unittest

from loomq.ir import parse_qasm2
from loomq.quantum_riscv import (
    ANGLE_SCALE,
    FUNCT3,
    PARAM_FUNCT3,
    QuantumInstruction,
    assemble_qasm,
    decode,
    encode,
    quantize_angle,
)
from loomq.simulator import statevector
from riscv_emulator import TinyRISCVEmulator


BELL = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
'''


class QuantumRiscVTests(unittest.TestCase):
    def test_all_opcode_variants_round_trip(self):
        for name in FUNCT3:
            if name in {"qh", "qx", "qs", "qt"}:
                instruction = QuantumInstruction(name, q0=1)
            elif name in {"qcx", "qswap"}:
                instruction = QuantumInstruction(name, q0=1, q1=2)
            elif name == "qccx":
                instruction = QuantumInstruction(name, q0=1, q1=2, destination=3)
            else:
                instruction = QuantumInstruction(name, q0=1, destination=3)
            with self.subTest(name=name):
                self.assertEqual(decode(encode(instruction)), instruction)
        parameter_cases = [
            QuantumInstruction("qry", q0=1, destination=31),
            QuantumInstruction("qrz", q0=2, destination=30),
            QuantumInstruction("qcu1", q0=1, q1=2, destination=29),
        ]
        self.assertEqual(set(PARAM_FUNCT3), {"qry", "qrz", "qcu1"})
        for instruction in parameter_cases:
            with self.subTest(name=instruction.name):
                self.assertEqual(decode(encode(instruction)), instruction)

    def test_reserved_encoding_is_rejected(self):
        with self.assertRaises(ValueError):
            decode(encode(QuantumInstruction("qh", 0)) | (1 << 31))
        with self.assertRaises(ValueError):
            decode(encode(QuantumInstruction("qh", 0)) | (1 << 20))
        with self.assertRaises(ValueError):
            encode(QuantumInstruction("qcu1", 2, 2, 31))
        with self.assertRaises(ValueError):
            encode(QuantumInstruction("qccx", 1, 2, 2))

    def test_bell_end_to_end_has_only_correlated_measurements(self):
        assembly = assemble_qasm(BELL)
        outcomes = set()
        for seed in range(100):
            emulator = TinyRISCVEmulator(seed=seed)
            emulator.load_program(assembly)
            state = emulator.execute()
            left, right = state.get("x10", 0), state.get("x11", 0)
            self.assertEqual(left, right)
            outcomes.add(left)
        self.assertEqual(outcomes, {0, 1})

    def test_ccx_encoded_semantics(self):
        instructions = [
            ".qinit 3",
            f".word 0x{encode(QuantumInstruction('qx', 0)):08x}",
            f".word 0x{encode(QuantumInstruction('qx', 1)):08x}",
            f".word 0x{encode(QuantumInstruction('qccx', 0, 1, 2)):08x}",
            f".word 0x{encode(QuantumInstruction('qmeasure', 2, destination=12)):08x}",
        ]
        emulator = TinyRISCVEmulator()
        emulator.load_program("\n".join(instructions))
        self.assertEqual(emulator.execute()["x12"], 1)

    def test_parameter_profile_matches_reference_with_proved_bound(self):
        qasm = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
h q[1];
ry(0.73123456789) q[2];
rz(-2.3456789123) q[0];
cu1(1.2345678912) q[0], q[1];
'''
        expected = statevector(parse_qasm2(qasm))
        emulator = TinyRISCVEmulator()
        emulator.load_program(assemble_qasm(qasm))
        emulator.execute()
        overlap = sum(a.conjugate() * b for a, b in zip(expected, emulator.quantum_state))
        phase = overlap.conjugate() / abs(overlap)
        distance = math.sqrt(sum(abs(a - phase * b) ** 2 for a, b in zip(expected, emulator.quantum_state)))
        # Three gates, each quantized within 0.5 µrad; the telescoping
        # operator-norm bound is at most 1.5e-6 for this conservative profile.
        self.assertLessEqual(distance, 3 * 0.5 / ANGLE_SCALE + 1e-12)

    def test_angle_quantization_bound_after_periodic_normalization(self):
        for angle in (-12345.6789, -math.pi, -0.1, 0.0, math.pi, 99999.25):
            quantized = quantize_angle(angle) / ANGLE_SCALE
            self.assertLessEqual(abs(math.remainder(angle, 2 * math.pi) - quantized), 0.5 / ANGLE_SCALE + 1e-15)


if __name__ == "__main__":
    unittest.main()
