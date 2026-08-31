"""Submission-contained end-to-end tests for the quantum RISC-V Bonus."""

import math
import random
import unittest

try:
    from .adapter import (
        HybridCompileError,
        QUANTUM_CUSTOM_OPCODE,
        compile_hybrid,
        compile_hybrid_bonus,
    )
    from .riscv_emulator import TinyRISCVEmulator
except ImportError:  # Running from the starter_kit evaluation root.
    from adapter import (
        HybridCompileError,
        QUANTUM_CUSTOM_OPCODE,
        compile_hybrid,
        compile_hybrid_bonus,
    )
    from riscv_emulator import TinyRISCVEmulator


def _source(operations, classical="r1 = c[0];", qsize=3, csize=None, extra_qreg=""):
    if csize is None:
        csize = qsize
    return f'''OPENQASM 2.0;
include "qelib1.inc";
qreg q[{qsize}];
{extra_qreg}
creg c[{csize}];
{operations}
classical {{ {classical} }}
'''


def _word(gate_id, q0=0, q1=0, q2=0, parameter=False, version=1, opcode=0x0B):
    return (
        opcode
        | (q0 << 7)
        | (q1 << 12)
        | (q2 << 17)
        | (gate_id << 22)
        | (int(parameter) << 27)
        | (version << 28)
    )


class QuantumRiscVEndToEndTests(unittest.TestCase):
    def test_all_gates_round_trip_and_classical_control(self):
        operations = '''
        h q[0]; x q[1]; s q[2]; sdg q[0]; t q[1]; tdg q[2];
        rz(pi/2) q[0]; ry(-pi/4) q[1]; cx q[0], q[1];
        swap q[1], q[2]; ccx q[0], q[1], q[2]; cu1(pi/8) q[0], q[2];
        measure q -> c;
        '''
        quantum, assembly = compile_hybrid_bonus(
            _source(
                operations,
                "if (c[0] != c[1]) { r1 = 17; } else { r1 = -4; } "
                "r2 = r1 + c[2];",
            )
        )
        self.assertEqual(len(quantum), 13)
        self.assertIn("qinst", assembly)

        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        for index, value in enumerate((1, 0, 1)):
            emulator.set_register(f"x{10 + index}", value)
        state = emulator.execute()
        decoded = emulator.get_quantum_operations()

        self.assertEqual(state["x1"], 17)
        self.assertEqual(state["x2"], 18)
        self.assertEqual(
            [item["gate"] for item in decoded],
            [
                "h", "x", "s", "sdg", "t", "tdg", "rz", "ry",
                "cx", "swap", "ccx", "cu1", "measure", "measure", "measure",
            ],
        )
        self.assertAlmostEqual(decoded[6]["parameter"], math.pi / 2, places=6)
        self.assertAlmostEqual(decoded[7]["parameter"], -math.pi / 4, places=6)
        self.assertEqual(decoded[-1]["qubits"], [2])
        self.assertEqual(decoded[-1]["clbits"], [2])

    def test_base_l3_output_remains_officially_compatible(self):
        program = _source("h q[0]; measure q[0] -> c[0];")
        _, base_assembly = compile_hybrid(program)
        _, bonus_assembly = compile_hybrid_bonus(program)
        self.assertNotIn("qinst", base_assembly)
        self.assertIn("qinst", bonus_assembly)

    def test_all_measurement_combinations_preserve_classical_semantics(self):
        _, assembly = compile_hybrid_bonus(
            _source(
                "h q[0]; measure q -> c;",
                "if (c[0] == c[1]) { r1 = c[2] + 5; } "
                "else { r1 = c[2] - 5; }",
            )
        )
        for value in range(8):
            bits = [(value >> index) & 1 for index in range(3)]
            emulator = TinyRISCVEmulator()
            emulator.load_program(assembly)
            for index, bit in enumerate(bits):
                emulator.set_register(f"x{10 + index}", bit)
            state = emulator.execute()
            expected = bits[2] + 5 if bits[0] == bits[1] else bits[2] - 5
            self.assertEqual(state.get("x1", 0), expected)

    def test_seeded_random_classical_programs(self):
        rng = random.Random(20260820)
        for case_index in range(50):
            first, second = rng.randint(-10_000, 10_000), rng.randint(-10_000, 10_000)
            classical = f'''
            r1 = {first}; r2 = {second}; r3 = r1 + c[0] - r2;
            if ((r3 + c[1]) != ({first} - {second})) {{
              r4 = r3 + c[2];
            }} else {{ r4 = r2 - c[2]; }}
            r5 = r4 + r1 - r3;
            '''
            _, assembly = compile_hybrid_bonus(
                _source("h q[0]; measure q -> c;", classical)
            )
            for measured in range(8):
                bits = [(measured >> index) & 1 for index in range(3)]
                r3 = first + bits[0] - second
                r4 = r3 + bits[2] if r3 + bits[1] != first - second else second - bits[2]
                expected = (first, second, r3, r4, r4 + first - r3)
                emulator = TinyRISCVEmulator()
                emulator.load_program(assembly)
                for index, bit in enumerate(bits):
                    emulator.set_register(f"x{10 + index}", bit)
                emulator.execute()
                self.assertEqual(
                    tuple(emulator.get_register(f"x{i}") for i in range(1, 6)),
                    expected,
                    msg=f"case={case_index}, measured={measured}",
                )


class QuantumRiscVBoundaryTests(unittest.TestCase):
    def test_custom_zero_opcode_and_maximum_qubit_index(self):
        _, assembly = compile_hybrid_bonus(
            _source(
                "ccx q[29], q[30], q[31]; rz(3.4e38) q[31];",
                qsize=32,
                csize=1,
            )
        )
        qinst = [line for line in assembly.splitlines() if line.startswith("qinst")]
        first_word = int(qinst[0].split()[1].rstrip(","), 0)
        self.assertEqual(first_word & 0x7F, QUANTUM_CUSTOM_OPCODE)
        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        emulator.execute()
        decoded = emulator.get_quantum_operations()
        self.assertEqual(decoded[0]["qubits"], [29, 30, 31])
        self.assertTrue(math.isfinite(decoded[1]["parameter"]))

    def test_invalid_quantum_sources_are_rejected(self):
        invalid = (
            _source("z q[0];"),
            _source("h(1) q[0];"),
            _source("rz q[0];"),
            _source("cx q[0];"),
            _source("cx q[0], q[0];"),
            _source("measure q[0] -> c;"),
            _source("measure q -> c;", qsize=2, csize=3),
            _source("rz(secret) q[0];"),
            _source("rz(1/0) q[0];"),
            _source("h q[0];", qsize=33, csize=3),
            _source("h q[0];", extra_qreg="qreg aux[1];"),
        )
        for program in invalid:
            with self.subTest(program=program):
                with self.assertRaises(HybridCompileError):
                    compile_hybrid_bonus(program)

    def test_malformed_instruction_words_are_rejected_atomically(self):
        h_word = _word(1)
        malformed = (
            "qinst",
            "qinst nope",
            "qinst -1",
            "qinst 0x100000000",
            f"qinst 0x{_word(1, opcode=0x13):08x}",
            f"qinst 0x{_word(1, version=2):08x}",
            f"qinst 0x{_word(31):08x}",
            f"qinst 0x{_word(1, parameter=True):08x}",
            f"qinst 0x{h_word:08x}, 0x00000000",
            f"qinst 0x{_word(9, q0=1, q1=1):08x}",
            f"qinst 0x{_word(1, q1=1):08x}",
            f"qinst 0x{_word(7, parameter=True):08x}, 0x7fc00000",
        )
        for assembly in malformed:
            with self.subTest(assembly=assembly):
                emulator = TinyRISCVEmulator()
                emulator.load_program(assembly)
                with self.assertRaises((ValueError, IndexError)):
                    emulator.execute()
                self.assertEqual(emulator.get_quantum_operations(), [])

    def test_combined_execution_step_limit(self):
        accepted = _source("\n".join("h q[0];" for _ in range(999)), qsize=1, csize=1)
        _, assembly = compile_hybrid_bonus(accepted)
        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        emulator.execute()

        rejected = _source("\n".join("h q[0];" for _ in range(1000)), qsize=1, csize=1)
        with self.assertRaisesRegex(HybridCompileError, "1000 steps"):
            compile_hybrid_bonus(rejected)

    def test_quantum_operation_snapshot_is_defensive_and_resets(self):
        _, assembly = compile_hybrid_bonus(_source("h q[0];"))
        emulator = TinyRISCVEmulator()
        emulator.load_program(assembly)
        emulator.execute()
        snapshot = emulator.get_quantum_operations()
        snapshot[0]["qubits"][0] = 31
        self.assertEqual(emulator.get_quantum_operations()[0]["qubits"], [0])
        emulator.load_program("li x1, 1")
        self.assertEqual(emulator.get_quantum_operations(), [])


if __name__ == "__main__":
    unittest.main()
